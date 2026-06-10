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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import SafetyLimits
from src.schema import ColumnDefinition, RelationshipDefinition, Schema, TableDefinition

Binds = Dict[str, Any]


# --------------------------------------------------------------------------- #
# SQL builders — each returns (sql, binds); all are read-only SELECTs.
# --------------------------------------------------------------------------- #
def columns_sql(owner: str, table_like: str) -> Tuple[str, Binds]:
    sql = (
        "SELECT owner, table_name, column_name, data_type, column_id "
        "FROM all_tab_columns "
        "WHERE owner = :owner AND table_name LIKE :table_like "
        "ORDER BY table_name, column_id"
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


def build_columns(rows: List[Dict[str, Any]]) -> Schema:
    schema = Schema()
    for r in rows:
        tname, cname = _s(r.get("TABLE_NAME")), _s(r.get("COLUMN_NAME"))
        if not tname or not cname:
            continue
        dtype = r.get("DATA_TYPE")
        col = ColumnDefinition(
            table_name=tname, column_name=cname, data_type=_s(dtype) or None
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

    try:
        sql, binds = primary_keys_sql(owner, table_like)
        pk_result = client.run_select(sql, limits=limits, binds=binds)
        truncated = truncated or bool(getattr(pk_result, "truncated", False))
        apply_primary_keys(schema, _rows_as_dicts(pk_result))
    except Exception as exc:  # noqa: BLE001 - constraint views may not be visible
        warnings.append(f"Primary keys unavailable ({exc}).")

    try:
        sql, binds = foreign_keys_sql(owner, table_like)
        fk_result = client.run_select(sql, limits=limits, binds=binds)
        truncated = truncated or bool(getattr(fk_result, "truncated", False))
        apply_foreign_keys(schema, _rows_as_dicts(fk_result))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Foreign keys unavailable ({exc}).")

    return IntrospectionResult(schema=schema, warnings=warnings, truncated=truncated)
