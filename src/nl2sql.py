from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp

logger = logging.getLogger("ask_oracle")

from tenacity import retry, stop_after_attempt, wait_exponential

from .schema import Schema
# Single source of truth for SQL safety (see src/core/sql_safety.py).
from .core.sql_safety import is_safe_select as sql_is_safe_select
# Provider abstraction (Phase 3).
from .core.llm.base import LLMConfig, LLMError, LLMProvider, NLSQLResult
from .core.llm.providers import DEFAULT_GROQ_MODEL, DEFAULT_OPENAI_MODEL, GROQ_BASE_URL
from .core.llm.policy import select_provider
from .core.llm.redaction import assert_no_values, build_external_context
from .core.llm.confidence import assess_confidence
from .core.llm.pii import pii_scrub_enabled, scrub_pii
# Curated EBS metadata packs (Phase 7) — opt-in, metadata-only context.
from .core.ebs_packs import build_ebs_context

# Backward-compatible public surface.
__all__ = [
    "LLMConfig",
    "LLMError",
    "NLSQLResult",
    "generate_sql_from_nl",
    "GROQ_BASE_URL",
    "DEFAULT_GROQ_MODEL",
    "DEFAULT_OPENAI_MODEL",
]

# Sentinel the model emits (instead of SQL) when a request isn't a data question
# answerable from the schema. Parsed back into a non-answerable NLSQLResult.
CANNOT_ANSWER_PREFIX = "CANNOT_ANSWER:"

_RULE_ORACLE = (
    "1. A single Oracle SELECT (or WITH … SELECT) query inside a ```sql code fence — "
    "named columns (no SELECT *), explicit JOINs using the given relationships, and Oracle "
    "date functions (TRUNC, ADD_MONTHS, SYSDATE) where needed. For row limits / top-N use "
    "FETCH FIRST n ROWS ONLY or ROWNUM — never LIMIT (Oracle has no LIMIT). Do not end the "
    "statement with a semicolon.\n"
)

_RULE_POSTGRES = (
    "1. A single PostgreSQL SELECT (or WITH … SELECT) query inside a ```sql code fence — "
    "named columns (no SELECT *), explicit JOINs using the given relationships, and standard "
    "PostgreSQL functions (date_trunc, CURRENT_DATE, NOW(), interval) where needed. For row "
    "limits / top-N use LIMIT n. Use the lower-case identifiers exactly as given in the schema. "
    "Do not end the statement with a semicolon.\n"
)

_PROMPT_TAIL = (
    "2. Then a line beginning with 'Interpreted question:' that restates the user's request "
    "as you understood it — correct obvious typos, resolve ambiguity, phrase it as a single "
    "clear question, and make it faithfully describe what your SQL actually returns (so the "
    "reader can tell whether it matches their intent). Do not include any data values.\n"
    "3. Then a line beginning with 'Explanation:' and at most 3 sentences explaining the "
    "query, referring only to the provided schema. Do not include any data values.\n\n"
    "IMPORTANT — scope & honesty. Use ONLY tables and columns that appear in the provided "
    "schema; never invent a column or fabricate a proxy/approximation for a concept the "
    "schema does not contain. Respond with a single line and nothing else —\n"
    f"{CANNOT_ANSWER_PREFIX} <one short sentence explaining you can only answer questions "
    "about the available data>\n"
    "— in EITHER of these cases:\n"
    "(a) the request is not about this data at all (small talk / general knowledge, e.g. "
    "'how to swim'); or\n"
    "(b) answering it would require information the schema does not contain — e.g. counting "
    "employees by gender (men OR women) when there is no gender column, filtering by a hire "
    "date / age / status / category that is not a column, or any attribute absent from the "
    "schema. In that case do NOT substitute a different metric, do NOT invent a column, and "
    "do NOT silently drop the unsatisfiable filter and return a broader count (e.g. a plain "
    "COUNT(*) for 'how many women') — decline.\n"
    "Otherwise, if the question maps to tables and columns that actually exist, attempt the SQL."
)


def _head(engine: str) -> str:
    return f"You are an expert {engine} SQL generator. Using ONLY the provided schema, respond with:\n"


# Oracle stays the default and keeps the name `SYSTEM_PROMPT` (back-compat).
SYSTEM_PROMPT = _head("Oracle") + _RULE_ORACLE + _PROMPT_TAIL
SYSTEM_PROMPT_POSTGRES = _head("PostgreSQL") + _RULE_POSTGRES + _PROMPT_TAIL


def system_prompt_for(dialect: str) -> str:
    return SYSTEM_PROMPT_POSTGRES if dialect == "postgres" else SYSTEM_PROMPT


def _parse_sql_and_explanation(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Split the model output into (sql, explanation, interpreted_question).
    Robust to any of the labelled lines or the code fence being absent."""
    text = (text or "").strip()
    interpreted: Optional[str] = None
    explanation: Optional[str] = None

    # Single-line restatement of the request (typo-corrected / disambiguated).
    m_i = re.search(r"(?im)^\s*interpreted\s*question\s*:\s*(.+?)\s*$", text)
    if m_i:
        interpreted = m_i.group(1).strip() or None

    m = re.search(r"(?ims)^\s*explanation\s*:\s*(.+)$", text)
    if m:
        explanation = m.group(1).strip() or None

    # SQL always comes from the fenced block; fall back to the text with the
    # labelled lines stripped when there is no fence.
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        sql = fence.group(1).strip()
    else:
        sql_part = text[: m.start()] if m else text
        sql_part = re.sub(r"(?im)^\s*interpreted\s*question\s*:.*$", "", sql_part).strip()
        sql = sql_part
        if sql.startswith("```"):
            sql = re.sub(r"^```[a-zA-Z]*\n|```$", "", sql, flags=re.MULTILINE).strip()
    # Strip a trailing statement terminator: python-oracledb rejects a single
    # statement ending in ';' (ORA-00933), and models routinely append one.
    sql = re.sub(r"[;\s]+\Z", "", sql)
    return sql, explanation, interpreted


# reraise=True so a persistent failure surfaces the underlying exception rather
# than tenacity's RetryError wrapper (F2).
@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3), reraise=True)
def _complete_with_retry(provider: LLMProvider, system: str, user: str, model: Optional[str]) -> str:
    return provider.complete(system, user, model)


_DEFAULT_DECLINE_MSG = "I can only answer questions about the available data."

# A model reply is treated as an attempted SQL statement (so a non-SELECT aborts
# for safety) when it begins with a SQL keyword. Anything else with no code fence
# is prose — the model declined/answered in words — and is surfaced as a graceful
# "can't answer" notice instead of the technical safety error (consistency).
_SQL_START_RE = re.compile(
    r"(?is)^\s*(?:with|select|insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|begin|declare)\b"
)


def _looks_like_sql(text: str) -> bool:
    return bool(_SQL_START_RE.match(text or ""))


def _decline_message(text: str) -> str:
    """A short, user-facing reason from the model's prose/sentinel; generic if empty."""
    msg = re.sub(r"\s+", " ", (text or "").strip())
    msg = re.sub(r"(?i)^cannot_answer\s*:?\s*", "", msg).strip()
    return msg[:240] if msg else _DEFAULT_DECLINE_MSG


# Oracle pseudo-columns / built-ins that are valid references but never appear in a
# data dictionary — never treat these as "fabricated".
_PSEUDO_COLUMNS = {
    "ROWNUM", "ROWID", "LEVEL", "ORA_ROWSCN", "SYSDATE", "SYSTIMESTAMP",
    "CURRENT_DATE", "CURRENT_TIMESTAMP", "USER", "UID",
}


def _unknown_columns(sql: str, schema: Schema, dialect: str = "oracle") -> List[str]:
    """Column names the SQL references that are NOT in the schema, NOT query-defined
    (SELECT aliases / CTE names / table aliases), and NOT Oracle pseudo-columns.

    Used to decline a query that referenced a **fabricated** column (e.g. HIRE_DATE
    when the schema has no such column) GRACEFULLY, instead of running it and
    surfacing a raw ORA-00904. **Fail-open:** any parse difficulty, or an unknown
    schema, returns ``[]`` so a valid query is never wrongly blocked (the SELECT-only
    chokepoint remains the hard safety boundary regardless)."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:  # noqa: BLE001 - unparseable → don't block
        return []
    if tree is None:
        return []
    known = {c.column_name.upper() for t in schema.tables.values() for c in t.columns}
    if not known:
        return []  # we don't know the schema's columns → cannot judge

    defined: set = set()
    for node in tree.find_all(exp.Alias):
        if node.alias:
            defined.add(node.alias.upper())
    for cte in tree.find_all(exp.CTE):
        if cte.alias:
            defined.add(cte.alias.upper())
    for tbl in tree.find_all(exp.Table):
        if tbl.alias:
            defined.add(tbl.alias.upper())

    unknown: List[str] = []
    for col in tree.find_all(exp.Column):
        name = (col.name or "").upper()
        if not name or name == "*":
            continue
        if name in known or name in defined or name in _PSEUDO_COLUMNS:
            continue
        unknown.append(col.name)
    return sorted(set(unknown))


def generate_sql_from_nl(
    natural_language: str,
    schema: Schema,
    model: Optional[str] = None,
    llm: Optional[LLMConfig] = None,
    policy: Optional[str] = None,
    ebs_modules: Optional[List[str]] = None,
    dialect: str = "oracle",
) -> NLSQLResult:
    """Propose Oracle SQL (+ explanation + heuristic confidence) for a question.

    The provider is chosen by the LLM policy ([local_only|local_external|
    external_disabled]) and the optional per-user ``llm`` config. External prompts
    carry schema names only (strict redaction). ``ebs_modules`` (Phase 7, opt-in)
    appends curated EBS **metadata** (table/column descriptions + glossary, no row
    data) for the selected modules to the external context — covered by the same
    ``assert_no_values`` tripwire. The result is always verified to be a safe
    SELECT/CTE before return; it is never executed here.
    """
    if not natural_language or not natural_language.strip():
        raise ValueError("Empty natural language input.")
    if schema is None or not schema.tables:
        raise ValueError("Schema is empty; upload schema metadata first.")

    provider = select_provider(llm, policy)  # raises LLMError (clean) if unavailable/disabled

    question = natural_language.strip()
    if provider.name == "local":
        context = schema.to_compact_markdown()
    else:
        context = build_external_context(schema)
        # Opt-in EBS metadata (Phase 7) — names/descriptions only; appended before
        # the tripwire so the combined external context is verified as a whole.
        ebs_context = build_ebs_context(ebs_modules or [])
        if ebs_context:
            context = context + "\n\n" + ebs_context
        assert_no_values(context)  # defense-in-depth before any external send
        # Optional, opt-in PII scrubbing of the question on the external path
        # only (ITM-008, default off). Local generation stays verbatim.
        if pii_scrub_enabled():
            question, _ = scrub_pii(question)

    user = (
        "Schema:\n" + context + "\n\n"
        "User request:\n" + question + "\n\n"
        "Return the Oracle SQL in a ```sql fence, then an 'Interpreted question:' line, "
        "then an 'Explanation:' line."
    )

    try:
        raw = _complete_with_retry(provider, system_prompt_for(dialect), user, model)
    except LLMError:
        raise  # already a clean, user-safe message
    except Exception as exc:  # noqa: BLE001 — provider/network/auth failure
        # Map to a clean message; never surface RetryError/internal reprs or the key (F2).
        raise LLMError(
            f"LLM request failed ({type(exc).__name__}). Check the API key, model, and provider settings."
        ) from exc

    # Off-topic guard (conservative): the model emits the CANNOT_ANSWER sentinel
    # for a request that isn't answerable from the schema. Only treat it as a
    # refusal when there's no SQL fence — if it somehow returned both, prefer the
    # SQL so a real question is never blocked.
    has_fence = re.search(r"```(?:sql)?\s", raw, re.IGNORECASE) is not None
    refusal = re.search(r"(?im)^\s*CANNOT_ANSWER\s*:\s*(.*)$", raw)
    if refusal and not has_fence:
        return NLSQLResult(sql="", answerable=False, message=_decline_message(refusal.group(1)))

    sql, explanation, interpreted = _parse_sql_and_explanation(raw)
    if not sql_is_safe_select(sql, dialect=dialect):
        # The model didn't return a usable read-only query — whether an explicit
        # decline (sentinel/prose), or non-SELECT / unparseable output. Always surface
        # the SAME graceful not-answerable notice (the owner's consistency
        # requirement) rather than a technical "not a SELECT" error: nothing is
        # proposed or run, and the SELECT-only chokepoint at /execute stays the hard
        # safety boundary regardless. The rejected output is logged server-side so the
        # signal isn't lost. Prose carries a useful reason; a SQL-shaped non-SELECT
        # (e.g. the model attempted DML) gets a generic message.
        logger.warning("nl2sql: no usable SELECT produced; declining (preview=%r)", (sql or "")[:120])
        message = _decline_message("" if _looks_like_sql(sql) else sql)
        return NLSQLResult(sql="", answerable=False, message=message)

    # Decline gracefully when the model fabricated a column that isn't in the schema
    # (F2): far better a calm "the data has no column for X" than a raw ORA-00904 at
    # run time. Fail-open — only fires on a confident, parseable unknown reference.
    unknown = _unknown_columns(sql, schema, dialect)
    if unknown:
        logger.info("nl2sql: SQL references column(s) not in schema %s; declining", unknown)
        cols_txt = ", ".join(unknown[:5])
        return NLSQLResult(
            sql="",
            answerable=False,
            message=f"I can't answer that from the available data — it has no column for: {cols_txt}.",
        )

    return NLSQLResult(
        sql=sql,
        explanation=explanation,
        interpreted_question=interpreted,
        confidence=assess_confidence(sql, schema),
    )
