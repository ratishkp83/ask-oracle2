"""Phase 11 — derived profiling outputs (ADR-028, charter D-K/D-L).

Pure, deterministic functions over an enriched :class:`~src.schema.Schema`
(Channel A) plus optional engineer-supplied semantics (Channel B):

- :func:`build_optimization_advisory` — **advise-only** structural DDL suggestions
  for the implementation engineers/DBA. The app NEVER executes any DDL.
- :func:`compute_readiness` — the setup readiness gate (soft-block default).

No DB access, no LLM, no row data. Semantics (Channel B) is read here only to
decide what is still *missing* at the gate — its values never leave the server.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.schema import Schema

# A table at or above this estimated row count is treated as "large" for advisory
# and plan-steering purposes. NUM_ROWS is a hint (may be stale/null); see ADR-028.
LARGE_TABLE_ROWS = 1_000_000


class Suggestion(BaseModel):
    kind: str  # index_fk | partition | stats | no_pk
    target: str
    ddl_candidate: str
    rationale: str
    tradeoff: str
    severity: str  # high | medium | low


_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def build_optimization_advisory(schema: Schema) -> List[Suggestion]:
    """Rank workload-independent structural suggestions from the profile.

    Advise-only: every item is a *candidate* with its rationale and tradeoff. The
    product never runs DDL — the client's engineers apply (or reject) these under
    their own change control.
    """
    out: List[Suggestion] = []

    # 1) FK/join columns with no leading index — the most common join-perf killer.
    for rel in schema.relationships:
        table = schema.tables.get(rel.from_table)
        if table is None:
            continue
        col = next((c for c in table.columns if c.column_name == rel.from_column), None)
        if col is not None and not col.is_indexed:
            out.append(Suggestion(
                kind="index_fk",
                target=f"{rel.from_table}.{rel.from_column}",
                ddl_candidate=f"CREATE INDEX {rel.from_table}_{rel.from_column}_IX "
                              f"ON {rel.from_table} ({rel.from_column});",
                rationale=f"{rel.from_table}.{rel.from_column} joins to "
                          f"{rel.to_table} but has no leading index — joins on it may full-scan.",
                tradeoff="An index speeds reads but adds write overhead and storage; "
                         "evaluate against the table's write rate.",
                severity="high",
            ))

    for name, table in schema.tables.items():
        big = table.row_count_estimate is not None and table.row_count_estimate >= LARGE_TABLE_ROWS

        # 2) Large unpartitioned tables — scans cannot prune.
        if big and not table.partition_keys:
            out.append(Suggestion(
                kind="partition",
                target=name,
                ddl_candidate=f"-- consider partitioning {name} (e.g. RANGE on a date key) "
                              f"so queries can prune partitions",
                rationale=f"{name} has ~{table.row_count_estimate:,} rows and is not "
                          f"partitioned — large scans read the whole table.",
                tradeoff="Partitioning is a structural change; pick the key against the real query mix.",
                severity="medium",
            ))

        # 3) Missing/stale optimizer stats — the planner guesses.
        if table.stats_stale:
            out.append(Suggestion(
                kind="stats",
                target=name,
                ddl_candidate=f"-- ask the DBA to gather stats: "
                              f"DBMS_STATS.GATHER_TABLE_STATS(owner, '{name}')",
                rationale=f"Optimizer statistics on {name} are missing or stale — "
                          f"the planner may choose a poor plan.",
                tradeoff="Gathering stats is safe but should run off-peak on very large tables.",
                severity="medium" if big else "low",
            ))

        # 4) No primary/unique key detected.
        has_unique = bool(table.primary_keys()) or any(c.is_unique for c in table.columns)
        if not has_unique:
            out.append(Suggestion(
                kind="no_pk",
                target=name,
                ddl_candidate=f"-- no unique/primary key detected on {name}; "
                              f"confirm the natural key with the data owner",
                rationale=f"{name} has no detected PK/unique key — risks duplicate rows "
                          f"and forces defensive DISTINCT.",
                tradeoff="Adding a key is the owner's call; this is informational.",
                severity="low",
            ))

    out.sort(key=lambda s: (_SEVERITY_RANK.get(s.severity, 9), s.kind, s.target))
    return out


# --------------------------------------------------------------------------- #
# Setup readiness gate (D-L) — soft-block default.
# --------------------------------------------------------------------------- #
class CheckItem(BaseModel):
    key: str
    label: str
    status: str  # ok | missing | unavailable | acknowledged
    detail: Optional[str] = None


class Readiness(BaseModel):
    state: str  # ready | not_optimized | incomplete
    usable: bool
    enforcement: str  # soft | hard
    checklist: List[CheckItem]


def _ack(semantics: Dict[str, Any], key: str) -> bool:
    ack = semantics.get("acknowledged") if isinstance(semantics, dict) else None
    return isinstance(ack, list) and key in ack


def compute_readiness(
    schema: Schema,
    semantics: Optional[Dict[str, Any]] = None,
    coverage: Optional[Dict[str, bool]] = None,
    enforcement: str = "soft",
) -> Readiness:
    """Compute the setup-readiness checklist + state.

    Auto checks come from the profiling ``coverage`` map; human checks come from
    engineer-supplied ``semantics`` (glossary / value domains / declared joins).
    "Mandatory" is enforced as *capture-or-explicitly-resolve*: an item the
    account cannot read is ``unavailable`` (or ``acknowledged`` once the engineer
    accepts it). Under the default **soft** enforcement the connection stays
    usable; **hard** blocks until ``state == ready``.
    """
    semantics = semantics or {}
    coverage = coverage or {}
    checks: List[CheckItem] = []

    def add(key, label, ok, *, required=False, detail=None, unavailable=False):
        if ok:
            status = "ok"
        elif _ack(semantics, key):
            status = "acknowledged"
        elif unavailable:
            status = "unavailable"
        else:
            status = "missing"
        checks.append(CheckItem(key=key, label=label, status=status, detail=detail))
        return status, required

    results = []
    results.append(add("columns", "Tables & columns read", bool(schema.tables), required=True))
    results.append(add("primary_keys", "Primary keys", coverage.get("primary_keys", False),
                       unavailable=True))
    results.append(add("foreign_keys", "Foreign keys (catalog)", coverage.get("foreign_keys", False),
                       unavailable=True))
    results.append(add("indexes", "Indexes", coverage.get("indexes", False), unavailable=True))
    results.append(add("partitions", "Partition keys", coverage.get("partitions", False),
                       unavailable=True))
    results.append(add("stats", "Optimizer statistics", coverage.get("stats", False),
                       unavailable=True))

    # Human-supplied (Channel B) — required for an "optimized" connection.
    results.append(add("glossary", "Business glossary for cryptic columns",
                       bool(semantics.get("glossary"))))
    results.append(add("value_domains", "Value-domain labels (e.g. 'A' = Active)",
                       bool(semantics.get("value_domains"))))
    # Joins are required only when the catalog declared none.
    has_joins = bool(schema.relationships) or bool(semantics.get("joins"))
    results.append(add("joins", "Join relationships", has_joins,
                       detail=None if has_joins else "No declared FKs — supply joins manually"))

    statuses = [c.status for c in checks]
    columns_ok = checks[0].status == "ok"
    if not columns_ok:
        state = "incomplete"
    elif any(s in ("missing", "unavailable") for s in statuses):
        state = "not_optimized"
    else:
        state = "ready"

    enforcement = "hard" if enforcement == "hard" else "soft"
    usable = True if enforcement == "soft" else state == "ready"
    return Readiness(state=state, usable=usable, enforcement=enforcement, checklist=checks)
