"""API tests for /reports CRUD and /reports/{id}/run.

The Oracle driver is never touched: OracleClient.run_select is monkeypatched for
the run path; rejection/validation paths return before any DB call.
"""

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.profiles import InMemoryProfileStore, ProfileCreate
from src.core.reports import InMemoryReportStore
from src.db import OracleClient, QueryResult

client = TestClient(app)

INLINE = {"host": "db", "port": 1521, "service_name": "XE", "username": "u", "password": "p"}


@pytest.fixture(autouse=True)
def fresh_stores(monkeypatch):
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())
    monkeypatch.setattr(api_module, "_report_store", InMemoryReportStore())


@pytest.fixture
def no_db(monkeypatch):
    captured = {}

    def fake_run_select(self, sql, limits=None, binds=None):
        captured["sql"] = sql
        captured["binds"] = binds
        return QueryResult(columns=["X"], rows=[(1,)], elapsed_seconds=0.0, truncated=False, row_count=1)

    monkeypatch.setattr(OracleClient, "run_select", fake_run_select)
    return captured


def _make_report(**overrides):
    body = {
        "name": "AP Invoices",
        "description": "",
        "sql": "SELECT invoice_num FROM ap_invoices_all WHERE org_id = :org_id",
        "parameters": [{"name": "org_id", "label": "Org", "type": "number", "required": True}],
    }
    body.update(overrides)
    return body


# --- CRUD ----------------------------------------------------------------- #
def test_report_crud_lifecycle():
    created = client.post("/reports", json=_make_report())
    assert created.status_code == 201
    rid = created.json()["id"]
    assert created.json()["parameters"][0]["name"] == "org_id"

    # Duplicate name -> 409
    assert client.post("/reports", json=_make_report()).status_code == 409

    # List + get
    assert any(r["id"] == rid for r in client.get("/reports").json())
    assert client.get(f"/reports/{rid}").status_code == 200
    assert client.get("/reports/missing").status_code == 404

    # Update
    upd = client.put(f"/reports/{rid}", json=_make_report(name="AP Invoices v2"))
    assert upd.status_code == 200 and upd.json()["name"] == "AP Invoices v2"
    assert client.put("/reports/missing", json=_make_report()).status_code == 404

    # Delete, then gone
    assert client.delete(f"/reports/{rid}").status_code == 204
    assert client.get(f"/reports/{rid}").status_code == 404
    assert client.delete(f"/reports/{rid}").status_code == 404


def test_param_lookup_sql_round_trips():
    """A parameter's optional lookup_sql (value-picker query) persists verbatim."""
    body = _make_report(
        name="With lookup",
        parameters=[
            {
                "name": "dept_id",
                "label": "Department",
                "type": "number",
                "required": True,
                "lookup_sql": "SELECT department_id, department_name FROM departments ORDER BY department_name",
            }
        ],
    )
    created = client.post("/reports", json=body)
    assert created.status_code == 201
    param = created.json()["parameters"][0]
    assert param["lookup_sql"] == "SELECT department_id, department_name FROM departments ORDER BY department_name"
    # Omitting it defaults to null (backward-compatible).
    plain = client.post("/reports", json=_make_report(name="No lookup")).json()
    assert plain["parameters"][0]["lookup_sql"] is None


# --- run ------------------------------------------------------------------ #
def test_run_report_with_inline_connection(no_db):
    rid = client.post("/reports", json=_make_report()).json()["id"]
    resp = client.post(f"/reports/{rid}/run", json={"connection": INLINE, "binds": {"org_id": 204}})
    assert resp.status_code == 200
    assert resp.json()["row_count"] == 1
    assert no_db["binds"] == {"org_id": 204}  # coerced to int, bound as value


def test_run_report_uses_bound_default_profile(no_db, monkeypatch):
    profile = api_module._store.create(
        ProfileCreate(name="EBS DEV", host="db", service_name="XE", username="u", password="p")
    )
    rid = client.post(
        "/reports", json=_make_report(default_profile_id=profile.id)
    ).json()["id"]
    # No connection/profile in the run body -> falls back to the report's bound profile.
    resp = client.post(f"/reports/{rid}/run", json={"binds": {"org_id": 1}})
    assert resp.status_code == 200


def test_run_report_missing_required_bind_is_400(no_db):
    rid = client.post("/reports", json=_make_report()).json()["id"]
    resp = client.post(f"/reports/{rid}/run", json={"connection": INLINE, "binds": {}})
    assert resp.status_code == 400
    assert "Missing required" in resp.json()["detail"]


def test_run_report_no_target_is_400(no_db):
    rid = client.post("/reports", json=_make_report()).json()["id"]
    resp = client.post(f"/reports/{rid}/run", json={"binds": {"org_id": 1}})
    assert resp.status_code == 400
    assert "No connection target" in resp.json()["detail"]


def test_run_unknown_report_is_404():
    resp = client.post("/reports/missing/run", json={"connection": INLINE})
    assert resp.status_code == 404


def test_run_report_non_finite_number_is_400(no_db):
    # F3 at the HTTP layer: a NaN/inf number param is a clean 400, not a driver error.
    rid = client.post("/reports", json=_make_report()).json()["id"]
    resp = client.post(f"/reports/{rid}/run", json={"connection": INLINE, "binds": {"org_id": "nan"}})
    assert resp.status_code == 400
    assert "finite number" in resp.json()["detail"]


def test_run_report_unknown_bind_is_400(no_db):
    rid = client.post("/reports", json=_make_report()).json()["id"]
    resp = client.post(
        f"/reports/{rid}/run", json={"connection": INLINE, "binds": {"org_id": 1, "evil": 2}}
    )
    assert resp.status_code == 400
    assert "Unknown parameter" in resp.json()["detail"]


def test_run_report_with_dml_sql_still_rejected(no_db):
    rid = client.post(
        "/reports", json=_make_report(name="Bad", sql="DELETE FROM ap_invoices_all", parameters=[])
    ).json()["id"]
    resp = client.post(f"/reports/{rid}/run", json={"connection": INLINE})
    assert resp.status_code == 400
