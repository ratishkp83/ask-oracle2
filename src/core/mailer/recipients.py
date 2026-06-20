"""Smart quick-pick: surface email-like values found in a result set (Phase 8, D-D).

So "whom to contact" can be one click from the report output, we scan the result
for email addresses using the same conservative pattern as the PII detector in
:mod:`src.core.llm.pii`. Pure in-memory, no I/O, no LLM.
"""

from __future__ import annotations

import re
from typing import List

import pandas as pd

# Same shape as the email detector in core/llm/pii.py.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def detect_recipient_candidates(df: pd.DataFrame, *, limit: int = 50) -> List[str]:
    """Email addresses found anywhere in ``df``.

    Deduped case-insensitively, returned in first-seen order, capped at ``limit``.
    Non-string / NaN cells are ignored.
    """
    out: List[str] = []
    seen = set()
    if df is None or df.empty:
        return out
    # Scan column by column so each column's contacts stay grouped together.
    for col in df.columns:
        for value in df[col].tolist():
            if not isinstance(value, str):
                continue
            for match in _EMAIL_RE.findall(value):
                key = match.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(match)
                    if len(out) >= limit:
                        return out
    return out
