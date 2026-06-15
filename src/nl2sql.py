from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

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

SYSTEM_PROMPT = (
    "You are an expert Oracle SQL generator. Using ONLY the provided schema, respond with:\n"
    "1. A single Oracle SELECT (or WITH … SELECT) query inside a ```sql code fence — "
    "named columns (no SELECT *), explicit JOINs using the given relationships, and Oracle "
    "date functions (TRUNC, ADD_MONTHS, SYSDATE) where needed. For row limits / top-N use "
    "FETCH FIRST n ROWS ONLY or ROWNUM — never LIMIT (Oracle has no LIMIT). Do not end the "
    "statement with a semicolon.\n"
    "2. Then a line beginning with 'Explanation:' and at most 3 sentences explaining the "
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
    "'women' when there is no gender column, or filtering by an age/status/category that is "
    "not a column. In that case do NOT substitute a different metric or guess a proxy; "
    "decline.\n"
    "Otherwise, if the question maps to tables and columns that actually exist, attempt the SQL."
)


def _parse_sql_and_explanation(text: str) -> Tuple[str, Optional[str]]:
    """Split the model output into (sql, explanation). Robust to a missing
    explanation block or missing code fence."""
    text = (text or "").strip()
    explanation: Optional[str] = None

    m = re.search(r"(?ims)^\s*explanation\s*:\s*(.+)$", text)
    sql_part = text
    if m:
        explanation = m.group(1).strip() or None
        sql_part = text[: m.start()].strip()

    fence = re.search(r"```(?:sql)?\s*(.*?)```", sql_part, re.DOTALL | re.IGNORECASE)
    if fence:
        sql = fence.group(1).strip()
    else:
        sql = sql_part.strip()
        if sql.startswith("```"):
            sql = re.sub(r"^```[a-zA-Z]*\n|```$", "", sql, flags=re.MULTILINE).strip()
    # Strip a trailing statement terminator: python-oracledb rejects a single
    # statement ending in ';' (ORA-00933), and models routinely append one.
    sql = re.sub(r"[;\s]+\Z", "", sql)
    return sql, explanation


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


def generate_sql_from_nl(
    natural_language: str,
    schema: Schema,
    model: Optional[str] = None,
    llm: Optional[LLMConfig] = None,
    policy: Optional[str] = None,
    ebs_modules: Optional[List[str]] = None,
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
        "Return the Oracle SQL in a ```sql fence, then an 'Explanation:' line."
    )

    try:
        raw = _complete_with_retry(provider, SYSTEM_PROMPT, user, model)
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

    sql, explanation = _parse_sql_and_explanation(raw)
    if not sql_is_safe_select(sql):
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

    return NLSQLResult(sql=sql, explanation=explanation, confidence=assess_confidence(sql, schema))
