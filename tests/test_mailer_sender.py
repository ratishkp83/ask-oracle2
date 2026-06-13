"""B2 — SMTP send orchestration (transport fully mocked, no network)."""

from __future__ import annotations

import smtplib
from unittest.mock import patch

import pandas as pd
import pytest

from src.core import metrics
from src.core.errors import GENERIC_EMAIL_DETAIL
from src.core.mailer.config import EmailConfig
from src.core.mailer.sender import SendResult, send_report_email

DF = pd.DataFrame({"id": [1, 2], "owner": ["a@corp.io", "b@corp.io"]})
_SECRET = "SUPER-SECRET-APP-PW"


def _cfg(**over) -> EmailConfig:
    base = dict(
        host="smtp.gmail.com", port=587, user="me@example.com", password=_SECRET,
        sender="me@example.com", allowed_domains=frozenset(),
        max_attachment_bytes=20 * 1024 * 1024,
    )
    base.update(over)
    return EmailConfig(**base)


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


# --- success -------------------------------------------------------------- #
def test_send_success_starttls_path():
    with patch("smtplib.SMTP") as mock_smtp, patch("src.core.mailer.sender._audit") as audit:
        result = send_report_email(to="x@corp.io, y@corp.io", cc="z@corp.io",
                                   subject="Q4", body="see attached", df=DF,
                                   attachment_format="csv", config=_cfg())
    server = mock_smtp.return_value.__enter__.return_value
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("me@example.com", _SECRET)
    assert server.send_message.call_count == 1
    # explicit envelope carries To + Cc
    _, kwargs = server.send_message.call_args
    assert sorted(kwargs["to_addrs"]) == ["x@corp.io", "y@corp.io", "z@corp.io"]

    assert isinstance(result, SendResult) and result.ok
    assert result.recipients == 3
    assert metrics.snapshot()["counters"]["emails_sent"] == 1

    # audit emitted, metadata only, secret-free
    audit.info.assert_called_once()
    logged = repr(audit.info.call_args)
    assert _SECRET not in logged
    assert "email_sent" in logged and "see attached" not in logged  # no body


def test_send_uses_ssl_on_465():
    with patch("smtplib.SMTP_SSL") as mock_ssl, patch("smtplib.SMTP") as mock_plain, \
            patch("src.core.mailer.sender._audit"):
        result = send_report_email(to="x@corp.io", subject="S", body="", df=DF,
                                   attachment_format="excel", config=_cfg(port=465))
    assert result.ok
    mock_ssl.return_value.__enter__.return_value.login.assert_called_once()
    mock_plain.assert_not_called()  # did not use the STARTTLS path


# --- transport failure ---------------------------------------------------- #
def test_send_transport_failure_is_sanitized():
    with patch("smtplib.SMTP") as mock_smtp, patch("src.core.mailer.sender._audit") as audit:
        server = mock_smtp.return_value.__enter__.return_value
        server.send_message.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 bad creds")
        result = send_report_email(to="x@corp.io", subject="S", body="", df=DF,
                                   attachment_format="csv", config=_cfg())
    assert result.kind == "error"
    assert result.error_id
    assert result.message == GENERIC_EMAIL_DETAIL
    assert "5.7.8" not in result.message and _SECRET not in result.message
    assert metrics.snapshot()["counters"]["emails_failed"] == 1
    # failure audited as a warning, still secret-free
    audit.warning.assert_called_once()
    assert _SECRET not in repr(audit.warning.call_args)


# --- rejections (no SMTP call) ------------------------------------------- #
def test_reject_bad_recipient_skips_smtp():
    with patch("smtplib.SMTP") as mock_smtp:
        result = send_report_email(to="not-an-email", subject="S", body="", df=DF,
                                   attachment_format="csv", config=_cfg())
    assert result.kind == "rejected"
    mock_smtp.assert_not_called()
    assert metrics.snapshot()["counters"]["emails_rejected"] == 1


def test_reject_disallowed_domain():
    with patch("smtplib.SMTP") as mock_smtp:
        result = send_report_email(to="x@gmail.com", subject="S", body="", df=DF,
                                   attachment_format="csv",
                                   config=_cfg(allowed_domains=frozenset({"corp.io"})))
    assert result.kind == "rejected" and "not allowed" in result.message
    mock_smtp.assert_not_called()


def test_reject_no_recipient():
    with patch("smtplib.SMTP") as mock_smtp:
        result = send_report_email(to="   ", subject="S", body="", df=DF,
                                   attachment_format="csv", config=_cfg())
    assert result.kind == "rejected"
    mock_smtp.assert_not_called()


def test_reject_oversize_attachment():
    big = pd.DataFrame({"v": range(50_000)})
    with patch("smtplib.SMTP") as mock_smtp:
        result = send_report_email(to="x@corp.io", subject="S", body="", df=big,
                                   attachment_format="csv",
                                   config=_cfg(max_attachment_bytes=200))
    assert result.kind == "rejected" and "limit" in result.message
    mock_smtp.assert_not_called()


def test_reject_when_not_configured():
    with patch("smtplib.SMTP") as mock_smtp:
        result = send_report_email(to="x@corp.io", subject="S", body="", df=DF,
                                   attachment_format="csv",
                                   config=_cfg(user="", password=""))
    assert result.kind == "rejected" and "not configured" in result.message
    mock_smtp.assert_not_called()
