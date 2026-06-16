"""API tests for POST /reports/email-bundle (Phase 10, ADR-026).

Emails a prebuilt cascading-report HTML bundle as an ``.html`` attachment. SMTP is
fully mocked (no network). Verifies opt-in gating, the SendResult->HTTP mapping,
allow-list / newline-injection rejections, the size cap, empty-html validation, and
that the /v1 mount is auth-gated. Mirrors ``test_email_api.py``.
"""

import smtplib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.core import metrics
from src.core.auth import API_KEY_ENV, API_KEY_HEADER

client = TestClient(app)

BUNDLE = {
    "to": "cfo@corp.io",
    "subject": "Cascading AR report",
    "body": "See attached.",
    "html": '<!doctype html><html lang="en"><body><h1>Outstanding by region</h1></body></html>',
}


def _payload(**over):
    body = dict(BUNDLE)
    body.update(over)
    return body


@pytest.fixture
def email_on(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-pw")
    monkeypatch.delenv("EMAIL_ALLOWED_DOMAINS", raising=False)
    monkeypatch.delenv("EMAIL_MAX_ATTACHMENT_MB", raising=False)


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


# --- opt-in gating -------------------------------------------------------- #
def test_bundle_not_configured_returns_503(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    resp = client.post("/reports/email-bundle", json=_payload())
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]


# --- happy path ----------------------------------------------------------- #
def test_bundle_success_maps_to_200(email_on):
    with patch("smtplib.SMTP") as mock_smtp, patch("src.core.mailer.sender._audit"):
        resp = client.post("/reports/email-bundle", json=_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["recipients"] == 1
    assert data["attachment_bytes"] > 0
    mock_smtp.return_value.__enter__.return_value.send_message.assert_called_once()
    assert metrics.snapshot()["counters"]["emails_sent"] == 1


def test_bundle_cc_counted(email_on):
    with patch("smtplib.SMTP"), patch("src.core.mailer.sender._audit"):
        resp = client.post("/reports/email-bundle", json=_payload(cc="ap@corp.io, ar@corp.io"))
    assert resp.status_code == 200
    assert resp.json()["recipients"] == 3


# --- rejections (no SMTP call) ------------------------------------------- #
def test_bundle_bad_recipient_400(email_on):
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email-bundle", json=_payload(to="not-an-email"))
    assert resp.status_code == 400
    mock_smtp.assert_not_called()


def test_bundle_disallowed_domain_400(email_on, monkeypatch):
    monkeypatch.setenv("EMAIL_ALLOWED_DOMAINS", "corp.io")
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email-bundle", json=_payload(to="cfo@gmail.com"))
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]
    mock_smtp.assert_not_called()


def test_bundle_newline_injection_400(email_on):
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email-bundle", json=_payload(to="cfo@corp.io\nBcc: evil@x.io"))
    assert resp.status_code == 400
    mock_smtp.assert_not_called()


def test_bundle_empty_html_returns_422(email_on):
    resp = client.post("/reports/email-bundle", json=_payload(html="   "))
    assert resp.status_code == 422  # pydantic field validator


def test_bundle_oversize_returns_400(email_on, monkeypatch):
    monkeypatch.setenv("EMAIL_MAX_ATTACHMENT_MB", "1")
    big = "<html>" + ("a" * (1024 * 1024 + 100)) + "</html>"  # just over 1 MB
    with patch("smtplib.SMTP") as mock_smtp:
        resp = client.post("/reports/email-bundle", json=_payload(html=big))
    assert resp.status_code == 400
    assert "limit" in resp.json()["detail"].lower()
    mock_smtp.assert_not_called()


# --- transport failure ---------------------------------------------------- #
def test_bundle_transport_failure_502_with_error_id(email_on):
    with patch("smtplib.SMTP") as mock_smtp, patch("src.core.mailer.sender._audit"):
        server = mock_smtp.return_value.__enter__.return_value
        server.send_message.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 bad creds")
        resp = client.post("/reports/email-bundle", json=_payload())
    assert resp.status_code == 502
    body = resp.json()
    assert body["error_id"]
    assert "5.7.8" not in body["detail"] and "app-pw" not in body["detail"]  # sanitized
    assert metrics.snapshot()["counters"]["emails_failed"] == 1


# --- /v1 mount is auth-gated --------------------------------------------- #
def test_v1_bundle_requires_auth(monkeypatch, email_on):
    monkeypatch.setenv(API_KEY_ENV, "k")
    assert client.post("/v1/reports/email-bundle", json=_payload()).status_code == 401  # no key
    with patch("smtplib.SMTP"), patch("src.core.mailer.sender._audit"):
        ok = client.post("/v1/reports/email-bundle", json=_payload(), headers={API_KEY_HEADER: "k"})
    assert ok.status_code == 200
