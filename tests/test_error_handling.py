"""B2 — uniform error sanitization, correlation IDs, and the error envelope.

No network, no Oracle: ``OracleClient.run_select`` is monkeypatched to raise.
Proves ITM-015 is closed — a raw driver error never reaches the client, yet the
full detail is captured server-side keyed by the same ``error_id``.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.logging_config import JsonFormatter
from src.core.profiles import InMemoryProfileStore, ProfileCreate
from src.db import OracleClient, QueryResult

client = TestClient(app)

INLINE = {"host": "db", "port": 1521, "service_name": "XE", "username": "u", "password": "p"}

# A driver error whose text embeds infrastructure detail that must NOT leak.
LEAKY = "ORA-12541: TNS:no listener at dbhost.internal:1521 user=SCOTT"


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())


@pytest.fixture
def server_logs():
    """Capture what is emitted server-side on the ask_oracle namespace."""
    logger = logging.getLogger("ask_oracle")
    cap = _Capture()
    logger.addHandler(cap)
    try:
        yield cap
    finally:
        logger.removeHandler(cap)


# --------------------------------------------------------------------------- #
# ITM-015 — DB driver error is sanitized to the client, logged in full server-side
# --------------------------------------------------------------------------- #
def test_db_error_is_sanitized_but_logged_server_side(monkeypatch, server_logs):
    def boom(self, sql, limits=None, binds=None):
        raise RuntimeError(LEAKY)

    monkeypatch.setattr(OracleClient, "run_select", boom)
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "connection": INLINE})

    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"] == "Database error — see server logs."
    assert body["error_id"]
    # No infrastructure detail leaks to the client — body OR headers (F-5).
    assert "dbhost.internal" not in resp.text
    assert "SCOTT" not in resp.text
    assert "ORA-12541" not in resp.text
    header_blob = " ".join(f"{k}:{v}" for k, v in resp.headers.items())
    assert "dbhost.internal" not in header_blob and "SCOTT" not in header_blob
    # But the full detail IS captured server-side, keyed by the same error_id.
    joined = "\n".join(server_logs.lines)
    assert LEAKY in joined
    assert body["error_id"] in joined


def test_introspect_db_error_is_sanitized(monkeypatch, server_logs):
    """F-5: /schemas/introspect must sanitize raw driver errors like the others."""

    def boom(*args, **kwargs):
        raise RuntimeError(LEAKY)

    monkeypatch.setattr(api_module, "introspect_schema", boom)
    resp = client.post("/schemas/introspect", json={"connection": INLINE, "owner": "HR"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"] == "Database error — see server logs."
    assert body["error_id"]
    assert "dbhost.internal" not in resp.text and "SCOTT" not in resp.text
    header_blob = " ".join(f"{k}:{v}" for k, v in resp.headers.items())
    assert "dbhost.internal" not in header_blob and "SCOTT" not in header_blob
    assert LEAKY in "\n".join(server_logs.lines)


def test_inbound_request_id_is_sanitized_in_echo_header():
    """F-3: a malicious inbound X-Request-ID cannot inject control chars into
    the echoed header / body / logs — it is reduced to a safe token."""
    resp = client.get("/health", headers={"X-Request-ID": "ok-1\r\nSet-Cookie: x=y"})
    echoed = resp.headers.get("X-Request-ID")
    # The id is reduced to an opaque token: no CR/LF/space/colon survive, so it
    # cannot terminate the header or forge a new one.
    assert echoed and not any(c in echoed for c in "\r\n :")
    assert resp.headers.get("Set-Cookie") is None  # no header was injected


@pytest.mark.parametrize("path", ["/test-connection", "/profiles-test"])
def test_other_db_endpoints_are_also_sanitized(monkeypatch, path):
    def boom(self, sql, limits=None, binds=None):
        raise RuntimeError(LEAKY)

    monkeypatch.setattr(OracleClient, "run_select", boom)

    if path == "/test-connection":
        resp = client.post("/test-connection", json=INLINE)
    else:
        store = api_module._store
        public = store.create(ProfileCreate(name="P", host="db", service_name="XE", username="u", password="p"))
        resp = client.post(f"/profiles/{public.id}/test")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Database error — see server logs."
    assert "dbhost.internal" not in resp.text and "SCOTT" not in resp.text


# --------------------------------------------------------------------------- #
# Correlation id — generated, honoured inbound, echoed, reused as error_id
# --------------------------------------------------------------------------- #
def test_request_id_generated_and_echoed():
    resp = client.get("/health")
    assert resp.headers.get("X-Request-ID")


def test_inbound_request_id_is_honoured_and_becomes_error_id():
    rid = "corr-abc-123"
    resp = client.post(
        "/execute",
        json={"sql": "SELECT 1 FROM DUAL", "profile_id": "missing"},
        headers={"X-Request-ID": rid},
    )
    assert resp.status_code == 404  # unknown profile
    assert resp.headers.get("X-Request-ID") == rid
    assert resp.json()["error_id"] == rid


# --------------------------------------------------------------------------- #
# Safe/intentional messages stay verbatim and merely GAIN an error_id (additive)
# --------------------------------------------------------------------------- #
def test_not_found_detail_is_verbatim_plus_error_id():
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "profile_id": "missing"})
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"] == "Profile not found."  # unchanged
    assert body["error_id"]


def test_safety_rejection_reason_stays_verbatim():
    resp = client.post("/execute", json={"sql": "DROP TABLE emp", "connection": INLINE})
    assert resp.status_code == 400
    body = resp.json()
    # The safety reason is user-actionable and must NOT be replaced by the generic DB message.
    assert body["detail"] != "Database error — see server logs."
    assert body["error_id"]


def test_validation_error_gains_error_id():
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL"})  # no target
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], list)  # FastAPI validation detail preserved
    assert body["error_id"]


# --------------------------------------------------------------------------- #
# Catch-all — an unexpected error never leaks; generic 500 + error_id
# --------------------------------------------------------------------------- #
def test_unhandled_error_returns_generic_500(monkeypatch):
    safe_client = TestClient(app, raise_server_exceptions=False)

    class Boom:
        def list(self):
            raise RuntimeError("kaboom internal secret")

    monkeypatch.setattr(api_module, "_store", Boom())
    resp = safe_client.get("/profiles")
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Internal server error."
    assert body["error_id"]
    assert "kaboom" not in resp.text


# --------------------------------------------------------------------------- #
# Shared UI sanitizer (used by src/app.py, which bypasses HTTP) — same rule
# --------------------------------------------------------------------------- #
def test_ui_sanitizer_returns_ref_and_logs_full_detail(server_logs):
    from src.core.errors import GENERIC_DB_DETAIL, sanitize_db_error_for_ui

    error_id, msg = sanitize_db_error_for_ui(RuntimeError(LEAKY), context="ui-execute")
    assert msg == GENERIC_DB_DETAIL  # generic to the user
    assert error_id
    joined = "\n".join(server_logs.lines)
    assert LEAKY in joined  # full detail server-side
    assert error_id in joined  # keyed by the same ref


def test_sanitize_correlation_id_strips_unsafe_and_bounds_length():
    from src.core.errors import sanitize_correlation_id

    assert sanitize_correlation_id("abc-123_.ok") == "abc-123_.ok"  # safe chars kept
    assert sanitize_correlation_id("a\r\nb c:d") == "abcd"  # CR/LF/space/colon stripped
    assert sanitize_correlation_id(None) is None
    assert sanitize_correlation_id("") is None
    assert sanitize_correlation_id("!@#$%") is None  # nothing safe → None (caller regenerates)
    assert len(sanitize_correlation_id("x" * 500)) == 128  # length-bounded
