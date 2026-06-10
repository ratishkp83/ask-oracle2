from __future__ import annotations

from typing import List, Set

import sqlglot
from sqlglot import exp

from src.core.llm.base import Confidence
from src.schema import Schema


def _schema_identifiers(schema: Schema) -> tuple[Set[str], Set[str]]:
    tables = {t.lower() for t in schema.list_tables()}
    columns: Set[str] = set()
    for t in schema.list_tables():
        for c in schema.list_columns(t):
            columns.add(c.lower())
    return tables, columns


def assess_confidence(sql: str, schema: Schema) -> Confidence:
    """Deterministic, coarse confidence — NOT a correctness guarantee.

    Signals: SQL parses; referenced tables/columns resolve against the uploaded
    schema (excluding CTE names and SELECT aliases). High = everything resolves;
    Low = unknown table(s) or no schema; Medium = only unknown column(s).
    """
    known_tables, known_columns = _schema_identifiers(schema)
    if not known_tables:
        return Confidence(level="Low", reasons=["No schema loaded to validate against."])

    try:
        parsed = sqlglot.parse_one(sql, read="oracle")
    except Exception:
        return Confidence(level="Low", reasons=["Generated SQL did not parse."])
    if parsed is None:
        return Confidence(level="Low", reasons=["Generated SQL did not parse."])

    cte_names = {c.alias_or_name.lower() for c in parsed.find_all(exp.CTE) if c.alias_or_name}
    alias_names = {a.alias_or_name.lower() for a in parsed.find_all(exp.Alias) if a.alias_or_name}

    ref_tables = {t.name.lower() for t in parsed.find_all(exp.Table) if t.name}
    ref_columns = {c.name.lower() for c in parsed.find_all(exp.Column) if c.name}

    unknown_tables = sorted(t for t in ref_tables if t not in known_tables and t not in cte_names)
    unknown_columns = sorted(
        c for c in ref_columns if c not in known_columns and c not in alias_names and c not in cte_names
    )

    reasons: List[str] = []
    if unknown_tables:
        reasons.append(f"Tables not in schema: {', '.join(unknown_tables)}")
    if unknown_columns:
        reasons.append(f"Columns not in schema: {', '.join(unknown_columns)}")

    if not unknown_tables and not unknown_columns:
        return Confidence(level="High", reasons=["All referenced tables and columns resolve against the schema."])
    if unknown_tables:
        return Confidence(level="Low", reasons=reasons)
    return Confidence(level="Medium", reasons=reasons)
