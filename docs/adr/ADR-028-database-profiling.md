# ADR-028 — Read-only database profiling & enriched metadata (two-channel)

- **Status:** Proposed (B2 — awaiting owner sign-off)
- **Date:** 2026-06-18
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 11 (Pillar 1a, B3)

## Context
On a real client database the model writes *correct-but-slow* or *grain-wrong* SQL because it is given only table/column/FK **names**, truncated at 12 000 chars. The fixes need richer metadata — indexes, partition keys, row-count magnitude, nullability, unique keys, and FK cardinality — plus business semantics and value domains. The hard constraint is **Invariant 3**: no row data (or values derived from rows) may reach any model. Per the charter (D-D, D-J, D-L) profiling is read-only, bounded, privilege-degrading, mandatory at a setup gate, and persisted additively.

## Decision
Extend live introspection ([ADR-010](ADR-010-schema-introspection-via-chokepoint.md)) into a **profiler** that captures enriched metadata in **two physically separated channels**:

- **Channel A — structure + statistics** (`Schema`, persisted in `SchemaRecord.definition`): indexes (`ALL_INDEXES`/`ALL_IND_COLUMNS`), partition keys (`ALL_PART_KEY_COLUMNS`), row-count magnitude + staleness (`ALL_TABLES.NUM_ROWS`/`LAST_ANALYZED`, **treated as a hint**), nullability/precision (`ALL_TAB_COLUMNS`), unique (`ALL_CONSTRAINTS` type `U`), and **derived** FK cardinality. Names/structure/magnitudes only — safe to send to the LLM.
- **Channel B — semantics + value domains** (new `SchemaRecord.semantics`, **never** read by `schema_from_dict`/`to_compact_markdown`): business glossary, distinct **value domains** (`'A'='Active'`), engineer-declared joins. Used only server-side (local value rewrite, readiness gate).

All readers are SELECT-only through `run_select`, bind-parameterized, `SafetyLimits`-capped, and **degrade gracefully** (generic warning, continue) when a catalog view isn't granted — mirroring today's PK/FK degradation. Value-domain sampling (Channel B) is **opt-in, bounded, default OFF** (catalog-only by default; live `COUNT`/`SAMPLE` only when enabled). Schema dataclass + `schema_to_dict`/`from_dict` extensions and the new `SchemaRecord` fields are **additive and back-compatible** (absent → today's behavior).

## Consequences
- The model can reason about size, indexes, partitions, and fan-out → fewer slow/wrong queries (the input to ADR-029).
- The two-channel split makes Invariant 3 a **structural** property: Channel B is unreachable from the prompt path (the LLM context is built only from `Schema`, which never carries values).
- Profiling is heavier than name-only introspection → governed by sampling/bounds/privilege-degradation (P11-R1) and runs at onboarding + manual refresh (no scheduler).
- `NUM_ROWS` can be stale/null → used as a hint with a `stats_stale` flag, never a correctness dependency (P11-R5).

## Security / invariants
- **Invariant 1:** profiling queries are read-only SELECTs over `ALL_*` views through the chokepoint; no new execution path.
- **Invariant 3:** Channel B (values/semantics) is never serialized into `definition` nor read by `schema_from_dict`; a dedicated test asserts profiled values cannot appear in `build_external_context` output.
- **Invariant 5:** privilege/driver failures log raw text server-side, surface a generic warning only.

## Alternatives considered
- **Single enriched Schema carrying values:** rejected — one slip in prompt-building would leak values; the two-channel split removes that class of bug by construction.
- **Ask the client to hand over metadata:** rejected — nearly all of it is auto-readable from the catalog; only glossary/undeclared-joins need a human (captured at the D-L gate).
- **Profile everything live (counts on every table):** rejected — risks hammering production; bounded/opt-in sampling instead (D-D).
