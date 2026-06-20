"""B1 — smart quick-pick recipient detection from a result set."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.core.mailer.recipients import detect_recipient_candidates


def test_detects_across_columns():
    df = pd.DataFrame({
        "owner": ["alice@corp.io", "bob@corp.io"],
        "note": ["ping carol@vendor.com", "n/a"],
    })
    found = detect_recipient_candidates(df)
    assert found == ["alice@corp.io", "bob@corp.io", "carol@vendor.com"]


def test_dedupes_case_insensitively():
    df = pd.DataFrame({"email": ["Sam@X.com", "sam@x.com", "SAM@X.COM"]})
    assert detect_recipient_candidates(df) == ["Sam@X.com"]


def test_respects_limit():
    df = pd.DataFrame({"email": [f"user{i}@x.com" for i in range(10)]})
    assert len(detect_recipient_candidates(df, limit=3)) == 3


def test_ignores_non_string_and_nan():
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "amount": [10.5, np.nan, 7.0],
        "email": ["a@b.com", None, "c@d.com"],
    })
    assert detect_recipient_candidates(df) == ["a@b.com", "c@d.com"]


def test_empty_df_returns_empty():
    assert detect_recipient_candidates(pd.DataFrame()) == []


def test_no_emails_returns_empty():
    df = pd.DataFrame({"x": ["nothing", "here"], "y": [1, 2]})
    assert detect_recipient_candidates(df) == []
