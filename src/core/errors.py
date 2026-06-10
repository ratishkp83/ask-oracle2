"""Uniform error sanitization + correlation — shared by the API and the UI.

The single rule (ITM-015): a **raw driver/connection exception must never reach
the client**. It is logged server-side in full, keyed by an ``error_id``, and the
caller receives only a generic message plus that id. Intentional, safe messages
(validation ``ValueError``, the safety layer's rejection ``reason``, "not
found"/"duplicate") are deliberately **not** routed through here — they stay
verbatim because they are user-actionable and carry no infrastructure detail.

This module is framework-agnostic (no FastAPI import) so both ``src/api.py`` and
the Streamlit ``src/app.py`` — which call the chokepoint directly, bypassing
HTTP — can share one sanitization rule. The API wraps these into an
``HTTPException`` itself.

Server-side log records carry ``str(exc)`` and the exception type only — never a
password, bind value, or raw SQL.
"""

from __future__ import annotations

import logging
from typing import Tuple
from uuid import uuid4

from src.core.logging_config import get_logger

GENERIC_DB_DETAIL = "Database error — see server logs."
GENERIC_SERVER_DETAIL = "Internal server error."

logger = get_logger("errors")


def new_error_id() -> str:
    """A fresh correlation id (used when there is no request scope, e.g. the UI)."""
    return uuid4().hex


def log_error(
    exc: BaseException,
    *,
    context: str,
    error_id: str,
    event: str = "error",
    level: int = logging.ERROR,
) -> None:
    """Emit one server-side error record keyed by ``error_id``.

    Records ``str(exc)`` and the exception type only — secret-free by policy.
    """
    logger.log(
        level,
        event,
        extra={
            "extra_fields": {
                "event": event,
                "error_id": error_id,
                "context": context,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        },
    )


def sanitize_db_error_for_ui(exc: BaseException, *, context: str) -> Tuple[str, str]:
    """UI path: log the driver error server-side, return ``(error_id, message)``.

    The caller displays e.g. ``f"{message} (ref: {error_id})"``.
    """
    error_id = new_error_id()
    log_error(exc, context=context, error_id=error_id, event="db_error")
    return error_id, GENERIC_DB_DETAIL
