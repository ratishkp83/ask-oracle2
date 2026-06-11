"""B1 — opt-in API-key auth + env-driven CORS (ADR-013, closes ITM-009).

No network, no Oracle. Proves: auth is a strict no-op while APP_API_KEY is
unset (the historical posture); when set, every endpoint except /health
requires X-API-Key and rejects with the uniform 401 envelope; the CORS
wildcard+credentials combination is unrepresentable.
"""

import logging

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app, _cors_config
from src.core.auth import API_KEY_ENV, API_KEY_HEADER
from src.core.logging_config import JsonFormatter
from src.core.profiles import InMemoryProfileStore

client = TestClient(app)

KEY = "test-api-key-123"


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())


@pytest.fixture
def auth_enabled(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, KEY)


# --------------------------------------------------------------------------- #
# Default posture (APP_API_KEY unset) — behaviour unchanged, nothing requires a key
# --------------------------------------------------------------------------- #
def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/profiles").status_code == 200
    assert client.get("/reports").status_code == 200


# --------------------------------------------------------------------------- #
# Auth enabled — everything except /health requires the key
# --------------------------------------------------------------------------- #
def test_health_stays_exempt(auth_enabled):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}  # minimal body, no config detail


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/metrics"),  # deliberately gated (D-B)
        ("get", "/profiles"),
        ("get", "/reports"),
        ("get", "/templates"),
        ("get", "/schemas"),
        ("post", "/execute"),
        ("post", "/nl2sql"),
    ],
)
def test_missing_key_is_401(auth_enabled, method, path):
    resp = getattr(client, method)(path, json={}) if method == "post" else client.get(path)
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"] == "Not authenticated."
    assert body["error_id"]  # uniform envelope via the standard handlers
    assert resp.headers.get("X-Request-ID")


def test_wrong_key_is_401(auth_enabled):
    resp = client.get("/metrics", headers={API_KEY_HEADER: "wrong-key"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated."


def test_correct_key_passes(auth_enabled):
    assert client.get("/metrics", headers={API_KEY_HEADER: KEY}).status_code == 200
    assert client.get("/profiles", headers={API_KEY_HEADER: KEY}).status_code == 200


def test_auth_failure_never_logs_key_material(auth_enabled):
    class _Capture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.setFormatter(JsonFormatter())
            self.lines: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.lines.append(self.format(record))

    logger = logging.getLogger("ask_oracle")
    cap = _Capture()
    logger.addHandler(cap)
    try:
        client.get("/metrics", headers={API_KEY_HEADER: "attacker-guess"})
        client.get("/metrics", headers={API_KEY_HEADER: KEY})
    finally:
        logger.removeHandler(cap)
    joined = "\n".join(cap.lines)
    assert KEY not in joined
    assert "attacker-guess" not in joined


# --------------------------------------------------------------------------- #
# CORS — explicit env-driven origins; "*"+credentials unrepresentable
# --------------------------------------------------------------------------- #
def test_cors_default_is_explicit_localhost(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    origins, allow_credentials = _cors_config()
    assert origins == ["http://localhost:8501", "http://localhost:3000"]
    assert allow_credentials is True  # explicit origins may carry credentials


def test_cors_env_override_parses_and_strips(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://reports.example.com , https://bi.example.com ")
    origins, allow_credentials = _cors_config()
    assert origins == ["https://reports.example.com", "https://bi.example.com"]
    assert allow_credentials is True


def test_cors_wildcard_forfeits_credentials(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    origins, allow_credentials = _cors_config()
    assert origins == ["*"]
    assert allow_credentials is False  # the ITM-009 combination cannot be configured


def test_cors_preflight_not_blocked_by_auth(auth_enabled):
    """CORSMiddleware answers preflights before routing, so OPTIONS needs no key."""
    resp = client.options(
        "/profiles",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
