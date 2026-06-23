"""Brevo HTTP API backend — the path that works on hosts that block SMTP (Render)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.core import metrics
from src.core.errors import GENERIC_EMAIL_DETAIL
from src.core.mailer.config import EmailConfig, email_enabled, load_config
from src.core.mailer.sender import SendResult, send_report_email

DF = pd.DataFrame({"id": [1, 2], "amount": [10, 20]})
_KEY = "xkeysib-SUPER-SECRET-KEY"


def _brevo_cfg(**over) -> EmailConfig:
    base = dict(
        host="smtp.gmail.com", port=587, user="", password="",
        sender="Reports <me@example.com>", allowed_domains=frozenset(),
        max_attachment_bytes=20 * 1024 * 1024, provider="brevo", api_key=_KEY,
    )
    base.update(over)
    return EmailConfig(**base)


class _Resp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


def test_brevo_send_success_builds_correct_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers)
        return _Resp(201, '{"messageId":"<abc@brevo>"}')

    monkeypatch.setattr("requests.post", fake_post)
    with patch("smtplib.SMTP") as smtp, patch("src.core.mailer.sender._audit"):
        result = send_report_email(
            to="x@corp.io, y@corp.io", cc="z@corp.io", subject="Q4 sales",
            body="see attached", df=DF, attachment_format="csv", config=_brevo_cfg(),
        )

    assert isinstance(result, SendResult) and result.ok
    smtp.assert_not_called()  # HTTP path, never SMTP
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"]["api-key"] == _KEY
    body = captured["json"]
    assert body["sender"] == {"email": "me@example.com", "name": "Reports"}
    assert body["to"] == [{"email": "x@corp.io"}, {"email": "y@corp.io"}]
    assert body["cc"] == [{"email": "z@corp.io"}]
    assert body["subject"] == "Q4 sales"
    assert body["attachment"][0]["name"].endswith(".csv")
    assert body["attachment"][0]["content"]  # base64 content present
    assert metrics.snapshot()["counters"]["emails_sent"] == 1


def test_brevo_api_error_is_sanitized(monkeypatch):
    monkeypatch.setattr("requests.post", lambda url, **k: _Resp(401, '{"message":"Key not found"}'))
    with patch("src.core.mailer.sender._audit") as audit:
        result = send_report_email(
            to="x@corp.io", subject="S", body="", df=DF,
            attachment_format="csv", config=_brevo_cfg(),
        )
    assert result.kind == "error" and result.error_id
    assert result.message == GENERIC_EMAIL_DETAIL
    assert _KEY not in result.message
    assert metrics.snapshot()["counters"]["emails_failed"] == 1
    audit.warning.assert_called_once()
    assert _KEY not in repr(audit.warning.call_args)  # secret never logged


def test_brevo_rejected_without_sender_skips_http(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    result = send_report_email(
        to="x@corp.io", subject="S", body="", df=DF,
        attachment_format="csv", config=_brevo_cfg(sender=""),
    )
    assert result.kind == "rejected" and "not configured" in result.message


def test_email_enabled_detects_brevo(monkeypatch):
    for k in ("SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("BREVO_API_KEY", _KEY)
    monkeypatch.setenv("EMAIL_FROM", "me@example.com")
    assert email_enabled() is True
    cfg = load_config()
    assert cfg.provider == "brevo" and cfg.is_configured


def test_brevo_needs_sender_to_enable(monkeypatch):
    for k in ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("BREVO_API_KEY", _KEY)  # key but no sender → not enabled
    assert email_enabled() is False
