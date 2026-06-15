"""NL→SQL orchestration tests with a mocked provider (no network)."""

import pytest

from src import nl2sql
from src.core.llm.base import LLMError, NLSQLResult
from src.schema import ColumnDefinition, Schema, TableDefinition


class FakeProvider:
    name = "external"

    def __init__(self, text: str):
        self._text = text

    def is_available(self) -> bool:
        return True

    def resolve_model(self, requested=None) -> str:
        return "fake-model"

    def complete(self, system, user, model=None) -> str:
        return self._text


def _schema() -> Schema:
    s = Schema()
    s.tables["EMP"] = TableDefinition(
        name="EMP",
        columns=[
            ColumnDefinition(table_name="EMP", column_name="EMP_ID"),
            ColumnDefinition(table_name="EMP", column_name="SALARY"),
        ],
    )
    return s


def _patch_provider(monkeypatch, text: str):
    monkeypatch.setattr(nl2sql, "select_provider", lambda cfg=None, policy=None: FakeProvider(text))


def test_parses_sql_and_explanation_and_confidence(monkeypatch):
    _patch_provider(monkeypatch, "```sql\nSELECT emp_id, salary FROM emp\n```\nExplanation: Returns employee pay.")
    result = nl2sql.generate_sql_from_nl("show salaries", _schema())
    assert isinstance(result, NLSQLResult)
    assert result.sql.lower().startswith("select")
    assert "employee pay" in (result.explanation or "").lower()
    assert result.confidence.level == "High"


def test_non_select_generation_declines_gracefully(monkeypatch):
    # A non-SELECT generation (even fenced) is never returned as runnable SQL. For
    # consistency it surfaces as the same graceful not-answerable notice rather than
    # a technical error (BUG-012); the SELECT-only chokepoint at /execute is the hard
    # safety boundary regardless.
    _patch_provider(monkeypatch, "```sql\nDELETE FROM emp\n```\nExplanation: nope.")
    result = nl2sql.generate_sql_from_nl("delete everything", _schema())
    assert result.answerable is False
    assert result.sql == ""


def test_off_topic_returns_not_answerable(monkeypatch):
    # The model declines a non-data question with the sentinel → no SQL, no run.
    _patch_provider(monkeypatch, "CANNOT_ANSWER: I can only answer questions about your database.")
    result = nl2sql.generate_sql_from_nl("how to swim", _schema())
    assert result.answerable is False
    assert result.sql == ""
    assert "database" in (result.message or "").lower()
    assert result.confidence is None


def test_system_prompt_forbids_proxy_for_missing_columns():
    # The guard must also cover data-shaped questions needing a column the schema
    # lacks (e.g. 'women' with no gender column) — decline, never fabricate a proxy.
    p = nl2sql.SYSTEM_PROMPT.lower()
    assert nl2sql.CANNOT_ANSWER_PREFIX.lower() in p
    assert "proxy" in p
    assert "gender" in p  # the canonical missing-attribute example


def test_prose_refusal_without_sentinel_declines(monkeypatch):
    # The model declines in plain prose (no CANNOT_ANSWER sentinel, no SQL fence) —
    # must surface as a graceful not-answerable notice, NOT the technical
    # "Generated SQL is not a SELECT/CTE" safety error (consistency, BUG-012).
    _patch_provider(monkeypatch, "There is no column in the provided schema to determine the gender of an employee.")
    result = nl2sql.generate_sql_from_nl("count of women", _schema())
    assert result.answerable is False
    assert result.sql == ""
    assert "gender" in (result.message or "").lower()


def test_unfenced_non_select_declines_without_proposing_sql(monkeypatch):
    # An unfenced SQL-shaped non-SELECT (e.g. attempted DML) is never proposed as
    # runnable SQL — it declines gracefully (logged server-side), no raise.
    _patch_provider(monkeypatch, "DELETE FROM emp WHERE 1=1")
    result = nl2sql.generate_sql_from_nl("remove everyone", _schema())
    assert result.answerable is False
    assert result.sql == ""


def test_off_topic_sentinel_ignored_when_sql_present(monkeypatch):
    # Conservative: if the model returns BOTH a SQL fence and the sentinel, prefer
    # the SQL so a real question is never blocked.
    _patch_provider(monkeypatch, "```sql\nSELECT emp_id FROM emp\n```\nCANNOT_ANSWER: maybe")
    result = nl2sql.generate_sql_from_nl("show emp ids", _schema())
    assert result.answerable is True
    assert result.sql.lower().startswith("select")


def test_graceful_when_no_provider(monkeypatch):
    def boom(cfg=None, policy=None):
        raise LLMError("no provider configured")

    monkeypatch.setattr(nl2sql, "select_provider", boom)
    with pytest.raises(LLMError):
        nl2sql.generate_sql_from_nl("anything", _schema())


def test_requires_non_empty_schema():
    with pytest.raises(ValueError):
        nl2sql.generate_sql_from_nl("anything", Schema())


def test_provider_failure_returns_clean_message(monkeypatch):
    """F2 — a failing provider call must not leak RetryError/internal repr or the key."""
    _patch_provider(monkeypatch, "ignored")

    def boom(provider, system, user, model):
        raise RuntimeError("401 Unauthorized sk-leak-123")

    monkeypatch.setattr(nl2sql, "_complete_with_retry", boom)
    with pytest.raises(LLMError) as ei:
        nl2sql.generate_sql_from_nl("show salaries", _schema())
    msg = str(ei.value)
    assert "RetryError" not in msg
    assert "sk-leak-123" not in msg
    assert "RuntimeError" in msg  # the exception *type* is acceptable signal


# --------------------------------------------------------------------------- #
# Phase 7 (B2) — opt-in EBS metadata packs in the external context
# --------------------------------------------------------------------------- #
class CapturingProvider:
    def __init__(self, text: str, name: str = "external"):
        self._text = text
        self.name = name
        self.last_user = None

    def is_available(self) -> bool:
        return True

    def resolve_model(self, requested=None) -> str:
        return "fake-model"

    def complete(self, system, user, model=None) -> str:
        self.last_user = user
        return self._text


def _patch_capturing(monkeypatch, prov):
    monkeypatch.setattr(nl2sql, "select_provider", lambda cfg=None, policy=None: prov)


def test_ebs_modules_append_glossary_to_external_prompt(monkeypatch):
    prov = CapturingProvider("```sql\nSELECT invoice_id FROM ap_invoices_all\n```\nExplanation: invoices.")
    _patch_capturing(monkeypatch, prov)
    nl2sql.generate_sql_from_nl("list invoices", _schema(), ebs_modules=["AP"])
    assert "EBS Metadata" in prov.last_user
    assert "invoice -> AP_INVOICES_ALL" in prov.last_user  # glossary reached the prompt
    assert "AP_PAYMENT_SCHEDULES_ALL" in prov.last_user     # table notes too


def test_no_ebs_modules_leaves_external_prompt_unchanged(monkeypatch):
    prov = CapturingProvider("```sql\nSELECT emp_id FROM emp\n```")
    _patch_capturing(monkeypatch, prov)
    nl2sql.generate_sql_from_nl("show emp", _schema())
    assert "EBS Metadata" not in prov.last_user  # opt-in default: no pack context
    assert "EMP" in prov.last_user                # schema-name context unchanged


def test_local_provider_ignores_ebs_modules(monkeypatch):
    prov = CapturingProvider("```sql\nSELECT emp_id FROM emp\n```", name="local")
    _patch_capturing(monkeypatch, prov)
    nl2sql.generate_sql_from_nl("show emp", _schema(), ebs_modules=["AP", "GL"])
    assert "EBS Metadata" not in prov.last_user  # local path = schema markdown only
