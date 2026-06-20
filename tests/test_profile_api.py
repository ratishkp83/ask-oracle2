"""Phase 11 / B3c — API tests for /schemas/profile, /advisory, /readiness (mocked DB)."""
import json

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.profiles import InMemoryProfileStore
from src.core.schema_store import InMemorySchemaStore
from src.db import OracleClient, QueryResult

client = TestClient(app)
INLINE = {"host": "db", "port": 1521, "service_name": "XE", "username": "u", "password": "p"}


def _qr(columns, rows):
    return QueryResult(columns=columns, rows=rows, elapsed_seconds=0.0,
                       truncated=False, row_count=len(rows))


@pytest.fixture(autouse=True)
def fresh_stores(monkeypatch):
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())
    monkeypatch.setattr(api_module, "_schema_store", InMemorySchemaStore())


@pytest.fixture
def fake_profile(monkeypatch):
    def fake_run_select(self, sql, limits=None, binds=None):
        s = sql.lower()
        if "sample(" in s:  # Channel-B value-domain sample
            return _qr(["CODE", "CNT"], [("A", 90), ("I", 10)])
        if "all_tab_columns" in s:
            return _qr(
                ["OWNER", "TABLE_NAME", "COLUMN_NAME", "DATA_TYPE", "COLUMN_ID",
                 "NULLABLE", "DATA_LENGTH", "DATA_PRECISION", "DATA_SCALE"],
                [("HR", "EMP", "EMP_ID", "NUMBER", 1, "N", 22, None, None),
                 ("HR", "EMP", "DEPT_ID", "NUMBER", 2, "Y", 22, None, None),
                 ("HR", "EMP", "STATUS", "VARCHAR2", 3, "Y", 1, None, None),
                 ("HR", "DEPT", "DEPT_ID", "NUMBER", 1, "N", 22, None, None),
                 ("HR", "DEPT", "NAME", "VARCHAR2", 2, "Y", 100, None, None)],
            )
        if "constraint_type = 'p'" in s:
            return _qr(["TABLE_NAME", "COLUMN_NAME"], [("EMP", "EMP_ID"), ("DEPT", "DEPT_ID")])
        if "constraint_type = 'r'" in s:
            return _qr(["FROM_TABLE", "FROM_COLUMN", "TO_TABLE", "TO_COLUMN"],
                       [("EMP", "DEPT_ID", "DEPT", "DEPT_ID")])
        if "constraint_type = 'u'" in s:
            return _qr(["TABLE_NAME", "COLUMN_NAME"], [])
        if "all_ind_columns" in s:
            return _qr(["TABLE_NAME", "INDEX_NAME", "UNIQUENESS", "COLUMN_NAME", "COLUMN_POSITION"],
                       [("EMP", "EMP_PK", "UNIQUE", "EMP_ID", 1),
                        ("DEPT", "DEPT_PK", "UNIQUE", "DEPT_ID", 1)])
        if "all_part_key_columns" in s:
            return _qr(["TABLE_NAME", "COLUMN_NAME", "COLUMN_POSITION"], [])
        if "all_tables" in s:
            return _qr(["TABLE_NAME", "NUM_ROWS", "LAST_ANALYZED"],
                       [("EMP", 2_000_000, None), ("DEPT", 50, "2026-06-01")])
        raise AssertionError(f"unrouted SQL: {sql}")

    monkeypatch.setattr(OracleClient, "run_select", fake_run_select)


def test_profile_returns_coverage_advisory_readiness(fake_profile):
    resp = client.post("/schemas/profile", json={"connection": INLINE, "owner": "hr"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["definition"]["tables"]) == {"EMP", "DEPT"}
    assert body["coverage"]["indexes"] is True and body["coverage"]["stats"] is True
    kinds = {s["kind"] for s in body["advisory"]}
    assert "index_fk" in kinds and "partition" in kinds and "stats" in kinds
    assert body["readiness"]["state"] in ("ready", "not_optimized")
    assert body["readiness"]["usable"] is True  # soft-block default
    assert body["saved"] is None


def test_profile_and_save_persists_readiness(fake_profile):
    resp = client.post("/schemas/profile",
                       json={"connection": INLINE, "owner": "HR", "save": True, "name": "HR prof"})
    assert resp.status_code == 200
    sid = resp.json()["saved"]["id"]
    assert resp.json()["saved"]["readiness_state"] in ("ready", "not_optimized")
    # persisted readiness + advisory endpoints
    rd = client.get(f"/schemas/{sid}/readiness").json()["readiness"]
    assert rd["state"] in ("ready", "not_optimized")
    adv = client.get(f"/schemas/{sid}/advisory").json()["advisory"]
    assert any(s["kind"] == "index_fk" for s in adv)


def test_profile_update_existing_schema(fake_profile):
    created = client.post("/schemas", json={"name": "ToProfile",
                          "definition": {"tables": {"X": []}, "relationships": []}})
    sid = created.json()["id"]
    resp = client.post("/schemas/profile",
                       json={"connection": INLINE, "owner": "HR", "schema_id": sid})
    assert resp.status_code == 200 and resp.json()["saved"]["id"] == sid
    # the stored definition was replaced by the profiled one
    assert set(client.get(f"/schemas/{sid}").json()["definition"]["tables"]) == {"EMP", "DEPT"}


def test_profile_value_domains_stay_server_side(fake_profile):
    resp = client.post("/schemas/profile", json={
        "connection": INLINE, "owner": "HR", "save": True, "name": "HR vd",
        "sample_value_columns": ["EMP.STATUS"],
    })
    sid = resp.json()["saved"]["id"]
    record = client.get(f"/schemas/{sid}").json()
    # Channel B: captured in semantics, value codes present
    assert "EMP.STATUS" in record["semantics"]["value_domains"]
    codes = [c["code"] for c in record["semantics"]["value_domains"]["EMP.STATUS"]["codes"]]
    assert "A" in codes
    # Invariant 3: value domains are NOT in the (LLM-facing) definition / Channel A
    assert "value_domains" not in json.dumps(record["definition"])


def test_profile_update_unknown_schema_is_404(fake_profile):
    resp = client.post("/schemas/profile",
                       json={"connection": INLINE, "owner": "HR", "schema_id": "nope"})
    assert resp.status_code == 404


def test_advisory_readiness_404_for_unknown_schema():
    assert client.get("/schemas/nope/advisory").status_code == 404
    assert client.get("/schemas/nope/readiness").status_code == 404
