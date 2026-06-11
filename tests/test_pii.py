"""ITM-008 — optional NL-question PII scrubbing (default-off, external path only)."""

import pytest

from src import nl2sql
from src.core.llm.pii import pii_scrub_enabled, scrub_pii
from src.schema import ColumnDefinition, Schema, TableDefinition


# --------------------------------------------------------------------------- #
# Unit — patterns + flag
# --------------------------------------------------------------------------- #
def test_scrub_masks_common_pii():
    text = "email john.doe@example.com phone 555-123-4567 ssn 123-45-6789 card 4111 1111 1111 1111"
    out, n = scrub_pii(text)
    assert "john.doe@example.com" not in out and "[EMAIL]" in out
    assert "555-123-4567" not in out and "[PHONE]" in out
    assert "123-45-6789" not in out and "[SSN]" in out
    assert "4111 1111 1111 1111" not in out and "[CARD]" in out
    assert n >= 4


def test_scrub_leaves_ordinary_numbers_alone():
    # A numeric threshold/quantity is not PII and must survive (or scrubbing
    # would silently degrade the query).
    out, n = scrub_pii("show orders over 100000 in 2026")
    assert out == "show orders over 100000 in 2026"
    assert n == 0


def test_scrub_empty():
    assert scrub_pii("") == ("", 0)


@pytest.mark.parametrize("val,expected", [("1", True), ("true", True), ("ON", True), ("yes", True),
                                          ("0", False), ("false", False), ("", False), ("  ", False)])
def test_flag_parsing(monkeypatch, val, expected):
    monkeypatch.setenv("SCRUB_PII", val)
    assert pii_scrub_enabled() is expected


def test_flag_unset_is_off(monkeypatch):
    monkeypatch.delenv("SCRUB_PII", raising=False)
    assert pii_scrub_enabled() is False


# --------------------------------------------------------------------------- #
# Integration — applied on the external path only, when the flag is on
# --------------------------------------------------------------------------- #
class _Recorder:
    def __init__(self, name: str):
        self.name = name
        self.seen_user = None

    def is_available(self) -> bool:
        return True

    def resolve_model(self, requested=None) -> str:
        return "fake"

    def complete(self, system, user, model=None) -> str:
        self.seen_user = user
        return "```sql\nSELECT emp_id FROM emp\n```\nExplanation: ok."


def _schema() -> Schema:
    s = Schema()
    s.tables["EMP"] = TableDefinition(
        name="EMP", columns=[ColumnDefinition(table_name="EMP", column_name="EMP_ID")]
    )
    return s


def test_external_question_scrubbed_when_flag_on(monkeypatch):
    monkeypatch.setenv("SCRUB_PII", "true")
    rec = _Recorder("external")
    monkeypatch.setattr(nl2sql, "select_provider", lambda cfg=None, policy=None: rec)
    nl2sql.generate_sql_from_nl("email me at john@example.com about emp", _schema())
    assert "john@example.com" not in rec.seen_user
    assert "[EMAIL]" in rec.seen_user


def test_external_question_verbatim_when_flag_off(monkeypatch):
    monkeypatch.delenv("SCRUB_PII", raising=False)
    rec = _Recorder("external")
    monkeypatch.setattr(nl2sql, "select_provider", lambda cfg=None, policy=None: rec)
    nl2sql.generate_sql_from_nl("email me at john@example.com about emp", _schema())
    assert "john@example.com" in rec.seen_user  # opt-in: off by default


def test_local_path_never_scrubbed(monkeypatch):
    # Even with the flag on, the local provider gets the verbatim question
    # (nothing leaves the box, so scrubbing would only hurt quality).
    monkeypatch.setenv("SCRUB_PII", "true")
    rec = _Recorder("local")
    monkeypatch.setattr(nl2sql, "select_provider", lambda cfg=None, policy=None: rec)
    nl2sql.generate_sql_from_nl("email me at john@example.com about emp", _schema())
    assert "john@example.com" in rec.seen_user
