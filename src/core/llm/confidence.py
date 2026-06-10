from __future__ import annotations

from typing import Dict, List, Set, Tuple

import sqlglot
from sqlglot import exp

from src.core.llm.base import Confidence
from src.schema import Schema


def _columns_by_table(schema: Schema) -> Dict[str, Set[str]]:
    return {t.lower(): {c.lower() for c in schema.list_columns(t)} for t in schema.list_tables()}


def assess_confidence(sql: str, schema: Schema) -> Confidence:
    """Deterministic, coarse confidence — NOT a correctness guarantee.

    Signals (per design §6):
    - SQL parses.
    - Referenced tables resolve against the schema (excluding CTE names).
    - Each referenced column resolves against *its* table (qualified) or any
      referenced table (unqualified) — not the whole schema (fixes F5).
    - JOIN predicates are backed by a known relationship (fixes F1). If joins are
      present but no relationship metadata exists, confidence is capped at Medium
      (we cannot claim "joins known").

    High = everything resolves and joins are consistent; Low = unknown table or a
    join predicate not backed by a relationship; Medium = unknown column, or
    joins present but unverifiable.
    """
    cols_by_table = _columns_by_table(schema)
    if not cols_by_table:
        return Confidence(level="Low", reasons=["No schema loaded to validate against."])

    try:
        parsed = sqlglot.parse_one(sql, read="oracle")
    except Exception:
        return Confidence(level="Low", reasons=["Generated SQL did not parse."])
    if parsed is None:
        return Confidence(level="Low", reasons=["Generated SQL did not parse."])

    known_tables = set(cols_by_table.keys())
    cte_names = {c.alias_or_name.lower() for c in parsed.find_all(exp.CTE) if c.alias_or_name}
    alias_names = {a.alias_or_name.lower() for a in parsed.find_all(exp.Alias) if a.alias_or_name}

    # alias/name -> real table name
    alias_to_table: Dict[str, str] = {}
    ref_real_tables: Set[str] = set()
    for t in parsed.find_all(exp.Table):
        real = (t.name or "").lower()
        if not real:
            continue
        ref_real_tables.add(real)
        alias_to_table[real] = real
        if t.alias:
            alias_to_table[t.alias.lower()] = real

    unknown_tables = sorted(t for t in ref_real_tables if t not in known_tables and t not in cte_names)

    # --- column resolution (per-table) ---
    unknown_columns: List[str] = []
    ref_known_tables = [t for t in ref_real_tables if t in cols_by_table]
    for col in parsed.find_all(exp.Column):
        name = (col.name or "").lower()
        if not name or name in alias_names:
            continue
        qual = (col.table or "").lower()
        if qual:
            real = alias_to_table.get(qual)
            if real is None or real in cte_names or real not in cols_by_table:
                continue  # unknown/CTE table already accounted for elsewhere
            if name not in cols_by_table[real]:
                unknown_columns.append(f"{real}.{name}")
        else:
            if ref_known_tables and not any(name in cols_by_table[t] for t in ref_known_tables):
                unknown_columns.append(name)
    unknown_columns = sorted(set(unknown_columns))

    # --- join predicate validation ---
    rel_set: Set[Tuple[str, str, str, str]] = set()
    for r in schema.relationships:
        a = (r.from_table.lower(), r.from_column.lower(), r.to_table.lower(), r.to_column.lower())
        rel_set.add(a)
        rel_set.add((a[2], a[3], a[0], a[1]))  # both directions

    join_predicates: List[Tuple[str, str, str, str]] = []
    unbacked: List[str] = []
    for join in parsed.find_all(exp.Join):
        on = join.args.get("on")
        if on is None:
            continue
        for eq in on.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if isinstance(left, exp.Column) and isinstance(right, exp.Column):
                lt = alias_to_table.get((left.table or "").lower())
                rt = alias_to_table.get((right.table or "").lower())
                if lt and rt and lt != rt:
                    pred = (lt, left.name.lower(), rt, right.name.lower())
                    join_predicates.append(pred)
                    if schema.relationships and pred not in rel_set:
                        unbacked.append(f"{pred[0]}.{pred[1]} = {pred[2]}.{pred[3]}")

    # --- combine ---
    reasons: List[str] = []
    if unknown_tables:
        reasons.append(f"Tables not in schema: {', '.join(unknown_tables)}")
    if unknown_columns:
        reasons.append(f"Columns not in schema: {', '.join(unknown_columns)}")
    if unbacked:
        reasons.append(f"Join predicate(s) not backed by a known relationship: {', '.join(sorted(set(unbacked)))}")

    if unknown_tables or unbacked:
        return Confidence(level="Low", reasons=reasons)
    if unknown_columns:
        return Confidence(level="Medium", reasons=reasons)
    if join_predicates and not schema.relationships:
        return Confidence(
            level="Medium",
            reasons=["Join(s) present but no relationship metadata to validate them."],
        )
    return Confidence(
        level="High",
        reasons=["All referenced tables and columns resolve; joins consistent with provided relationships."],
    )
