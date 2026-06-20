"""Phase 11 / B3b — derived profiling outputs: Optimization Advisory (D-K),
setup readiness gate (D-L), value-domain capture (Channel B), and store update.
"""
from __future__ import annotations

import pytest

from src.core.introspection import capture_value_domains, value_domain_sql
from src.core.profiling import build_optimization_advisory, compute_readiness
from src.core.schema_store import InMemorySchemaStore
from src.schema import schema_from_dict


def _schema(*, indexed=False, partitioned=False, stale=True):
    d = {
        "tables": {
            "ORDERS": [
                {"column_name": "ORDER_ID", "is_primary_key": True, "is_indexed": True},
                {"column_name": "CUSTOMER_ID", "is_foreign_key": True,
                 "references_table": "CUSTOMERS", "references_column": "CUSTOMER_ID",
                 "is_indexed": indexed},
            ],
            "CUSTOMERS": [{"column_name": "CUSTOMER_ID", "is_primary_key": True}],
        },
        "table_meta": {
            "ORDERS": {"indexes": [], "partition_keys": (["ORDER_DATE"] if partitioned else []),
                       "row_count_estimate": 5_000_000, "stats_stale": stale},
            "CUSTOMERS": {"indexes": [], "partition_keys": [],
                          "row_count_estimate": 1200, "stats_stale": False},
        },
        "relationships": [{"from_table": "ORDERS", "from_column": "CUSTOMER_ID",
                           "to_table": "CUSTOMERS", "to_column": "CUSTOMER_ID"}],
    }
    return schema_from_dict(d)


# --------------------------------------------------------------------------- #
# Optimization Advisory (D-K)
# --------------------------------------------------------------------------- #
def test_advisory_flags_unindexed_fk_first():
    adv = build_optimization_advisory(_schema(indexed=False, partitioned=False, stale=True))
    kinds = [s.kind for s in adv]
    assert "index_fk" in kinds
    assert adv[0].kind == "index_fk"  # highest severity first
    fk = next(s for s in adv if s.kind == "index_fk")
    assert fk.target == "ORDERS.CUSTOMER_ID" and "CREATE INDEX" in fk.ddl_candidate


def test_advisory_quiet_when_indexed_partitioned_and_fresh():
    adv = build_optimization_advisory(_schema(indexed=True, partitioned=True, stale=False))
    kinds = {s.kind for s in adv}
    assert "index_fk" not in kinds and "partition" not in kinds and "stats" not in kinds


def test_advisory_flags_large_unpartitioned_and_stale_stats():
    adv = build_optimization_advisory(_schema(indexed=True, partitioned=False, stale=True))
    kinds = {s.kind for s in adv}
    assert "partition" in kinds and "stats" in kinds


def test_advisory_never_emits_executable_index_or_partition_dml_without_marker():
    # The product advises but never executes; partition/stats are comment candidates.
    adv = build_optimization_advisory(_schema(indexed=True, partitioned=False, stale=True))
    part = next(s for s in adv if s.kind == "partition")
    assert part.ddl_candidate.strip().startswith("--")


# --------------------------------------------------------------------------- #
# Readiness gate (D-L) — soft-block default
# --------------------------------------------------------------------------- #
_FULL_COVERAGE = {"primary_keys": True, "foreign_keys": True, "indexes": True,
                  "partitions": True, "stats": True}
_HUMAN = {"glossary": {"DT_FLG": "date flag"}, "value_domains": {"ORDERS.STATUS": [{"code": "A"}]}}


def test_readiness_ready_when_everything_present():
    r = compute_readiness(_schema(), _HUMAN, _FULL_COVERAGE, enforcement="soft")
    assert r.state == "ready" and r.usable is True


def test_readiness_not_optimized_but_usable_under_soft_block():
    r = compute_readiness(_schema(), {}, _FULL_COVERAGE, enforcement="soft")
    assert r.state == "not_optimized" and r.usable is True
    missing = {c.key for c in r.checklist if c.status == "missing"}
    assert {"glossary", "value_domains"} <= missing


def test_readiness_hard_block_blocks_when_not_ready():
    r = compute_readiness(_schema(), {}, _FULL_COVERAGE, enforcement="hard")
    assert r.state == "not_optimized" and r.usable is False


def test_readiness_incomplete_with_no_tables():
    r = compute_readiness(schema_from_dict({"tables": {}}), {}, {}, enforcement="hard")
    assert r.state == "incomplete" and r.usable is False


def test_readiness_acknowledged_unavailable_does_not_block_ready():
    cov = {**_FULL_COVERAGE, "indexes": False}
    sem = {**_HUMAN, "acknowledged": ["indexes"]}
    r = compute_readiness(_schema(), sem, cov, enforcement="soft")
    idx = next(c for c in r.checklist if c.key == "indexes")
    assert idx.status == "acknowledged" and r.state == "ready"


# --------------------------------------------------------------------------- #
# Value-domain capture (Channel B) — bounded, server-side only
# --------------------------------------------------------------------------- #
class _VR:
    def __init__(self, columns, rows):
        self.columns, self.rows, self.truncated = columns, rows, False


def test_value_domain_sql_is_a_bounded_select():
    sql, binds = value_domain_sql("AOR_DEMO", "ORDERS", "STATUS", sample_percent=5, cap=10)
    low = sql.lower()
    assert low.startswith("select") and "sample(" in low and "fetch first" in low
    assert binds == {}


def test_value_domain_sql_rejects_unsafe_identifier():
    with pytest.raises(ValueError):
        value_domain_sql("AOR_DEMO", "ORDERS", "X; DROP TABLE Y")


def test_capture_value_domains_collects_codes_and_degrades():
    class Client:
        def run_select(self, sql, limits=None, binds=None):
            if "BAD" in sql:
                raise RuntimeError("ORA-00942")
            return _VR(["CODE", "CNT"], [("A", 100), ("I", 5)])

    domains, warnings = capture_value_domains(
        Client(), "AOR_DEMO", [("ORDERS", "STATUS"), ("ORDERS", "BAD")]
    )
    assert domains["ORDERS.STATUS"]["codes"][0]["code"] == "A"
    assert any("ORDERS.BAD" in w for w in warnings)


# --------------------------------------------------------------------------- #
# Store update (additive semantics/readiness)
# --------------------------------------------------------------------------- #
def test_schema_store_update_sets_semantics_and_readiness():
    store = InMemorySchemaStore()
    rec = store.create("XE", {"tables": {"ORDERS": []}}, source="introspection")
    updated = store.update(rec.id, semantics={"glossary": {"A": "b"}},
                           readiness={"state": "not_optimized"})
    assert updated is not None
    fetched = store.get(rec.id)
    assert fetched.semantics == {"glossary": {"A": "b"}}
    assert fetched.summary().readiness_state == "not_optimized"
    assert store.update("nope", semantics={}) is None
