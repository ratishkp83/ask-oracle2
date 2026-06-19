"""PostgreSQL schema introspection (Phase 11 multi-engine MVP).

The Postgres counterpart to :mod:`src.core.introspection` (Oracle): builds a
:class:`~src.schema.Schema` from ``information_schema`` — columns + PK + FK — using
the **same** ``IntrospectionResult`` shape so the API/UI stay engine-agnostic. Every
query is a SELECT through the engine's read-only chokepoint (``client.run_select``),
bind-parameterized and **privilege-degrading** (a missing constraint view yields a
generic warning, not a failure). Identifiers are lower-case (Postgres convention).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.config import SafetyLimits
from src.core.introspection import IntrospectionResult
from src.schema import ColumnDefinition, RelationshipDefinition, Schema, TableDefinition

logger = logging.getLogger("ask_oracle.introspection")


def _int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _rows(result: Any) -> List[Dict[str, Any]]:
    cols = [str(c).lower() for c in result.columns]
    return [dict(zip(cols, row)) for row in result.rows]


_COLUMNS_SQL = (
    "SELECT table_name, column_name, data_type, is_nullable, "
    "character_maximum_length, numeric_precision, numeric_scale "
    "FROM information_schema.columns WHERE table_schema = :schema "
    "ORDER BY table_name, ordinal_position"
)

_PK_SQL = (
    "SELECT kcu.table_name AS table_name, kcu.column_name AS column_name "
    "FROM information_schema.table_constraints tc "
    "JOIN information_schema.key_column_usage kcu "
    "ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
    "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = :schema"
)

_FK_SQL = (
    "SELECT kcu.table_name AS from_table, kcu.column_name AS from_column, "
    "ccu.table_name AS to_table, ccu.column_name AS to_column "
    "FROM information_schema.table_constraints tc "
    "JOIN information_schema.key_column_usage kcu "
    "ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
    "JOIN information_schema.constraint_column_usage ccu "
    "ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema "
    "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = :schema"
)


def introspect_schema_postgres(
    client: Any,
    schema: str = "public",
    limits: Optional[SafetyLimits] = None,
) -> IntrospectionResult:
    """Introspect a Postgres schema into a names-only :class:`Schema` (invariant 3)."""
    schema_name = (schema or "public").strip().lower()
    if not schema_name:
        raise ValueError("A schema is required for introspection.")

    binds = {"schema": schema_name}
    warnings: List[str] = []
    truncated = False

    col_result = client.run_select(_COLUMNS_SQL, limits=limits, binds=binds)
    truncated = truncated or bool(getattr(col_result, "truncated", False))
    out = Schema()
    for r in _rows(col_result):
        tname = str(r.get("table_name") or "").strip()
        cname = str(r.get("column_name") or "").strip()
        if not tname or not cname:
            continue
        out.tables.setdefault(tname, TableDefinition(name=tname, columns=[])).columns.append(
            ColumnDefinition(
                table_name=tname,
                column_name=cname,
                data_type=(str(r.get("data_type")).strip() if r.get("data_type") else None),
                nullable=(str(r.get("is_nullable")).upper() == "YES"),
                data_length=_int(r.get("character_maximum_length")),
                data_precision=_int(r.get("numeric_precision")),
                data_scale=_int(r.get("numeric_scale")),
            )
        )

    if not out.tables:
        warnings.append(f"No tables found in schema '{schema_name}'.")
        return IntrospectionResult(schema=out, warnings=warnings, truncated=truncated)

    index = {(t.name, c.column_name): c for t in out.tables.values() for c in t.columns}

    try:
        pk_result = client.run_select(_PK_SQL, limits=limits, binds=binds)
        for r in _rows(pk_result):
            col = index.get((str(r.get("table_name") or ""), str(r.get("column_name") or "")))
            if col is not None:
                col.is_primary_key = True
    except Exception as exc:  # noqa: BLE001 - constraint views may not be visible
        logger.info("Postgres primary-key introspection unavailable for %s: %s", schema_name, exc)
        warnings.append("Primary keys unavailable for this account.")

    try:
        fk_result = client.run_select(_FK_SQL, limits=limits, binds=binds)
        for r in _rows(fk_result):
            ft, fc = str(r.get("from_table") or ""), str(r.get("from_column") or "")
            tt, tc = str(r.get("to_table") or ""), str(r.get("to_column") or "")
            if not (ft and fc and tt and tc):
                continue
            col = index.get((ft, fc))
            if col is not None:
                col.is_foreign_key = True
                col.references_table = tt
                col.references_column = tc
            out.relationships.append(
                RelationshipDefinition(
                    from_table=ft, from_column=fc, to_table=tt, to_column=tc,
                    relationship_type="many-to-one",
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.info("Postgres foreign-key introspection unavailable for %s: %s", schema_name, exc)
        warnings.append("Foreign keys unavailable for this account.")

    return IntrospectionResult(schema=out, warnings=warnings, truncated=truncated)
