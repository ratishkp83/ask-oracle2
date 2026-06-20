"""Phase 11 / B3 — database profiling (Channel A) unit tests (ADR-028).

Covers the new introspection builders, mappers, the `profile_schema` orchestrator
(including privilege-degradation), and the additive serialization round-trip.
"""
from __future__ import annotations

import pytest

from src.core.introspection import (
    apply_foreign_keys,
    apply_indexes,
    apply_partition_keys,
    apply_primary_keys,
    apply_table_stats,
    apply_unique,
    build_columns,
    columns_sql,
    derive_fk_cardinality,
    indexes_sql,
    partition_keys_sql,
    profile_schema,
    table_stats_sql,
    unique_constraints_sql,
)
from src.schema import schema_from_dict, schema_to_dict


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeResult:
    def __init__(self, columns, rows, truncated=False):
        self.columns = columns
        self.rows = rows
        self.truncated = truncated


def _route(sql: str) -> str:
    s = sql.lower()
    if "all_tab_columns" in s:
        return "columns"
    if "constraint_type = 'p'" in s:
        return "pk"
    if "constraint_type = 'r'" in s:
        return "fk"
    if "constraint_type = 'u'" in s:
        return "unique"
    if "all_ind_columns" in s or "all_indexes" in s:
        return "indexes"
    if "all_part_key_columns" in s:
        return "partitions"
    if "all_tables" in s:
        return "stats"
    raise AssertionError(f"unrouted SQL: {sql}")


_RESPONSES = {
    "columns": FakeResult(
        ["OWNER", "TABLE_NAME", "COLUMN_NAME", "DATA_TYPE", "COLUMN_ID",
         "NULLABLE", "DATA_LENGTH", "DATA_PRECISION", "DATA_SCALE"],
        [
            ("AOR_DEMO", "ORDERS", "ORDER_ID", "NUMBER", 1, "N", 22, None, None),
            ("AOR_DEMO", "ORDERS", "CUSTOMER_ID", "NUMBER", 2, "Y", 22, None, None),
            ("AOR_DEMO", "ORDERS", "ORDER_DATE", "DATE", 3, "Y", 7, None, None),
            ("AOR_DEMO", "ORDERS", "AMOUNT", "NUMBER", 4, "Y", 22, 10, 2),
            ("AOR_DEMO", "CUSTOMERS", "CUSTOMER_ID", "NUMBER", 1, "N", 22, None, None),
            ("AOR_DEMO", "CUSTOMERS", "NAME", "VARCHAR2", 2, "Y", 100, None, None),
        ],
    ),
    "pk": FakeResult(["TABLE_NAME", "COLUMN_NAME"],
                     [("ORDERS", "ORDER_ID"), ("CUSTOMERS", "CUSTOMER_ID")]),
    "fk": FakeResult(["FROM_TABLE", "FROM_COLUMN", "TO_TABLE", "TO_COLUMN"],
                     [("ORDERS", "CUSTOMER_ID", "CUSTOMERS", "CUSTOMER_ID")]),
    "indexes": FakeResult(
        ["TABLE_NAME", "INDEX_NAME", "UNIQUENESS", "COLUMN_NAME", "COLUMN_POSITION"],
        [
            ("ORDERS", "ORDERS_PK", "UNIQUE", "ORDER_ID", 1),
            ("ORDERS", "ORDERS_CUST_IX", "NONUNIQUE", "CUSTOMER_ID", 1),
            ("CUSTOMERS", "CUSTOMERS_PK", "UNIQUE", "CUSTOMER_ID", 1),
        ],
    ),
    "partitions": FakeResult(["TABLE_NAME", "COLUMN_NAME", "COLUMN_POSITION"],
                             [("ORDERS", "ORDER_DATE", 1)]),
    "stats": FakeResult(["TABLE_NAME", "NUM_ROWS", "LAST_ANALYZED"],
                        [("ORDERS", 5_000_000, "2026-06-01"), ("CUSTOMERS", 1200, None)]),
    "unique": FakeResult(["TABLE_NAME", "COLUMN_NAME"], [("CUSTOMERS", "NAME")]),
}


class FakeClient:
    def __init__(self, fail_on=()):
        self.fail_on = set(fail_on)

    def run_select(self, sql, limits=None, binds=None):
        key = _route(sql)
        if key in self.fail_on:
            raise RuntimeError(f"ORA-00942: {key} view not visible")
        return _RESPONSES[key]


def _columns_dict_rows():
    cols = _RESPONSES["columns"].columns
    return [dict(zip(cols, r)) for r in _RESPONSES["columns"].rows]


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def test_columns_sql_selects_profiling_fields():
    sql, binds = columns_sql("AOR_DEMO", "%")
    assert "nullable" in sql and "data_precision" in sql
    assert binds == {"owner": "AOR_DEMO", "table_like": "%"}


@pytest.mark.parametrize("builder, needle", [
    (indexes_sql, "all_ind_columns"),
    (partition_keys_sql, "all_part_key_columns"),
    (table_stats_sql, "all_tables"),
    (unique_constraints_sql, "constraint_type = 'u'"),
])
def test_profiling_builders_are_bound_selects(builder, needle):
    sql, binds = builder("AOR_DEMO", "ORD%")
    assert needle in sql.lower()
    assert binds == {"owner": "AOR_DEMO", "table_like": "ORD%"}
    assert sql.lower().lstrip().startswith("select")


# --------------------------------------------------------------------------- #
# Mappers
# --------------------------------------------------------------------------- #
def test_build_columns_reads_nullability_and_precision():
    schema = build_columns(_columns_dict_rows())
    cols = {c.column_name: c for c in schema.tables["ORDERS"].columns}
    assert cols["ORDER_ID"].nullable is False
    assert cols["CUSTOMER_ID"].nullable is True
    assert cols["AMOUNT"].data_precision == 10 and cols["AMOUNT"].data_scale == 2


def test_apply_indexes_marks_leading_column_and_builds_index_list():
    schema = build_columns(_columns_dict_rows())
    rows = [dict(zip(_RESPONSES["indexes"].columns, r)) for r in _RESPONSES["indexes"].rows]
    apply_indexes(schema, rows)
    orders = schema.tables["ORDERS"]
    assert len(orders.indexes) == 2
    cust = {c.column_name: c for c in orders.columns}["CUSTOMER_ID"]
    assert cust.is_indexed is True  # leading column of ORDERS_CUST_IX


def test_apply_table_stats_flags_staleness():
    schema = build_columns(_columns_dict_rows())
    rows = [dict(zip(_RESPONSES["stats"].columns, r)) for r in _RESPONSES["stats"].rows]
    apply_table_stats(schema, rows)
    assert schema.tables["ORDERS"].row_count_estimate == 5_000_000
    assert schema.tables["ORDERS"].stats_stale is False
    assert schema.tables["CUSTOMERS"].stats_stale is True  # NULL last_analyzed


def test_derive_fk_cardinality_sets_fan_out():
    schema = build_columns(_columns_dict_rows())
    apply_primary_keys(schema, [dict(zip(_RESPONSES["pk"].columns, r)) for r in _RESPONSES["pk"].rows])
    apply_foreign_keys(schema, [dict(zip(_RESPONSES["fk"].columns, r)) for r in _RESPONSES["fk"].rows])
    derive_fk_cardinality(schema)
    rel = schema.relationships[0]
    assert rel.fan_out is True and rel.relationship_type == "many-to-one"


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def test_profile_schema_enriches_all_channels():
    res = profile_schema(FakeClient(), "aor_demo", "%")
    assert res.coverage == {
        "columns": True, "primary_keys": True, "foreign_keys": True,
        "indexes": True, "partitions": True, "stats": True, "unique": True,
    }
    orders = res.schema.tables["ORDERS"]
    assert orders.partition_keys == ["ORDER_DATE"]
    assert orders.row_count_estimate == 5_000_000
    cust_col = {c.column_name: c for c in orders.columns}["CUSTOMER_ID"]
    assert cust_col.is_indexed is True
    assert res.schema.relationships[0].fan_out is True


def test_profile_schema_degrades_when_a_view_is_unavailable():
    res = profile_schema(FakeClient(fail_on={"indexes"}), "aor_demo", "%")
    assert res.coverage["indexes"] is False
    assert any("Indexes unavailable" in w for w in res.warnings)
    # other layers still applied despite the index failure
    assert res.coverage["stats"] is True
    assert res.schema.tables["ORDERS"].partition_keys == ["ORDER_DATE"]


# --------------------------------------------------------------------------- #
# Serialization (additive, back-compatible)
# --------------------------------------------------------------------------- #
def test_serialization_round_trip_preserves_enriched_metadata():
    res = profile_schema(FakeClient(), "aor_demo", "%")
    restored = schema_from_dict(schema_to_dict(res.schema))
    orders = restored.tables["ORDERS"]
    assert orders.partition_keys == ["ORDER_DATE"]
    assert orders.row_count_estimate == 5_000_000
    assert len(orders.indexes) == 2
    cust_col = {c.column_name: c for c in orders.columns}["CUSTOMER_ID"]
    assert cust_col.is_indexed is True
    assert restored.relationships[0].fan_out is True


def test_schema_from_dict_back_compat_without_table_meta():
    # A pre-Phase-11 record: no table_meta, columns lack the new keys.
    legacy = {
        "tables": {"ORDERS": [{"column_name": "ORDER_ID", "is_primary_key": True}]},
        "relationships": [{"from_table": "ORDERS", "from_column": "CUSTOMER_ID",
                           "to_table": "CUSTOMERS", "to_column": "CUSTOMER_ID"}],
    }
    schema = schema_from_dict(legacy)
    orders = schema.tables["ORDERS"]
    assert orders.indexes == [] and orders.partition_keys == []
    assert orders.row_count_estimate is None
    col = orders.columns[0]
    assert col.nullable is None and col.is_indexed is False
    assert schema.relationships[0].fan_out is False
