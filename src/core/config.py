from __future__ import annotations

import os

from pydantic import BaseModel, Field

# Conservative defaults suitable for interactive ad-hoc reporting. All three
# can be overridden per-deployment via environment variables.
DEFAULT_MAX_ROWS = 1000
DEFAULT_MAX_EXECUTION_SECONDS = 30.0
DEFAULT_MAX_RESULT_BYTES = 5_000_000  # ~5 MB of (approximate) result payload


class SafetyLimits(BaseModel):
    """Runtime guardrails applied to every query execution.

    These are enforced regardless of how the SQL was produced (raw editor,
    NL->SQL, or a saved report) and regardless of entry point (API or UI).
    """

    max_rows: int = Field(DEFAULT_MAX_ROWS, ge=1)
    max_execution_seconds: float = Field(DEFAULT_MAX_EXECUTION_SECONDS, gt=0)
    max_result_bytes: int = Field(DEFAULT_MAX_RESULT_BYTES, ge=1024)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def load_safety_limits() -> SafetyLimits:
    """Build :class:`SafetyLimits` from the environment, falling back to defaults."""
    return SafetyLimits(
        max_rows=_int_env("MAX_ROWS", DEFAULT_MAX_ROWS),
        max_execution_seconds=_float_env("MAX_EXECUTION_SECONDS", DEFAULT_MAX_EXECUTION_SECONDS),
        max_result_bytes=_int_env("MAX_RESULT_BYTES", DEFAULT_MAX_RESULT_BYTES),
    )
