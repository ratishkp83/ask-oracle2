"""Live schema introspection from Oracle data-dictionary views (Phase 5, ADR-010).

Builds a :class:`~src.schema.Schema` from ``ALL_TAB_COLUMNS`` +
``ALL_CONSTRAINTS``/``ALL_CONS_COLUMNS``. Every query is **SELECT-only**, runs
through ``OracleClient.run_select`` (so it passes ``assert_safe_select`` first) under
the required least-privilege read-only account, is **bind-parameterized**
(no string interpolation — ADR-007), and is **scoped** (owner + name filter) and
**capped** (``SafetyLimits``). There is **no new execution path** to the database.

Split for testability: SQL **builders** (return ``(sql, binds)``), pure **mappers**
(dictionary rows → ``Schema``), and an **orchestrator** that calls ``run_select`` and
degrades gracefully when constraint views are not visible to the account.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import SafetyLimits
from src.schema import (
    ColumnDefinition,
    IndexDefinition,
    RelationshipDefinition,
    Schema,
    TableDefinition,
)

logger = logging.getLogger("ask_oracle.introspection")

Binds = Dict[str, Any]


# --------------------------------------------------------------------------- #
# SQL builders — each returns (sql, binds); all are read-only SELECTs.
# --------------------------------------------------------------------------- #
def columns_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT owner, table_name, column_name, data_type, column_id, "
        "nullable, data_length, data_precision, data_scale "
        "FROM all_tab_columns "
        "WHERE owner = :owner AND table_name LIKE :table_like "
        "ORDER BY table_name, column_id"
    )
    return sql, {"owner": owner, "table_like": table_like}


# --------------------------------------------------------------------------- #
# Phase 11 profiling builders (Channel A — structure/statistics only; ADR-028).
# All read-only SELECTs over ALL_* views; bind-parameterized; privilege-degrading.
# --------------------------------------------------------------------------- #
def indexes_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT i.table_name, i.index_name, i.uniqueness, "
        "ic.column_name, ic.column_position "
        "FROM all_indexes i "
        "JOIN all_ind_columns ic ON ic.index_owner = i.owner AND ic.index_name = i.index_name "
        "WHERE i.owner = :owner AND i.table_name LIKE :table_like "
        "ORDER BY i.table_name, i.index_name, ic.column_position"
    )
    return sql, {"owner": owner, "table_like": table_like}


def partition_keys_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT name AS table_name, column_name, column_position "
        "FROM all_part_key_columns "
        "WHERE owner = :owner AND object_type = 'TABLE' AND name LIKE :table_like "
        "ORDER BY name, column_position"
    )
    return sql, {"owner": owner, "table_like": table_like}


def table_stats_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT table_name, num_rows, last_analyzed "
        "FROM all_tables "
        "WHERE owner = :owner AND table_name LIKE :table_like"
    )
    return sql, {"owner": owner, "table_like": table_like}


def unique_constraints_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT cc.table_name, cc.column_name "
        "FROM all_constraints c "
        "JOIN all_cons_columns cc ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name "
        "WHERE c.owner = :owner AND c.constraint_type = 'U' AND cc.table_name LIKE :table_like"
    )
    return sql, {"owner": owner, "table_like": table_like}


def primary_keys_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT cc.table_name, cc.column_name "
        "FROM all_constraints c "
        "JOIN all_cons_columns cc ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name "
        "WHERE c.owner = :owner AND c.constraint_type = 'P' AND cc.table_name LIKE :table_like"
    )
    return sql, {"owner": owner, "table_like": table_like}


def foreign_keys_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT fcc.table_name AS from_table, fcc.column_name AS from_column, "
        "rcc.table_name AS to_table, rcc.column_name AS to_column "
        "FROM all_constraints fc "
        "JOIN all_cons_columns fcc ON fcc.owner = fc.owner AND fcc.constraint_name = fc.constraint_name "
        "JOIN all_cons_columns rcc ON rcc.owner = fc.r_owner "
        "AND rcc.constraint_name = fc.r_constraint_name AND rcc.position = fcc.position "
        "WHERE fc.owner = :owner AND fc.constraint_type = 'R' AND fcc.table_name LIKE :table_like"
    )
    return sql, {"owner": owner, "table_like": table_like}


# --------------------------------------------------------------------------- #
# Mappers — pure functions over dictionary rows (keys upper-cased).
# --------------------------------------------------------------------------- #
def _s(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _opt_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_columns(rows: List[Dict[str, Any]]) -> Schema:
    schema = Schema()
    for r in rows:
        tname, cname = _s(r.get("TABLE_NAME")), _s(r.get("COLUMN_NAME"))
        if not tname or not cname:
            continue
        dtype = r.get("DATA_TYPE")
        nullable_raw = r.get("NULLABLE")  # 'Y' / 'N' in ALL_TAB_COLUMNS; absent for uploads
        col = ColumnDefinition(
            table_name=tname,
            column_name=cname,
            data_type=_s(dtype) or None,
            nullable=(_s(nullable_raw).upper() == "Y") if nullable_raw is not None else None,
            data_length=_opt_int(r.get("DATA_LENGTH")),
            data_precision=_opt_int(r.get("DATA_PRECISION")),
            data_scale=_opt_int(r.get("DATA_SCALE")),
        )
        schema.tables.setdefault(tname, TableDefinition(name=tname, columns=[])).columns.append(col)
    return schema


def _column_index(schema: Schema) -> Dict[Tuple[str, str], ColumnDefinition]:
    return {(t.name, c.column_name): c for t in schema.tables.values() for c in t.columns}


def apply_primary_keys(schema: Schema, rows: List[Dict[str, Any]]) -> Schema:
    index = _column_index(schema)
    for r in rows:
        col = index.get((_s(r.get("TABLE_NAME")), _s(r.get("COLUMN_NAME"))))
        if col is not None:
            col.is_primary_key = True
    return schema


def apply_foreign_keys(schema: Schema, rows: List[Dict[str, Any]]) -> Schema:
    index = _column_index(schema)
    for r in rows:
        ft, fc = _s(r.get("FROM_TABLE")), _s(r.get("FROM_COLUMN"))
        tt, tc = _s(r.get("TO_TABLE")), _s(r.get("TO_COLUMN"))
        if not (ft and fc and tt and tc):
            continue
        col = index.get((ft, fc))
        if col is not None:
            col.is_foreign_key = True
            col.references_table = tt
            col.references_column = tc
        schema.relationships.append(
            RelationshipDefinition(
                from_table=ft, from_column=fc, to_table=tt, to_column=tc,
                relationship_type="many-to-one",
            )
        )
    return schema


# --------------------------------------------------------------------------- #
# Phase 11 mappers (Channel A). Pure functions; tolerant of partial rows.
# --------------------------------------------------------------------------- #
def apply_indexes(schema: Schema, rows: List[Dict[str, Any]]) -> Schema:
    """Group index rows into per-table IndexDefinitions; mark leading columns indexed."""
    index = _column_index(schema)
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in rows:
        t, name, col = _s(r.get("TABLE_NAME")), _s(r.get("INDEX_NAME")), _s(r.get("COLUMN_NAME"))
        if not (t and name and col):
            continue
        g = grouped.setdefault(
            (t, name),
            {"is_unique": _s(r.get("UNIQUENESS")).upper() == "UNIQUE", "cols": []},
        )
        pos = _opt_int(r.get("COLUMN_POSITION"))
        g["cols"].append((pos if pos is not None else len(g["cols"]) + 1, col))
    for (t, name), g in grouped.items():
        table = schema.tables.get(t)
        if table is None:
            continue
        ordered = [c for _, c in sorted(g["cols"], key=lambda x: x[0])]
        table.indexes.append(IndexDefinition(name=name, columns=ordered, is_unique=g["is_unique"]))
        if ordered:  # the leading column is the one that helps equality/range predicates
            lead = index.get((t, ordered[0]))
            if lead is not None:
                lead.is_indexed = True
    return schema


def apply_partition_keys(schema: Schema, rows: List[Dict[str, Any]]) -> Schema:
    for r in rows:
        t, col = _s(r.get("TABLE_NAME")), _s(r.get("COLUMN_NAME"))
        if not (t and col):
            continue
        table = schema.tables.get(t)
        if table is not None and col not in table.partition_keys:
            table.partition_keys.append(col)
    return schema


def apply_table_stats(schema: Schema, rows: List[Dict[str, Any]]) -> Schema:
    for r in rows:
        table = schema.tables.get(_s(r.get("TABLE_NAME")))
        if table is None:
            continue
        num_rows = _opt_int(r.get("NUM_ROWS"))
        table.row_count_estimate = num_rows
        # Stale/absent stats: NUM_ROWS is only as good as the last GATHER_STATS.
        table.stats_stale = num_rows is None or r.get("LAST_ANALYZED") is None
    return schema


def apply_unique(schema: Schema, rows: List[Dict[str, Any]]) -> Schema:
    index = _column_index(schema)
    for r in rows:
        col = index.get((_s(r.get("TABLE_NAME")), _s(r.get("COLUMN_NAME"))))
        if col is not None:
            col.is_unique = True
    return schema


def derive_fk_cardinality(schema: Schema) -> Schema:
    """Set ``fan_out`` on each relationship: a join fans out unless the child
    (referencing) column is itself unique/PK (then it is 1:1)."""
    index = _column_index(schema)
    for rel in schema.relationships:
        child = index.get((rel.from_table, rel.from_column))
        child_unique = bool(child and (child.is_primary_key or child.is_unique))
        rel.fan_out = not child_unique
        rel.relationship_type = "one-to-one" if child_unique else "many-to-one"
    return schema


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
@dataclass
class IntrospectionResult:
    schema: Schema
    warnings: List[str] = field(default_factory=list)
    truncated: bool = False


def _rows_as_dicts(result: Any) -> List[Dict[str, Any]]:
    cols = [str(c).upper() for c in result.columns]
    return [dict(zip(cols, row)) for row in result.rows]


def introspect_schema(
    client: Any,
    owner: str,
    table_like: str = "%",
    limits: Optional[SafetyLimits] = None,
) -> IntrospectionResult:
    """Introspect ``owner``'s tables (optionally name-filtered) into a ``Schema``.

    ``client`` is an :class:`~src.db.OracleClient` (or test double) exposing
    ``run_select(sql, limits=..., binds=...)``. Owner/filter are upper-cased
    (Oracle dictionary names are upper-case). Constraint-view failures degrade
    gracefully to a columns-only schema with a warning.
    """
    owner = _s(owner).upper()
    if not owner:
        raise ValueError("An owner/schema is required for introspection.")
    table_like = (_s(table_like) or "%").upper()

    warnings: List[str] = []
    truncated = False

    sql, binds = columns_sql(owner, table_like)
    col_result = client.run_select(sql, limits=limits, binds=binds)
    truncated = truncated or bool(getattr(col_result, "truncated", False))
    schema = build_columns(_rows_as_dicts(col_result))
    if not schema.tables:
        warnings.append(f"No tables found for owner '{owner}' matching '{table_like}'.")
        return IntrospectionResult(schema=schema, warnings=warnings, truncated=truncated)

    # Warnings are returned to the client (a 200 success payload), so they carry a
    # GENERIC message only — the raw driver exception (which can embed host/service/
    # object names) is logged server-side, never echoed (review F-2).
    try:
        sql, binds = primary_keys_sql(owner, table_like)
        pk_result = client.run_select(sql, limits=limits, binds=binds)
        truncated = truncated or bool(getattr(pk_result, "truncated", False))
        apply_primary_keys(schema, _rows_as_dicts(pk_result))
    except Exception as exc:  # noqa: BLE001 - constraint views may not be visible
        logger.info("Primary-key introspection unavailable for %s: %s", owner, exc)
        warnings.append("Primary keys unavailable for this account.")

    try:
        sql, binds = foreign_keys_sql(owner, table_like)
        fk_result = client.run_select(sql, limits=limits, binds=binds)
        truncated = truncated or bool(getattr(fk_result, "truncated", False))
        apply_foreign_keys(schema, _rows_as_dicts(fk_result))
    except Exception as exc:  # noqa: BLE001
        logger.info("Foreign-key introspection unavailable for %s: %s", owner, exc)
        warnings.append("Foreign keys unavailable for this account.")

    return IntrospectionResult(schema=schema, warnings=warnings, truncated=truncated)


# --------------------------------------------------------------------------- #
# Phase 11 profiling orchestrator (ADR-028). Layers indexes/partitions/stats/
# unique/cardinality on top of introspect_schema; each step degrades gracefully.
# --------------------------------------------------------------------------- #
@dataclass
class ProfileResult:
    schema: Schema
    warnings: List[str] = field(default_factory=list)
    truncated: bool = False
    coverage: Dict[str, bool] = field(default_factory=dict)


def profile_schema(
    client: Any,
    owner: str,
    table_like: str = "%",
    limits: Optional[SafetyLimits] = None,
) -> ProfileResult:
    """Profile ``owner``'s tables into an enriched :class:`Schema` (Channel A).

    Builds the base schema (columns + PK + FK) via :func:`introspect_schema`, then
    layers index, partition-key, table-statistic, and unique-constraint metadata,
    and derives FK cardinality. Every layer is **SELECT-only through the chokepoint**
    and **privilege-degrading**: a view the read-only account cannot see yields a
    generic warning and ``coverage[step] = False`` (the raw error is logged only).
    Value domains / business semantics (Channel B) are captured separately and are
    **never** part of this Schema (invariant 3).
    """
    base = introspect_schema(client, owner, table_like, limits)
    schema = base.schema
    warnings = list(base.warnings)
    truncated = base.truncated
    coverage: Dict[str, bool] = {
        "columns": bool(schema.tables),
        "primary_keys": not any("Primary keys unavailable" in w for w in warnings),
        "foreign_keys": not any("Foreign keys unavailable" in w for w in warnings),
    }
    if not schema.tables:
        return ProfileResult(schema=schema, warnings=warnings, truncated=truncated, coverage=coverage)

    owner_u = _s(owner).upper()
    table_like_u = (_s(table_like) or "%").upper()
    steps = (
        ("Indexes", indexes_sql, apply_indexes, "indexes"),
        ("Partition keys", partition_keys_sql, apply_partition_keys, "partitions"),
        ("Table statistics", table_stats_sql, apply_table_stats, "stats"),
        ("Unique constraints", unique_constraints_sql, apply_unique, "unique"),
    )
    for label, builder, mapper, cov_key in steps:
        try:
            sql, binds = builder(owner_u, table_like_u)
            res = client.run_select(sql, limits=limits, binds=binds)
            truncated = truncated or bool(getattr(res, "truncated", False))
            mapper(schema, _rows_as_dicts(res))
            coverage[cov_key] = True
        except Exception as exc:  # noqa: BLE001 - the view may not be visible to the account
            logger.info("%s profiling unavailable for %s: %s", label, owner_u, exc)
            warnings.append(f"{label} unavailable for this account.")
            coverage[cov_key] = False

    derive_fk_cardinality(schema)
    return ProfileResult(schema=schema, warnings=warnings, truncated=truncated, coverage=coverage)
