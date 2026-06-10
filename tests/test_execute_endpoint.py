"""API tests for /execute and /profiles.

The Oracle driver is never touched: OracleClient.run_select is monkeypatched for
the success paths, and rejection/validation paths return before any DB call.
"""

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.profiles import InMemoryProfileStore, ProfileCreate
from src.db import OracleClient, QueryResult

client = TestClient(app)

INLINE = {"host": "db", "port": 1521, "service_name": "XE", "username": "u", "password": "p"}


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    """Isolate each test with an empty in-memory profile store."""
    store = InMemoryProfileStore()
    monkeypatch.setattr(api_module, "_store", store)
    return store


@pytest.fixture
def no_db(monkeypatch):
    """Stub query execution so we never open a real Oracle connection."""

    def fake_run_select(self, sql, limits=None, binds=None):
        return QueryResult(columns=["N"], rows=[(1,)], elapsed_seconds=0.01, truncated=False, row_count=1)

    monkeypatch.setattr(OracleClient, "run_select", fake_run_select)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DROP TABLE emp",
        "DELETE FROM emp",
        "UPDATE emp SET x = 1",
        "INSERT INTO emp (id) VALUES (1)",
        "SELECT * FROM emp; DROP TABLE emp",
        "SELECT * FROM emp FOR UPDATE",
    ],
)
def test_execute_rejects_unsafe_sql(bad_sql):
    resp = client.post("/execute", json={"sql": bad_sql, "connection": INLINE})
    assert resp.status_code == 400


def test_execute_requires_a_target():
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL"})
    assert resp.status_code == 422  # neither profile_id nor connection


def test_execute_unknown_profile_returns_404():
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "profile_id": "missing"})
    assert resp.status_code == 404


def test_execute_valid_select_inline(no_db):
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "connection": INLINE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"] == ["N"]
    assert body["row_count"] == 1
    assert body["truncated"] is False


def test_execute_via_profile(no_db, fresh_store):
    public = fresh_store.create(
        ProfileCreate(name="P1", host="db", service_name="XE", username="u", password="p")
    )
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "profile_id": public.id})
    assert resp.status_code == 200


def test_nl2sql_provider_failure_is_clean(monkeypatch):
    """F2 at the HTTP layer — provider failure must not return RetryError/internal repr or the key."""
    from src import nl2sql

    class FakeProvider:
        name = "external"

        def is_available(self):
            return True

        def resolve_model(self, requested=None):
            return "m"

        def complete(self, system, user, model=None):
            return "x"

    monkeypatch.setattr(nl2sql, "select_provider", lambda cfg=None, policy=None: FakeProvider())

    def boom(provider, system, user, model):
        raise RuntimeError("401 Unauthorized sk-leak-123")

    monkeypatch.setattr(nl2sql, "_complete_with_retry", boom)

    csv = (
        "table_name,column_name,data_type,is_primary_key,is_foreign_key,references_table,references_column\n"
        "EMP,EMP_ID,NUMBER,true,false,,\n"
    )
    resp = client.post("/nl2sql", json={"natural_language": "show employees", "schema_csv": csv})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "RetryError" not in detail
    assert "sk-leak-123" not in detail


def test_profiles_crud_and_password_not_returned():
    payload = {"name": "EBS DEV", "host": "db", "service_name": "XE", "username": "u", "password": "p"}

    created = client.post("/profiles", json=payload)
    assert created.status_code == 201
    body = created.json()
    pid = body["id"]
    assert "password" not in body and "password_encrypted" not in body

    # Duplicate name -> 409
    assert client.post("/profiles", json=payload).status_code == 409

    # Listed and fetchable
    assert any(p["id"] == pid for p in client.get("/profiles").json())
    assert client.get(f"/profiles/{pid}").status_code == 200

    # Deletable, then gone
    assert client.delete(f"/profiles/{pid}").status_code == 204
    assert client.get(f"/profiles/{pid}").status_code == 404
