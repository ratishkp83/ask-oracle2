"""Optional NL-question PII scrubbing before an external LLM send (ITM-008).

**Off by default.** Enabled per-tenant via the ``SCRUB_PII`` env flag. When on,
the user's natural-language question is masked to typed placeholders **only on
the external-provider path** (the local path stays verbatim) — complementing,
not replacing, the strict schema-context redaction in ``redaction.py`` (which
already sends schema **names only**).

The patterns are deliberately **conservative** (structured / long tokens only)
to limit false positives, since masking a value the user genuinely meant can
degrade the generated SQL — which is exactly why this is opt-in. Tune the
patterns here if a tenant needs broader or narrower coverage.
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

SCRUB_ENV = "SCRUB_PII"
_TRUTHY = {"1", "true", "yes", "on"}

# (placeholder, pattern) — applied in order; earlier patterns win on overlap.
_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("[SSN]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Grouped 16-digit card, or any bare 13–16 digit run (cards / long IDs).
    ("[CARD]", re.compile(r"\b(?:\d{4}[-\s]){3}\d{4}\b|\b\d{13,16}\b")),
    # Separator-formatted phone numbers (bare 10-digit runs are left alone to
    # avoid masking ordinary numeric values in a question).
    ("[PHONE]", re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")),
]


def pii_scrub_enabled() -> bool:
    """True only when ``SCRUB_PII`` is set to a truthy value (default off)."""
    return (os.environ.get(SCRUB_ENV) or "").strip().lower() in _TRUTHY


def scrub_pii(text: str) -> Tuple[str, int]:
    """Mask common PII to typed placeholders. Returns ``(scrubbed, n_masked)``."""
    if not text:
        return text, 0
    masked = text
    total = 0
    for placeholder, pattern in _PATTERNS:
        masked, n = pattern.subn(placeholder, masked)
        total += n
    return masked, total
