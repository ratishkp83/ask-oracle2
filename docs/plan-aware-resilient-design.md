# Design — Plan-Aware Query Intelligence + Resilient Execution (Phase 11, B2)

> **Document:** Phase Design · **Version:** 1.0 · **Status:** 🟡 **B2 — awaiting owner sign-off (no feature code until approved)** · **Owner:** Product/Engineering · **Date:** 2026-06-18
> **Charter:** [charters/phase-11-plan-aware-resilient.md](charters/phase-11-plan-aware-resilient.md) (🟢 B1 approved, v1.2). **ADRs:** [028](adr/ADR-028-database-profiling.md) · [029](adr/ADR-029-plan-aware-generation.md) · [030](adr/ADR-030-resilient-async-execution.md) · [031](adr/ADR-031-privilege-gated-plan-reading.md).

This design realizes the two pillars and the owner-directed additions (D-K advisory, D-L mandatory-at-setup, soft-block default). It is grounded in the current code; every new symbol below names a concrete module.

## 0. The load-bearing principle — two metadata channels

Invariant 3 (no row data to any model) is preserved **structurally, by construction**, not just by a tripwire. We split profiled metadata into two channels that never mix:

| Channel | Contents | Persisted in | May reach the LLM? |
|---|---|---|---|
| **A — Structure + statistics** | tables, columns, types, nullability, PK/FK, **index column names**, **partition key names**, **row-count magnitude**, **FK cardinality** | `SchemaRecord.definition` (via `schema_to_dict`) — extends the existing `Schema` | **Yes** — names/structure/magnitudes only, no values. Flows through `build_external_context`. |
| **B — Semantics + value domains** | business glossary/descriptions, **distinct value domains** (`'A' = "Active"`), engineer-declared join notes | **new** `SchemaRecord.semantics` field — **never** read by `schema_from_dict`/`to_compact_markdown` | **No.** Used only server-side for the **local** value-domain rewrite (D-C) and the readiness gate. |

The only function that builds LLM context is `build_external_context(schema)`, and `schema` is reconstructed by `schema_from_dict`, which is a **whitelist** that reads only Channel-A keys. Channel B is physically unreachable from the prompt path. This is the single most important structural guarantee in the phase.

---

## 1. Pillar 1a — Database Profiling (ADR-028)

### 1.1 New introspection readers (`src/core/introspection.py`)
Same shape as today (builder → mapper → orchestrator, all SELECT-only through `OracleClient.run_select`, bind-parameterized, `SafetyLimits`-capped, privilege-degrading):

- `indexes_sql(owner, table_like)` → `ALL_INDEXES`/`ALL_IND_COLUMNS` (index name, table, ordered columns, uniqueness). Mapper `apply_indexes` sets per-column `is_indexed` + a table-level `indexes: [IndexDefinition]`.
- `partition_keys_sql(owner)` → `ALL_PART_KEY_COLUMNS` (+ `ALL_PART_TABLES`). Mapper marks `partition_keys: [col]` per table.
- `table_stats_sql(owner, table_like)` → `ALL_TABLES.NUM_ROWS`, `LAST_ANALYZED`. Mapper sets `row_count_estimate` + `stats_stale` (null/old `LAST_ANALYZED`). **Treated as a hint** (§1.4).
- `unique_constraints_sql(owner, table_like)` → `ALL_CONSTRAINTS` type `U`. Mapper sets `is_unique`.
- Column detail: extend `columns_sql` to also select `nullable`, `data_length`, `data_precision`, `data_scale` → richer `ColumnDefinition`.
- **FK cardinality** is *derived* (no new query): an FK is `many-to-one` if the referenced column is PK/unique (it always is for a real FK); the **child** side is `1:N` unless the FK column set is itself unique/PK (then `1:1`). Mapper annotates `RelationshipDefinition.relationship_type` and a `fan_out: bool`.

### 1.2 Orchestrator `profile_schema(client, owner, options) -> ProfileResult`
Wraps `introspect_schema` (columns + PK + FK as today), then layers indexes/partitions/stats/unique/cardinality, each in its own `try/except` that appends a **generic** warning on a privilege failure (mirrors the existing PK/FK degradation; raw driver text logged server-side only). Returns the enriched `Schema` (Channel A) + `warnings[]` + a `coverage` map (which signals were available) used by the readiness gate.

### 1.3 Value-domain capture (Channel B) — bounded, opt-in, default OFF (D-D)
- **Catalog-only by default.** Live `COUNT(*)` and distinct-value sampling are **opt-in** and bounded: only columns the catalog marks **low-cardinality** (or a small allow-list), via `SELECT col, COUNT(*) FROM (SELECT col FROM tbl SAMPLE(p)) GROUP BY col FETCH FIRST k ROWS ONLY` — all SELECT-only through the chokepoint, row/time-capped. Result stored in Channel B (`semantics.value_domains[table.col] = [{code, label?}]`).
- The **label** ("Active") is engineer-supplied or left blank; the **code** ('A') is what the local rewrite targets. **No value ever leaves the server.**

### 1.4 Data-model additions (`src/schema.py`) — all additive, all Channel A
`ColumnDefinition += { nullable: bool|None, data_length, data_precision, data_scale, is_indexed: bool, is_unique: bool }`; `TableDefinition += { indexes: [IndexDefinition], partition_keys: [str], row_count_estimate: int|None, stats_stale: bool }`; `RelationshipDefinition += { fan_out: bool }`. `schema_to_dict`/`schema_from_dict` extended (whitelist) — back-compatible (absent → defaults). `to_compact_markdown` is **unchanged for now** (the perf brief is a separate compact view, §2.1, so we don't bloat every prompt).

### 1.5 Persistence (D-J) — `src/core/schema_store.py`
`SchemaRecord += { semantics: Dict = {}, readiness: Dict = {} }` (additive, default empty → back-compat). `definition` carries Channel A as today. `SchemaSummary` gains a `readiness_state` for list views. **Crucially, `semantics` is never passed to `schema_from_dict`.**

---

## 2. Pillar 1b — Plan-Aware Generation + local accuracy (ADR-029)

### 2.1 Performance brief + relevant-subset selection (fixes the 12k truncation)
Today `build_external_context` blunt-truncates at 12 000 chars (`src/core/llm/redaction.py:29`). Replace with **schema linking**:

- `select_relevant_tables(schema, question, semantics, budget) -> Schema` (new, pure, local): rank tables by lexical overlap of the question (+ glossary terms from Channel B) with table/column names, then **expand along the FK graph** to pull in directly-joined neighbors, capped to a char/token budget. Deterministic; never throws; falls back to "all tables" when the schema already fits.
- `build_performance_brief(schema) -> str` (new): a compact appendix listing, per selected table, **size class** (e.g. `~50M rows (FACT)` vs `~1.2k (lookup)`), **indexed columns**, **partition key**, and **fan-out joins** — names/magnitudes only (Channel A). Appended to the external context **before** the `assert_no_values` tripwire (same pattern as the EBS pack context).
- `SYSTEM_PROMPT` gains a short directive: *prefer filtering/joining on indexed & partition-key columns; include the partition key in WHERE for large partitioned tables; put the smaller (driving) table first; aggregate in SQL.* No behavioral change to the chokepoint.

### 2.2 Static pre-flight heuristics (`src/core/sql_plan.py`, new)
Pure sqlglot-AST analysis of the **proposed** SQL (reuses the parse the chokepoint already does), returning `[PlanWarning{code, message, severity}]` — **advisory, never blocks**:
- `CARTESIAN` — a join with no ON/USING and no correlating WHERE predicate between two tables.
- `FACT_SCAN` — a `FROM`/join on a table whose `row_count_estimate` exceeds a threshold with **no WHERE predicate** on it.
- `MISSING_PARTITION_PREDICATE` — a known-partitioned large table with no predicate on its partition key.
- `UNFILTERED_LARGE` — a non-aggregated projection over a large table with no row-bounding clause.
Surfaced in the Ask review step (and Streamlit) next to confidence — informational.

### 2.3 Local value-domain resolution (D-C) — `resolve_value_literals(sql, schema, semantics) -> (sql, [Correction])`
Post-generation, pre-review, **deterministic, server-side, no LLM**:
- Walk the AST for equality/IN predicates on a column that has a Channel-B value domain.
- If the literal already matches a **code** → leave it.
- If it matches a domain **label** (case-insensitive / fuzzy) but not a code → **rewrite** the literal to the code (`status = 'Active'` → `status = 'A'`), and record a `Correction` shown to the user in review ("mapped *Active* → `A`").
- Conservative: only rewrites on a confident label→code match; otherwise leaves the SQL untouched. Output still passes through `assert_safe_select` unchanged. **No values to the model; the user sees and approves the corrected SQL.**

---

## 3. Pillar 1c — Optimization Advisory (D-K) + Setup Readiness Gate (D-L)

### 3.1 Advisory `build_optimization_advisory(schema) -> [Suggestion]` (new, pure)
Deterministic derivation of Channel-A facts, ranked, **advise-only**:
- **FK/join column with no index** → "consider an index on `T.C`" (highest-value, most common).
- **Large table, no partitioning** → "consider partitioning `T` by a date/region key."
- **Missing/stale stats** → "ask the DBA to `DBMS_STATS.GATHER_TABLE_STATS('owner','T')`."
- **No PK/unique** → "no unique key detected on `T`."
Each `Suggestion{kind, target, ddl_candidate, rationale, tradeoff}`. Rendered on the **admin** surface (Connections/Data-dictionary). The app **never executes** any DDL. Conservative copy: "candidates to evaluate with your DBA."

### 3.2 Readiness gate (D-L, soft-block default)
`compute_readiness(schema, semantics, coverage) -> Readiness{state, checklist[]}`:
- **Auto checks:** catalog profiling succeeded for columns/PK/FK/index/partition/stats (or each is explicitly acknowledged-unavailable).
- **Human checks:** glossary present for flagged cryptic columns; value-domain labels for low-cardinality filter columns; **join relationships supplied where no FK is declared**.
- `state ∈ { ready, not_optimized, incomplete }`. **Default soft-block:** `not_optimized` connections are usable but the Ask/Reports UI shows a calm "Not optimized — accuracy/performance may suffer" banner. A deployment config `READINESS_ENFORCEMENT=hard` flips to blocking. Persisted in `SchemaRecord.readiness`; an onboarding wizard (admin) walks the checklist.

---

## 4. Pillar 2 — Resilient Execution (ADR-030)

### 4.1 Job model (`src/core/jobs.py`, new) — ephemeral, in-memory, single-worker (D-B)
- `QueryJob{ id, state: queued|running|succeeded|failed|cancelled, created_at, result?, error_id?, profile_id }`.
- `JobStore` — in-memory dict + lock + **TTL eviction** + a **max-jobs cap** (oldest evicted). **Nothing persisted to disk.** Mirrors the single-worker posture (RISK-16).
- A bounded `ThreadPoolExecutor` runs `_run_sql(...)` (the existing chokepoint body) per job. The worker holds the `OracleClient` so it can cancel.

### 4.2 Cancellation + timeout (reuses + extends `db.py`)
- `OracleClient.run_select` already sets `conn.call_timeout = max_execution_seconds*1000` → a runaway query is bounded **today**. For **async**, the job uses a separate, longer `max_execution_seconds_async` cap.
- **Explicit cancel:** add a cancellable path — `run_select(..., on_connect=cb)` (or a small `CancelToken`) that hands the live `conn` to the job so `POST /execute/jobs/{id}/cancel` can call `conn.cancel()` (best-effort; thin-mode supports it). `call_timeout` remains the hard backstop if cancel can't reach the connection (P11-R6).

### 4.3 Endpoints (root + `/v1`, auth-gated like `/execute`)
- `POST /execute` — **hybrid (D-E):** internally start a job, wait up to `EXECUTE_SYNC_WAIT_SECONDS` (config, e.g. 45s). If done → return the result inline **exactly as today** (back-compatible response). If still running → `202 { job_id, state: "running" }`.
- `GET /execute/jobs/{job_id}` → `{ state, result? , error_id? }` (sanitized).
- `POST /execute/jobs/{job_id}/cancel` → best-effort cancel → `{ state: "cancelled" }`.
- Result payload identical to today's `_run_sql` return (columns/rows/elapsed/row_count/truncated).

### 4.4 Ephemeral result cache (D-B)
`ResultCache` keyed by `hash(sql + binds + profile_id + max_rows)` → the result + timestamp; **in-memory, short TTL, size-capped**. `_run_sql` consults it before connecting; a cache hit skips the DB. Per-profile isolation; never persisted. Opt-out via a header/param for "force fresh."

### 4.5 Sample-first preview (D-I)
`POST /execute` accepts `sample: {percent}` (opt-in). When set on a query over a known-large base table, wrap as `SELECT * FROM (<approved>) SAMPLE(p)` (still a SELECT through the chokepoint) for a fast **approximate** answer, clearly labelled in the UI, with one-click full/async run. (Only applied when the approved SQL shape allows a safe sample wrap; otherwise the option is hidden.)

### 4.6 Frontend (`web/`)
- `endpoints.ts`: `executeAsync`/`getJob`/`cancelJob`; `execute()` handles the `202` → poll `getJob` with backoff, showing a "Still running… (cancel)" state in `AskPage`/`ReportsPage`. The cascade fan-out (`onRunSql`) reuses the same path. Sample-first toggle in the review step.

---

## 5. Self-heal (D-H) + Plan reading (D-F)

- **Self-heal (`src/core/selfheal.py`, B6):** on a timeout or a known-optimizable Oracle error, build a repair prompt = the **SQL + the sanitized error/static-warning** (no rows) → one model rewrite (max 2) → routed **back through the same review gate** (`ProposedSql`), re-approved (or, under Auto-run, the user's chosen mode), re-run via the chokepoint. Off when generation is disabled.
- **Plan reading (D-F, optional, B6):** behind `PLAN_READING_ENABLED` + a privilege probe at onboarding. `DBMS_XPLAN.DISPLAY_CURSOR` is read via a **SELECT** (so it can pass the chokepoint) **only on the guarded diagnostic path**; `EXPLAIN PLAN FOR` is never routed as user SQL. Gracefully disabled when grants/plan-table absent. Feeds higher-fidelity warnings when available; static heuristics are the always-on default.

---

## 6. API + data-model summary (additive, back-compatible)

**New/changed endpoints:** `POST /execute` (hybrid + optional `sample`), `GET /execute/jobs/{id}`, `POST /execute/jobs/{id}/cancel`, `POST /schemas/profile` (enriched profiling, extends introspect), `GET /schemas/{id}/advisory` (Optimization Advisory), `GET /schemas/{id}/readiness`. All auth-gated, all mounted on root + `/v1`.

**New config (env):** `EXECUTE_SYNC_WAIT_SECONDS`, `MAX_EXECUTION_SECONDS_ASYNC`, `RESULT_CACHE_TTL_SECONDS`, `RESULT_CACHE_MAX_ENTRIES`, `JOB_TTL_SECONDS`, `JOB_MAX`, `READINESS_ENFORCEMENT` (soft|hard, default soft), `PROFILE_SAMPLING_ENABLED` (default off), `PLAN_READING_ENABLED` (default off). All have safe defaults; the product runs unchanged if none are set.

## 7. Invariant analysis (all five hold)

1. **SELECT/CTE-only chokepoint** — every new SQL path (profiling readers, sample wrap, plan-reading SELECT, async jobs) runs through `assert_safe_select`/`run_select`. Async changes *when we wait*, not *what runs*. `EXPLAIN PLAN FOR` is never user SQL.
2. **AI proposes / user approves** — plan-aware context only changes what the model *sees*; value-domain rewrite and self-heal both surface in the **review** step for approval (Auto-run governs as today).
3. **Schema-names-only / no row data to any model** — enforced **structurally** by the two-channel split (§0): Channel B (values/semantics) is physically unreachable from `build_external_context`; the `assert_no_values` tripwire still guards the assembled context.
4. **No client-side DB secrets** — connections by `profile_id`; job ids opaque; the cache holds already-authorized results keyed by profile, never credentials.
5. **Sanitized errors + `error_id`** — job failures, timeouts, cancellations, profiling-privilege failures all route through `_db_error`/`friendlyError`; raw ORA/driver text logged server-side only.

## 8. Test strategy

- **pytest:** new introspection builders (SQL text + binds) and mappers (rows → enriched Schema) with mocked cursors; `profile_schema` privilege-degradation; `resolve_value_literals` (rewrite vs leave; never breaks safety); static heuristics (cartesian/fact-scan/partition); job lifecycle (queued→running→succeeded/failed/cancelled, TTL eviction, cap); hybrid `/execute` (inline vs 202); cache hit/miss + isolation; readiness computation; advisory derivation; **adversarial:** assert Channel B never appears in `build_external_context` output (a direct test that profiling values can't reach the prompt).
- **vitest:** async UI states (running/cancel/poll), sample-first toggle, advisory/readiness rendering, value-domain correction display.
- Gates each packet: **pytest · vitest · `tsc --build` · vite build** (BUG-013: the bare `tsc --noEmit -p tsconfig.json` is a no-op — use `tsc --build`).

## 9. Build packets (each: build → gates → internal review → present → HOLD for sign-off)

- **B3 — Profiling + Advisory + Readiness** (Pillar 1a/1c + D-L): introspection readers, enriched Schema + additive persistence, value-domain capture (opt-in), `profile_schema`, advisory + readiness, `POST /schemas/profile` + advisory/readiness endpoints; admin UI checklist; live vs XE.
- **B4 — Plan-aware generation + accuracy** (Pillar 1b): relevant-subset selection (12k fix), performance brief, prompt directive, static heuristics, local value-domain resolution; live vs XE.
- **B5 — Resilient execution** (Pillar 2): job model + hybrid `/execute` + jobs endpoints, timeout/cancel/cap, ephemeral cache, sample-first; async UI in Ask + Reports; live on a deliberately slow query.
- **B6 — Self-heal + optional plan reading** (D-H/D-F).
- **B7 — Docs sweep + complete product test + independent exit-gate review** (reviewer ≠ author) → remediate → CLOSE.

## 10. Decisions for this sign-off

- **Confirmed:** D-A/B/C (charter), D-L **soft-block default**, B2 proceed.
- **Carried recommendations (confirm or adjust at this sign-off):** D-D (catalog-default, sampling opt-in), D-E (hybrid sync→async), D-F (static-first, plan-reading opt-in), D-G (parallel OFF), D-H (bounded self-heal), D-I (opt-in sample-first), D-J (additive profile storage).
- **No feature code begins until this design is approved.**

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-18 | Product/Eng | B2 design drafted: two-channel metadata principle; profiling readers + enriched Schema + additive persistence; relevant-subset selection (12k fix) + performance brief + static heuristics + local value-domain resolution; Optimization Advisory + soft-block readiness gate; in-memory async job model + hybrid `/execute` + ephemeral cache + sample-first; self-heal + optional plan reading. ADR-028…031 drafted alongside. **Awaiting sign-off; no code yet.** |
