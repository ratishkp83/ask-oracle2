"""Tests for live schema introspection (Phase 5, ADR-010).

No live Oracle: the data-dictionary queries are validated against the safety
layer, the mappers run on synthetic rows, and the orchestrator uses a mocked
client. The key property: every introspection query is a provably safe SELECT.
"""

import pytest

from src.core.introspection import (
    IntrospectionResult,
    apply_foreign_keys,
    apply_primary_keys,
    build_columns,
    columns_sql,
    foreign_keys_sql,
    introspect_schema,
    primary_keys_sql,
)
from src.core.sql_safety import assert_safe_select
from src.db import QueryResult


# --- builders are safe SELECTs + bind-parameterized ----------------------- #
@pytest.mark.parametrize("builder", [columns_sql, primary_keys_sql, foreign_keys_sql])
def test_introspection_sql_is_safe_select(builder):
    sql, binds = builder("HR", "EMP%")
    result = assert_safe_select(sql)
    assert result.allowed, f"{builder.__name__} not a safe SELECT: {result.reason}"
    assert binds == {"owner": "HR", "table_like": "EMP%"}
    # values are passed as binds, not interpolated into the SQL text
    assert "HR" not in sql and "EMP%" not in sql
    assert ":owner" in sql and ":table_like" in sql


# --- mappers -------------------------------------------------------------- #
def test_build_columns_and_constraints():
    col_rows = [
        {"TABLE_NAME": "EMP", "COLUMN_NAME": "EMP_ID", "DATA_TYPE": "NUMBER"},
        {"TABLE_NAME": "EMP", "COLUMN_NAME": "DEPT_ID", "DATA_TYPE": "NUMBER"},
        {"TABLE_NAME": "DEPT", "COLUMN_NAME": "DEPT_ID", "DATA_TYPE": "NUMBER"},
    ]
    schema = build_columns(col_rows)
    assert schema.list_tables() == ["DEPT", "EMP"]
    assert [c.column_name for c in schema.tables["EMP"].columns] == ["EMP_ID", "DEPT_ID"]

    apply_primary_keys(schema, [{"TABLE_NAME": "EMP", "COLUMN_NAME": "EMP_ID"}])
    assert schema.tables["EMP"].primary_keys() == ["EMP_ID"]

    apply_foreign_keys(
        schema,
        [{"FROM_TABLE": "EMP", "FROM_COLUMN": "DEPT_ID", "TO_TABLE": "DEPT", "TO_COLUMN": "DEPT_ID"}],
    )
    fk = next(c for c in schema.tables["EMP"].columns if c.column_name == "DEPT_ID")
    assert fk.is_foreign_key and fk.references_table == "DEPT" and fk.references_column == "DEPT_ID"
    assert len(schema.relationships) == 1


# --- orchestrator (mocked client) ----------------------------------------- #
class _FakeClient:
    """Returns canned dictionary result sets based on the query shape."""

    def __init__(self, fail_constraints: bool = False):
        self.fail_constraints = fail_constraints
        self.calls = []

    def run_select(self, sql, limits=None, binds=None):
        self.calls.append((sql, binds))
        if "all_tab_columns" in sql:
            return QueryResult(
                columns=["OWNER", "TABLE_NAME", "COLUMN_NAME", "DATA_TYPE", "COLUMN_ID"],
                rows=[
                    ("HR", "EMP", "EMP_ID", "NUMBER", 1),
                    ("HR", "EMP", "DEPT_ID", "NUMBER", 2),
                    ("HR", "DEPT", "DEPT_ID", "NUMBER", 1),
                ],
                elapsed_seconds=0.0, truncated=False, row_count=3,
            )
        if self.fail_constraints:
            raise RuntimeError("ORA-00942: table or view does not exist")
        if "constraint_type = 'P'" in sql:
            return QueryResult(columns=["TABLE_NAME", "COLUMN_NAME"], rows=[("EMP", "EMP_ID")],
                               elapsed_seconds=0.0, truncated=False, row_count=1)
        if "constraint_type = 'R'" in sql:
            return QueryResult(
                columns=["FROM_TABLE", "FROM_COLUMN", "TO_TABLE", "TO_COLUMN"],
                rows=[("EMP", "DEPT_ID", "DEPT", "DEPT_ID")],
                elapsed_seconds=0.0, truncated=False, row_count=1,
            )
        raise AssertionError(f"unexpected sql: {sql}")


def test_introspect_schema_happy_path():
    client = _FakeClient()
    result = introspect_schema(client, owner="hr", table_like="%")
    assert isinstance(result, IntrospectionResult)
    assert not result.warnings
    assert result.schema.list_tables() == ["DEPT", "EMP"]
    assert result.schema.tables["EMP"].primary_keys() == ["EMP_ID"]
    fk = next(c for c in result.schema.tables["EMP"].columns if c.column_name == "DEPT_ID")
    assert fk.references_table == "DEPT"
    # owner upper-cased and bound (not interpolated)
    assert all(b == {"owner": "HR", "table_like": "%"} for _, b in client.calls)


def test_introspect_schema_degrades_gracefully():
    result = introspect_schema(_FakeClient(fail_constraints=True), owner="HR")
    # columns still built; PK/FK degrade to warnings
    assert result.schema.list_tables() == ["DEPT", "EMP"]
    assert len(result.warnings) == 2
    assert result.schema.tables["EMP"].primary_keys() == []
    # F-2: warnings must NOT echo the raw driver exception (ORA-… host/object names)
    assert all("ORA" not in w for w in result.warnings)


def test_introspect_requires_owner():
    with pytest.raises(ValueError, match="owner"):
        introspect_schema(_FakeClient(), owner="  ")
