from __future__ import annotations

import re

from src.schema import Schema


class RedactionError(RuntimeError):
    """Raised when prompt content destined for an external LLM appears to contain data."""


# Defense-in-depth tripwire: section markers that would indicate row/sample data
# was accidentally included in an external prompt. The PRIMARY guarantee is by
# construction — we only ever inject schema NAMES (no values) plus the user's
# question. This guard catches regressions if prompt-building changes later.
_FORBIDDEN_MARKERS = (
    "sample values",
    "sample value:",
    "example values",
    "example data",
    "sample data",
    "row data",
    "data preview",
    "result rows",
)
_FORBIDDEN_RE = re.compile("|".join(re.escape(m) for m in _FORBIDDEN_MARKERS), re.IGNORECASE)


def build_external_context(schema: Schema, max_chars: int = 12000) -> str:
    """Schema context safe to send to an external LLM: table/column/type/FK names
    and relationships only — no row values (Schema carries none)."""
    text = schema.to_compact_markdown()
    if len(text) > max_chars:
        return text[: max_chars - 500] + "\n...\n(truncated schema in prompt)"
    return text


def assert_no_values(schema_context: str) -> None:
    """Raise if the schema context destined for an external LLM looks like it
    contains data values rather than just schema names."""
    match = _FORBIDDEN_RE.search(schema_context)
    if match is not None:
        raise RedactionError(
            f"Refusing to send suspected data to an external LLM (matched '{match.group(0)}'). "
            "External prompts must contain schema names only."
        )
