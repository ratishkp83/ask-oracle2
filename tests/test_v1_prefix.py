"""B5 — every route is also mounted under /v1 (T-18), back-compat preserved."""

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.auth import API_KEY_ENV, API_KEY_HEADER
from src.core.profiles import InMemoryProfileStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())


def test_v1_health_and_root_both_work():
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/v1/health").json() == {"status": "ok"}


def test_v1_get_endpoints_match_root():
    assert client.get("/v1/templates").json() == client.get("/templates").json()
    assert client.get("/v1/packs").json() == client.get("/packs").json()


def test_v1_packs_detail_and_404():
    assert client.get("/v1/packs/AP").json()["module"] == "AP"
    assert client.get("/v1/packs/ZZ").status_code == 404


def test_v1_profiles_roundtrip_like_root():
    body = {"name": "P", "host": "db", "service_name": "XE", "username": "u", "password": "p"}
    assert client.post("/v1/profiles", json=body).status_code == 201
    assert any(p["name"] == "P" for p in client.get("/v1/profiles").json())


def test_v1_execute_safety_gate_still_enforced():
    # The chokepoint applies on the /v1 mount exactly as on the root mount.
    resp = client.post("/v1/execute", json={"sql": "DROP TABLE emp",
                                            "connection": {"host": "db", "port": 1521,
                                                           "service_name": "XE", "username": "u", "password": "p"}})
    assert resp.status_code == 400
    assert resp.json()["error_id"]


def test_auth_applies_to_v1_but_health_exempt(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "k")
    # Gated endpoints require the key on the /v1 mount too.
    assert client.get("/v1/metrics").status_code == 401
    assert client.get("/v1/metrics", headers={API_KEY_HEADER: "k"}).status_code == 200
    # Both health paths stay exempt (liveness probes).
    assert client.get("/health").status_code == 200
    assert client.get("/v1/health").status_code == 200
