"""API tests for POST /reports/email (Phase 9, ADR-020).

Exposes the Phase-8 mailer over HTTP. SMTP transport is fully mocked (no
network). Verifies opt-in gating, the SendResult->HTTP mapping, allow-list /
newline-injection / bad-format rejections, malformed-result handling, and that
the /v1 mount is auth-gated like every other route.
"""

import smtplib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.core import metrics
from src.core.auth import API_KEY_ENV, API_KEY_HEADER

client = TestClient(app)

RESULT = {
    "to": "cfo@corp.io",
    "subject": "Top customers by outstanding AR",
    "body": "See attached.",
    "attachment_format": "csv",
    "columns": ["customer", "outstanding"],
    "rows": [["Meridian Stores", 1140200], ["Northwind Foods", 922500]],
}


def _payload(**over):
    body = dict(RESULT)
    body.update(over)
    return body


@pytest.fixture
def email_on(monkeypatch):
    """Configure the mailbox (opt-in) for the duration of a test."""
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-pw")
    monkeypatch.delenv("EMAIL_ALLOWED_DOMAINS", raising=False)


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


# --- opt-in gating -------------------------------------------------------- #
def test_email_not_configured_returns_503(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    resp = client.post("/reports/email", json=_payload())
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]


# --- happy path ----------------------------------------------------------- #
def test_email_success_maps_to_200(email_on):
    with patch("smtplib.SMTP") as mock_smtp, patch("src.core.mailer.sender._audit"):
        resp = client.post("/reports/email", json=_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["recipients"] == 1
    assert data["attachment_bytes"] > 0
    mock_smtp.return_value.__enter__.return_value.send_message.assert_called_once()
    assert metrics.snapshot()["counters"]["emails_sent"] == 1


def test_email_cc_recipients_counted(email_on):
    with patch("smtplib.SMTP"), patch("src.core.mailer.sender._audit"):
        resp = client.post("/reports/email", json=_payload(cc="ap@corp.io, ar@corp.io"))
    assert resp.status_code == 200
    assert resp.json()["recipients"] == 3


def test_email_xlsx_format_accepted(email_on):
    with patch("smtplib.SMTP"), patch("src.core.mailer.sender._audit"):
        resp = client.post("/reports/email", json=_payload(attachment_format="xlsx"))
    assert resp.status_code == 200


# --- rejections (no SMTP call) ------------------------------------------- #
def test_email_bad_recipient_returns_400(email_on):
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email", json=_payload(to="not-an-email"))
    assert resp.status_code == 400
    mock_smtp.assert_not_called()


def test_email_disallowed_domain_returns_400(email_on, monkeypatch):
    monkeypatch.setenv("EMAIL_ALLOWED_DOMAINS", "corp.io")
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email", json=_payload(to="cfo@gmail.com"))
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]
    mock_smtp.assert_not_called()


def test_email_newline_injection_rejected(email_on):
    # A CRLF/newline-bearing recipient is split + rejected before any SMTP call.
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email", json=_payload(to="cfo@corp.io\nBcc: evil@x.io"))
    assert resp.status_code == 400
    mock_smtp.assert_not_called()


def test_email_bad_format_returns_400(email_on):
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email", json=_payload(attachment_format="pdf"))
    assert resp.status_code == 400
    assert "csv" in resp.json()["detail"].lower()
    mock_smtp.assert_not_called()


# --- transport failure ---------------------------------------------------- #
def test_email_transport_failure_returns_502_with_error_id(email_on):
    with patch("smtplib.SMTP") as mock_smtp, patch("src.core.mailer.sender._audit"):
        server = mock_smtp.return_value.__enter__.return_value
        server.send_message.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 bad creds")
        resp = client.post("/reports/email", json=_payload())
    assert resp.status_code == 502
    body = resp.json()
    assert body["error_id"]
    assert "5.7.8" not in body["detail"] and "app-pw" not in body["detail"]  # sanitized
    assert metrics.snapshot()["counters"]["emails_failed"] == 1


# --- malformed result ----------------------------------------------------- #
def test_email_ragged_rows_returns_400(email_on):
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email", json=_payload(rows=[["only-one-col"]]))
    assert resp.status_code == 400
    mock_smtp.assert_not_called()


def test_email_empty_columns_returns_422(email_on):
    resp = client.post("/reports/email", json=_payload(columns=[], rows=[]))
    assert resp.status_code == 422  # pydantic field validator


# --- /v1 mount is auth-gated --------------------------------------------- #
def test_v1_email_requires_auth(monkeypatch, email_on):
    monkeypatch.setenv(API_KEY_ENV, "k")
    assert client.post("/v1/reports/email", json=_payload()).status_code == 401  # no key
    with patch("smtplib.SMTP"), patch("src.core.mailer.sender._audit"):
        ok = client.post("/v1/reports/email", json=_payload(), headers={API_KEY_HEADER: "k"})
    assert ok.status_code == 200
