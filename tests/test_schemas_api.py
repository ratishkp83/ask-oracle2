"""API tests for /schemas CRUD and /schemas/introspect (mocked DB)."""

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.profiles import InMemoryProfileStore
from src.core.schema_store import InMemorySchemaStore
from src.db import OracleClient, QueryResult

client = TestClient(app)

INLINE = {"host": "db", "port": 1521, "service_name": "XE", "username": "u", "password": "p"}
DEFINITION = {"tables": {"EMP": [], "DEPT": []}, "relationships": []}


@pytest.fixture(autouse=True)
def fresh_stores(monkeypatch):
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())
    monkeypatch.setattr(api_module, "_schema_store", InMemorySchemaStore())


@pytest.fixture
def fake_dictionary(monkeypatch):
    """Stub OracleClient.run_select to return canned data-dictionary rows."""

    def fake_run_select(self, sql, limits=None, binds=None):
        if "all_tab_columns" in sql:
            return QueryResult(
                columns=["OWNER", "TABLE_NAME", "COLUMN_NAME", "DATA_TYPE", "COLUMN_ID"],
                rows=[("HR", "EMP", "EMP_ID", "NUMBER", 1), ("HR", "DEPT", "DEPT_ID", "NUMBER", 1)],
                elapsed_seconds=0.0, truncated=False, row_count=2,
            )
        if "constraint_type = 'P'" in sql:
            return QueryResult(columns=["TABLE_NAME", "COLUMN_NAME"], rows=[("EMP", "EMP_ID")],
                               elapsed_seconds=0.0, truncated=False, row_count=1)
        return QueryResult(columns=["FROM_TABLE", "FROM_COLUMN", "TO_TABLE", "TO_COLUMN"], rows=[],
                           elapsed_seconds=0.0, truncated=False, row_count=0)

    monkeypatch.setattr(OracleClient, "run_select", fake_run_select)


# --- CRUD ----------------------------------------------------------------- #
def test_schema_crud_lifecycle():
    created = client.post("/schemas", json={"name": "EBS DEV", "definition": DEFINITION})
    assert created.status_code == 201
    body = created.json()
    sid = body["id"]
    assert body["table_count"] == 2 and body["source"] == "upload"

    # Duplicate name -> 409
    assert client.post("/schemas", json={"name": "EBS DEV", "definition": DEFINITION}).status_code == 409

    # List returns summaries (no definition blob)
    listing = client.get("/schemas").json()
    assert any(s["id"] == sid for s in listing)
    assert "definition" not in listing[0]

    # Get returns the full record
    full = client.get(f"/schemas/{sid}").json()
    assert "tables" in full["definition"]
    assert client.get("/schemas/missing").status_code == 404

    # Delete, then gone
    assert client.delete(f"/schemas/{sid}").status_code == 204
    assert client.get(f"/schemas/{sid}").status_code == 404
    assert client.delete(f"/schemas/{sid}").status_code == 404


def test_create_schema_from_csv():
    csv = (
        "table_name,column_name,data_type,is_primary_key,is_foreign_key,references_table,references_column\n"
        "EMP,EMP_ID,NUMBER,true,false,,\n"
    )
    resp = client.post("/schemas", json={"name": "FromCSV", "schema_csv": csv})
    assert resp.status_code == 201
    assert resp.json()["table_count"] == 1


def test_create_schema_requires_a_source():
    assert client.post("/schemas", json={"name": "NoSource"}).status_code == 422


# --- introspect ----------------------------------------------------------- #
def test_introspect_inline_connection(fake_dictionary):
    resp = client.post(
        "/schemas/introspect",
        json={"connection": INLINE, "owner": "hr", "table_like": "%"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["table_count"] == 2
    assert set(body["definition"]["tables"].keys()) == {"EMP", "DEPT"}
    assert body["saved"] is None  # not saved unless requested


def test_introspect_and_save(fake_dictionary):
    resp = client.post(
        "/schemas/introspect",
        json={"connection": INLINE, "owner": "HR", "save": True, "name": "HR dict"},
    )
    assert resp.status_code == 200
    assert resp.json()["saved"]["source"] == "introspection"
    # now appears in the store
    assert any(s["name"] == "HR dict" for s in client.get("/schemas").json())


def test_introspect_requires_target():
    assert client.post("/schemas/introspect", json={"owner": "HR"}).status_code == 422


def test_introspect_blank_owner_is_400(fake_dictionary):
    resp = client.post("/schemas/introspect", json={"connection": INLINE, "owner": "   "})
    assert resp.status_code == 400
    assert "owner" in resp.json()["detail"].lower()
