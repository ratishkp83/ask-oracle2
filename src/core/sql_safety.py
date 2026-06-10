"""Central SQL safety layer.

Every SQL string that reaches an Oracle connection MUST pass through
:func:`assert_safe_select` first. The policy is layered (defense in depth):

1. Parse with sqlglot using the Oracle dialect. Parsing must succeed and yield
   exactly one statement (no stacked/`;`-separated statements).
2. The root statement must be a read-only construct: SELECT, UNION/INTERSECT/
   MINUS, or a parenthesised SELECT. `WITH ... SELECT` (CTE) is allowed because
   sqlglot models it as a SELECT carrying a `with` clause.
3. The AST must contain no DML/DDL/PL-SQL nodes anywhere (INSERT, UPDATE,
   DELETE, MERGE, CREATE, DROP, ALTER, or unparsed `Command` nodes), and no
   row-locking clause (`FOR UPDATE`).
4. A whole-word keyword denylist is applied as a backstop over the normalised,
   comment- and literal-stripped SQL.

The layer is intentionally **fail-closed**: anything we cannot confidently prove
to be a read-only SELECT is rejected. This can occasionally reject exotic-but-
valid Oracle SQL; for a safety-first product that trade-off is deliberate.
"""

from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import exp
from pydantic import BaseModel

# Expression types that must never appear anywhere in an accepted statement.
_FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,  # sqlglot's catch-all for statements it cannot fully parse
)

# Root statement types that represent a read-only result set.
_ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)

# Backstop denylist (whole-word, case-insensitive). Mirrors the spec's forbidden
# tokens plus common PL/SQL and transaction-control keywords.
_DENYLIST_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "DROP", "ALTER",
    "CREATE", "GRANT", "REVOKE", "RENAME", "COMMENT", "FLASHBACK", "PURGE",
    "LOCK", "BEGIN", "DECLARE", "CALL", "EXECUTE", "EXEC", "COMMIT",
    "ROLLBACK", "SAVEPOINT",
)
_DENYLIST_RE = re.compile(
    r"\b(" + "|".join(_DENYLIST_KEYWORDS) + r")\b", re.IGNORECASE
)
# Matches single-quoted string literals (including '' escaped quotes) so we can
# blank them out before keyword scanning (avoids false positives on data like
# WHERE status = 'DELETE').
_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")


class SqlSafetyError(ValueError):
    """Raised when SQL fails the safety policy."""


class SafetyResult(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    normalized_sql: Optional[str] = None


def _strip_trailing_semicolons(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def assert_safe_select(sql: str) -> SafetyResult:
    """Return a :class:`SafetyResult` describing whether ``sql`` is a safe SELECT.

    Never raises for unsafe input; callers inspect ``result.allowed`` and may
    raise :class:`SqlSafetyError` themselves. Only programming errors propagate.
    """
    if not sql or not sql.strip():
        return SafetyResult(allowed=False, reason="Empty SQL is not allowed.")

    cleaned = _strip_trailing_semicolons(sql)
    if not cleaned:
        return SafetyResult(allowed=False, reason="Empty SQL is not allowed.")

    # Layer 1: parse with the Oracle dialect; reject stacked statements.
    try:
        parsed = [s for s in sqlglot.parse(cleaned, read="oracle") if s is not None]
    except Exception as exc:  # noqa: BLE001 - any parse failure is fail-closed
        return SafetyResult(
            allowed=False,
            reason=f"Could not parse SQL safely; only single SELECT/CTE statements are allowed ({exc}).",
        )

    if len(parsed) == 0:
        return SafetyResult(allowed=False, reason="No executable statement found.")
    if len(parsed) > 1:
        return SafetyResult(
            allowed=False,
            reason="Multiple statements are not allowed; submit a single SELECT/CTE query.",
        )

    statement = parsed[0]

    # Unwrap a leading parenthesised/sub-query wrapper: (SELECT ...).
    root = statement
    while isinstance(root, (exp.Subquery, exp.Paren)) and root.this is not None:
        root = root.this

    # Layer 2: the root must be a read-only construct.
    if not isinstance(root, _ALLOWED_ROOTS):
        kind = type(root).__name__.upper()
        return SafetyResult(
            allowed=False,
            reason=f"Only SELECT/CTE queries are allowed; received a {kind} statement.",
        )

    # Layer 3a: no DML/DDL/PL-SQL nodes anywhere in the tree.
    forbidden = next(statement.find_all(*_FORBIDDEN_NODES), None)
    if forbidden is not None:
        kind = type(forbidden).__name__.upper()
        return SafetyResult(
            allowed=False,
            reason=f"Forbidden operation detected in query: {kind}.",
        )

    # Layer 3b: reject row-locking (FOR UPDATE) which is not read-only.
    if isinstance(root, exp.Select) and root.args.get("locks"):
        return SafetyResult(
            allowed=False,
            reason="Row-locking clauses (e.g. FOR UPDATE) are not allowed.",
        )

    # Layer 4: keyword denylist backstop over normalised, literal-stripped SQL.
    try:
        normalized = statement.sql(dialect="oracle")
    except Exception:  # noqa: BLE001 - fall back to the cleaned input
        normalized = cleaned
    scannable = _STRING_LITERAL_RE.sub("''", normalized)
    match = _DENYLIST_RE.search(scannable)
    if match is not None:
        return SafetyResult(
            allowed=False,
            reason=f"Forbidden keyword detected in query: {match.group(1).upper()}.",
        )

    return SafetyResult(allowed=True, normalized_sql=normalized)


def is_safe_select(sql: str) -> bool:
    """Backwards-compatible boolean wrapper around :func:`assert_safe_select`."""
    return assert_safe_select(sql).allowed
