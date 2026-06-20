"""Phase 11 multi-engine MVP — PostgreSQL engine + factory + dialect-aware safety.

The psycopg2 driver is mocked via a fake connection so these run with no live DB.
"""
from __future__ import annotations

import pytest

from src.core.db_factory import make_client
from src.core.db_postgres import PostgresClient, PostgresConnectionConfig, _to_pyformat
from src.core.sql_safety import SqlSafetyError, assert_safe_select
from src.db import OracleClient, OracleConnectionConfig

PG_CFG = PostgresConnectionConfig(
    host="db.x.supabase.co", port=5432, database="postgres",
    username="readonly", password="secret", search_path="public",
)


# --- dialect-aware safety ---------------------------------------------------- #
def test_safety_accepts_postgres_limit_select():
    assert assert_safe_select("SELECT id, name FROM sales LIMIT 10", dialect="postgres").allowed


def test_safety_rejects_non_select_postgres():
    assert not assert_safe_select("DELETE FROM sales", dialect="postgres").allowed
    assert not assert_safe_select("UPDATE sales SET x = 1", dialect="postgres").allowed


# --- bind translation -------------------------------------------------------- #
def test_to_pyformat_translates_named_binds_but_not_casts():
    assert _to_pyformat("SELECT * FROM t WHERE c = :p0") == "SELECT * FROM t WHERE c = %(p0)s"
    # Postgres ::type casts must be left alone.
    assert _to_pyformat("SELECT amount::int FROM t") == "SELECT amount::int FROM t"


# --- factory ----------------------------------------------------------------- #
def test_factory_dispatches_by_config_type():
    assert isinstance(make_client(PG_CFG), PostgresClient)
    ora = OracleConnectionConfig(
        host="h", port=1521, service_name="XE", sid=None, username="u", password="p"
    )
    assert isinstance(make_client(ora), OracleClient)


# --- run_select (fake driver) ----------------------------------------------- #
class _FakeCursor:
    def __init__(self, rows, description):
        self._rows = list(rows)
        self.description = description
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def _client_with(rows, description, monkeypatch):
    cur = _FakeCursor(rows, description)
    conn = _FakeConn(cur)
    client = PostgresClient(PG_CFG)
    monkeypatch.setattr(PostgresClient, "_connect", lambda self: conn)
    return client, cur, conn


def test_run_select_returns_query_result(monkeypatch):
    client, cur, conn = _client_with(
        rows=[(1, "Widget"), (2, "Gadget")],
        description=[("ID",), ("NAME",)],
        monkeypatch=monkeypatch,
    )
    res = client.run_select("SELECT id, name FROM sales")
    assert res.columns == ["ID", "NAME"]
    assert res.rows == [(1, "Widget"), (2, "Gadget")]
    assert res.row_count == 2 and res.truncated is False
    assert conn.closed is True  # connection always closed


def test_run_select_rejects_non_select(monkeypatch):
    client, _, _ = _client_with([], [], monkeypatch)
    with pytest.raises(SqlSafetyError):
        client.run_select("DROP TABLE sales")


def test_run_select_uses_pyformat_only_with_binds(monkeypatch):
    client, cur, _ = _client_with([(1,)], [("C",)], monkeypatch)
    client.run_select("SELECT c FROM t WHERE c = :p0", binds={"p0": "X"})
    # the data query (last execute) was translated + bound
    data_sql, params = cur.executed[-1]
    assert "%(p0)s" in data_sql and params == {"p0": "X"}
