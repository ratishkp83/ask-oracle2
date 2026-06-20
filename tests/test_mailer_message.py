"""B1 — validation, header-injection guard, allow-list, and message assembly."""

from __future__ import annotations

import pandas as pd
import pytest

from src.core.mailer.message import (
    EmailRejected,
    all_recipients,
    build_message,
    enforce_allowlist,
    normalize_format,
    parse_recipients,
    sanitize_subject,
    validate_address,
)
from src.utils import dataframe_to_csv_bytes

DF = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})


# --- address validation --------------------------------------------------- #
def test_validate_address_ok():
    assert validate_address("  Jane.Doe@Example.com ") == "Jane.Doe@Example.com"


@pytest.mark.parametrize("bad", ["", "   ", "no-at-sign", "missing@dot", "@nope.com", "a@b"])
def test_validate_address_rejects_invalid(bad):
    with pytest.raises(EmailRejected):
        validate_address(bad)


@pytest.mark.parametrize("payload", [
    "a@b.com\r\nBcc: evil@x.com",
    "a@b.com\nSubject: spoof",
    "a@b.com\twho",
])
def test_validate_address_rejects_header_injection(payload):
    with pytest.raises(EmailRejected):
        validate_address(payload)


@pytest.mark.parametrize("ctrl", ["\x01", "\x07", "\x0b", "\x1f", "\x7f"])
def test_validate_address_rejects_all_control_chars(ctrl):
    # P8-R1-F2: an embedded control char (full C0 + DEL class, not only CR/LF/TAB/NUL)
    # is rejected. Embedded — not trailing — so str.strip() can't quietly drop it first.
    with pytest.raises(EmailRejected):
        validate_address(f"a{ctrl}@b.com")


def test_build_message_strips_controls_from_sender():
    # P8-R1-F4: control chars in the operator-set From header are stripped.
    msg = build_message(
        sender="Reports\r\nBcc: evil@x.com <reports@x.com>", to=["a@x.com"], cc=(),
        subject="S", body="", df=DF, attachment_format="csv",
    )
    assert "\r" not in msg["From"] and "\n" not in msg["From"]


# --- recipient parsing ---------------------------------------------------- #
def test_parse_recipients_multi_separator_and_dedupe():
    raw = "a@x.com, b@y.com; a@X.COM  c@z.com"
    assert parse_recipients(raw) == ["a@x.com", "b@y.com", "c@z.com"]


def test_parse_recipients_empty():
    assert parse_recipients("") == []


def test_parse_recipients_propagates_invalid():
    with pytest.raises(EmailRejected):
        parse_recipients("ok@x.com, not-valid")


# --- allow-list ----------------------------------------------------------- #
def test_allowlist_empty_allows_any():
    enforce_allowlist(["a@anywhere.com"], frozenset())  # no raise


def test_allowlist_allows_matching_domain_case_insensitive():
    enforce_allowlist(["a@Corp.IO"], {"corp.io"})  # no raise


def test_allowlist_blocks_outside_domain():
    with pytest.raises(EmailRejected):
        enforce_allowlist(["a@gmail.com"], {"corp.io"})


# --- subject -------------------------------------------------------------- #
def test_sanitize_subject_strips_control_and_caps():
    out = sanitize_subject("Hello\r\nBcc: x@y.com" + " z" * 300)
    assert "\r" not in out and "\n" not in out
    assert len(out) <= 200


# --- format --------------------------------------------------------------- #
@pytest.mark.parametrize("raw,expected", [("csv", "csv"), ("CSV", "csv"),
                                          ("excel", "excel"), ("xlsx", "excel"), ("xls", "excel")])
def test_normalize_format_ok(raw, expected):
    assert normalize_format(raw) == expected


def test_normalize_format_rejects_unknown():
    with pytest.raises(EmailRejected):
        normalize_format("pdf")


# --- message assembly ----------------------------------------------------- #
def test_build_message_csv():
    msg = build_message(
        sender="me@example.com", to=["a@x.com"], cc=["b@y.com"],
        subject="Subject", body="Body text", df=DF, attachment_format="csv",
    )
    assert msg["From"] == "me@example.com"
    assert msg["To"] == "a@x.com"
    assert msg["Cc"] == "b@y.com"
    body = msg.get_body(preferencelist=("plain",))
    assert body is not None and body.get_content().strip() == "Body text"
    atts = list(msg.iter_attachments())
    assert len(atts) == 1
    assert atts[0].get_filename() == "report.csv"
    assert atts[0].get_content_type() == "text/csv"
    assert atts[0].get_payload(decode=True) == dataframe_to_csv_bytes(DF)


def test_build_message_excel():
    msg = build_message(
        sender="me@example.com", to=["a@x.com"], cc=(),
        subject="S", body="", df=DF, attachment_format="xlsx",
    )
    assert msg["Cc"] is None
    atts = list(msg.iter_attachments())
    assert atts[0].get_filename() == "report.xlsx"
    assert atts[0].get_content_type() == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert atts[0].get_payload(decode=True)[:2] == b"PK"  # xlsx is a zip


def test_build_message_custom_filename_gets_extension():
    msg = build_message(
        sender="me@example.com", to=["a@x.com"], cc=(),
        subject="S", body="", df=DF, attachment_format="csv", filename="q4_sales",
    )
    assert list(msg.iter_attachments())[0].get_filename() == "q4_sales.csv"


def test_build_message_requires_recipient():
    with pytest.raises(EmailRejected):
        build_message(sender="me@example.com", to=[], cc=(), subject="S",
                      body="", df=DF, attachment_format="csv")


def test_build_message_rejects_injection_in_recipient():
    with pytest.raises(EmailRejected):
        build_message(sender="me@example.com", to=["a@x.com\r\nBcc: e@v.com"], cc=(),
                      subject="S", body="", df=DF, attachment_format="csv")


def test_build_message_enforces_size_cap():
    big = pd.DataFrame({"v": range(10_000)})
    with pytest.raises(EmailRejected):
        build_message(sender="me@example.com", to=["a@x.com"], cc=(), subject="S",
                      body="", df=big, attachment_format="csv", max_attachment_bytes=100)


def test_all_recipients_flattens_to_and_cc():
    msg = build_message(
        sender="me@example.com", to=["a@x.com", "b@x.com"], cc=["c@y.com"],
        subject="S", body="", df=DF, attachment_format="csv",
    )
    assert all_recipients(msg) == ["a@x.com", "b@x.com", "c@y.com"]
