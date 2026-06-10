"""Secret-free audit logging.

We log *that* a query ran (which profile, which user, how many rows, how long)
and a SHA-256 fingerprint of the SQL — never the raw SQL text and never
credentials. This satisfies the audit requirement in the spec while avoiding
leakage of PII/PHI that may appear in literals or column predicates.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

logger = logging.getLogger("ask_oracle.audit")


def sql_fingerprint(sql: str) -> str:
    """Stable SHA-256 hex digest of the SQL text (full digest)."""
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def audit_execution(
    *,
    source: str,
    sql: str,
    allowed: bool,
    profile_id: Optional[str] = None,
    username: Optional[str] = None,
    row_count: Optional[int] = None,
    elapsed_seconds: Optional[float] = None,
    truncated: Optional[bool] = None,
    reason: Optional[str] = None,
) -> None:
    """Emit one structured audit record for a query attempt.

    ``source`` is e.g. "api" or "ui". ``reason`` is populated for rejected or
    failed attempts. Raw SQL and passwords are deliberately excluded.
    """
    payload = {
        "event": "sql_execute",
        "source": source,
        "profile_id": profile_id,
        "user": username,
        "sql_sha256": sql_fingerprint(sql)[:16],
        "allowed": allowed,
        "row_count": row_count,
        "elapsed_seconds": round(elapsed_seconds, 3) if elapsed_seconds is not None else None,
        "truncated": truncated,
        "reason": reason,
    }
    logger.info("%s", payload)


def audit_profile_usage(profile_id: str, username: Optional[str], action: str) -> None:
    """Record a profile lifecycle/usage event (create, delete, test, connect)."""
    logger.info(
        "%s",
        {"event": "profile_usage", "action": action, "profile_id": profile_id, "user": username},
    )
