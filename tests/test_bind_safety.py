"""Bind-parameter safety (Phase 4, ADR-007).

Proves that report/query parameters are passed to the driver as *values* and can
neither alter the parsed SQL nor bypass the SELECT/CTE-only chokepoint.
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.profiles import InMemoryProfileStore
from src.core.sql_safety import SqlSafetyError, assert_safe_select
from src.db import OracleClient, OracleConnectionConfig, validate_binds

client = TestClient(app)
INLINE = {"host": "db", "port": 1521, "service_name": "XE", "username": "u", "password": "p"}


# --- validate_binds accept/reject matrix ---------------------------------- #
def test_validate_binds_accepts_scalars():
    binds = {
        "s": "abc",
        "i": 5,
        "f": 1.5,
        "b": True,
        "n": None,
        "d": date(2026, 1, 1),
        "dt": datetime(2026, 1, 1, 12, 0),
    }
    assert validate_binds(binds) == binds


def test_validate_binds_none_is_empty():
    assert validate_binds(None) == {}


@pytest.mark.parametrize(
    "bad",
    [
        {"1bad": 1},               # name must start with a letter/underscore
        {"drop table": 1},          # no spaces in a bind name
        {"a" * 31: 1},              # too long
        {"ok": [1, 2, 3]},          # list value
        {"ok": {"nested": 1}},      # dict value
        {"ok": object()},           # arbitrary object
    ],
)
def test_validate_binds_rejects_bad(bad):
    with pytest.raises(SqlSafetyError):
        validate_binds(bad)


def test_validate_binds_rejects_non_mapping():
    with pytest.raises(SqlSafetyError):
        validate_binds([("a", 1)])  # type: ignore[arg-type]


# --- the value never enters the SQL text ---------------------------------- #
def test_injection_as_bind_value_does_not_alter_parsed_sql():
    sql = "SELECT * FROM emp WHERE name = :n"
    # The malicious string is only ever a *value*; the SQL text is benign.
    assert assert_safe_select(sql).allowed is True
    validate_binds({"n": "'; DROP TABLE emp; --"})  # accepted as an inert scalar


def test_run_select_passes_binds_as_separate_arg(monkeypatch):
    """run_select must hand binds to cur.execute(sql, binds), not format them in."""
    captured = {}

    class _FakeCursor:
        def __init__(self):
            self.description = [("NAME",)]
            self._rows = [("alice",)]

        def execute(self, sql, binds=None):
            captured["sql"] = sql
            captured["binds"] = binds

        def fetchone(self):
            return self._rows.pop(0) if self._rows else None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _FakeConn:
        def __init__(self):
            self.call_timeout = None
            self._cur = _FakeCursor()

        def cursor(self):
            return self._cur

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(OracleClient, "_connect", lambda self: _FakeConn())
    sql = "SELECT name FROM emp WHERE name = :n"
    cfg = OracleConnectionConfig(
        host="h", port=1521, service_name="XE", sid=None, username="u", password="p"
    )
    OracleClient(cfg).run_select(sql, binds={"n": "'; DROP TABLE emp; --"})

    assert captured["sql"] == sql  # unchanged, value not spliced in
    assert captured["binds"] == {"n": "'; DROP TABLE emp; --"}


# --- binds cannot bypass the SELECT-only gate ----------------------------- #
@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())


def test_dml_with_binds_still_rejected():
    resp = client.post(
        "/execute",
        json={"sql": "DELETE FROM emp WHERE id = :id", "connection": INLINE, "binds": {"id": 1}},
    )
    assert resp.status_code == 400


def test_parameterized_select_runs(monkeypatch):
    from src.db import QueryResult

    def fake_run_select(self, sql, limits=None, binds=None):
        assert binds == {"n": "x'; DROP TABLE emp; --"}  # carried through as a value
        return QueryResult(columns=["NAME"], rows=[("x",)], elapsed_seconds=0.0, truncated=False, row_count=1)

    monkeypatch.setattr(OracleClient, "run_select", fake_run_select)
    resp = client.post(
        "/execute",
        json={
            "sql": "SELECT name FROM emp WHERE name = :n",
            "connection": INLINE,
            "binds": {"n": "x'; DROP TABLE emp; --"},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["row_count"] == 1
