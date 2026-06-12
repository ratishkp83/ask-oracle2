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
from src.db import OracleClient, OracleConnectionConfig, expand_list_binds, validate_binds

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
        {"ok": {"nested": 1}},      # dict value
        {"ok": object()},           # arbitrary object
        {"ok": []},                 # empty list — Oracle IN () is invalid
        {"ok": [[1, 2]]},           # nested list
        {"ok": [object()]},         # non-scalar inside list
    ],
)
def test_validate_binds_rejects_bad(bad):
    with pytest.raises(SqlSafetyError):
        validate_binds(bad)


def test_validate_binds_rejects_non_mapping():
    with pytest.raises(SqlSafetyError):
        validate_binds([("a", 1)])  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_validate_binds_rejects_non_finite_numbers(bad):
    # F3: NaN/Infinity are never valid Oracle NUMBER binds.
    with pytest.raises(SqlSafetyError):
        validate_binds({"n": bad})


# --- the value never enters the SQL text ---------------------------------- #
def test_injection_as_bind_value_does_not_alter_parsed_sql():
    sql = "SELECT * FROM emp WHERE name = :n"
    # The malicious string is only ever a *value*; the SQL text is benign.
    assert assert_safe_select(sql).allowed is True
    validate_binds({"n": "'; DROP TABLE emp; --"})  # accepted as an inert scalar


def _fake_conn_factory():
    """Return a _FakeConn class that captures execute args into a shared dict."""
    captured: dict = {}

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

        def cursor(self):
            return _FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return _FakeConn, captured


def test_run_select_passes_binds_as_separate_arg(monkeypatch):
    """run_select must hand binds to cur.execute(sql, binds), not format them in."""
    _FakeConn, captured = _fake_conn_factory()
    monkeypatch.setattr(OracleClient, "_connect", lambda self: _FakeConn())
    sql = "SELECT name FROM emp WHERE name = :n"
    cfg = OracleConnectionConfig(
        host="h", port=1521, service_name="XE", sid=None, username="u", password="p"
    )
    OracleClient(cfg).run_select(sql, binds={"n": "'; DROP TABLE emp; --"})

    assert captured["sql"] == sql  # scalar: unchanged, value not spliced in
    assert captured["binds"] == {"n": "'; DROP TABLE emp; --"}


def test_run_select_expands_list_bind_before_execute(monkeypatch):
    """run_select must expand list binds into :name_0, :name_1, ... before execute."""
    _FakeConn, captured = _fake_conn_factory()
    monkeypatch.setattr(OracleClient, "_connect", lambda self: _FakeConn())
    sql = "SELECT * FROM emp WHERE dept_id IN (:depts)"
    cfg = OracleConnectionConfig(
        host="h", port=1521, service_name="XE", sid=None, username="u", password="p"
    )
    OracleClient(cfg).run_select(sql, binds={"depts": [10, 20, 30]})

    # The original single-placeholder form must be gone; the expanded form must be present.
    assert "IN (:depts)" not in captured["sql"]  # unexpanded form replaced
    assert ":depts_0" in captured["sql"] and ":depts_1" in captured["sql"] and ":depts_2" in captured["sql"]
    assert captured["binds"] == {"depts_0": 10, "depts_1": 20, "depts_2": 30}


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


# --- validate_binds: list values ------------------------------------------ #
def test_validate_binds_accepts_list_of_scalars():
    binds = {"ids": [1, 2, 3], "names": ["alice", "bob"]}
    result = validate_binds(binds)
    assert result == binds


def test_validate_binds_accepts_single_item_list():
    assert validate_binds({"x": [42]}) == {"x": [42]}


def test_validate_binds_accepts_list_with_none():
    assert validate_binds({"x": [None, 1]}) == {"x": [None, 1]}


# --- expand_list_binds unit tests ----------------------------------------- #
def test_expand_list_binds_passthrough_scalars():
    sql = "SELECT * FROM t WHERE id = :id"
    out_sql, out_binds = expand_list_binds(sql, {"id": 5})
    assert out_sql == sql
    assert out_binds == {"id": 5}


def test_expand_list_binds_single_item_list():
    sql = "SELECT * FROM t WHERE id IN (:ids)"
    out_sql, out_binds = expand_list_binds(sql, {"ids": [7]})
    assert out_sql == "SELECT * FROM t WHERE id IN (:ids_0)"
    assert out_binds == {"ids_0": 7}


def test_expand_list_binds_multi_item_list():
    sql = "SELECT * FROM t WHERE dept IN (:depts)"
    out_sql, out_binds = expand_list_binds(sql, {"depts": [10, 20, 30]})
    assert out_sql == "SELECT * FROM t WHERE dept IN (:depts_0, :depts_1, :depts_2)"
    assert out_binds == {"depts_0": 10, "depts_1": 20, "depts_2": 30}


def test_expand_list_binds_mixed_scalar_and_list():
    sql = "SELECT * FROM t WHERE dept IN (:depts) AND name = :name"
    out_sql, out_binds = expand_list_binds(sql, {"depts": [10, 20], "name": "alice"})
    assert ":depts_0" in out_sql and ":depts_1" in out_sql
    assert ":name" in out_sql
    assert out_binds["name"] == "alice"
    assert out_binds["depts_0"] == 10 and out_binds["depts_1"] == 20


def test_expand_list_binds_does_not_touch_non_matching_tokens():
    # :dept_id should not be touched when the list bind name is :dept
    sql = "SELECT * FROM t WHERE dept IN (:dept) AND dept_id = :dept_id"
    out_sql, out_binds = expand_list_binds(sql, {"dept": ["A", "B"], "dept_id": 99})
    assert ":dept_0" in out_sql and ":dept_1" in out_sql
    assert ":dept_id" in out_sql  # scalar, unchanged
    assert "dept_id_0" not in out_sql
    assert out_binds["dept_id"] == 99


def test_expand_list_binds_injection_value_is_inert():
    # Even if a list item looks like SQL, it is only ever a bind *value*
    sql = "SELECT * FROM t WHERE name IN (:names)"
    out_sql, out_binds = expand_list_binds(sql, {"names": ["alice", "'; DROP TABLE t; --"]})
    assert out_sql == "SELECT * FROM t WHERE name IN (:names_0, :names_1)"
    assert out_binds["names_1"] == "'; DROP TABLE t; --"  # carried verbatim as a value


def test_expand_list_binds_rejects_overlong_expanded_name():
    from src.core.sql_safety import SqlSafetyError
    long_name = "a" * 28  # 28 chars + "_99" = 31 chars — over the 30-char limit
    binds = {long_name: list(range(100))}
    sql = f"SELECT * FROM t WHERE id IN (:{long_name})"
    validate_binds(binds)  # passes (base name is 28 chars, fine)
    with pytest.raises(SqlSafetyError, match="exceeds"):
        expand_list_binds(sql, binds)


# --- DML with list bind still rejected ------------------------------------ #
def test_dml_with_list_bind_still_rejected():
    resp = client.post(
        "/execute",
        json={
            "sql": "DELETE FROM emp WHERE id IN (:ids)",
            "connection": INLINE,
            "binds": {"ids": [1, 2, 3]},
        },
    )
    assert resp.status_code == 400
