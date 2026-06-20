# ADR-021 — SQL-aware deterministic derivation + cascading drill-down (no row data to any LLM)

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 9 (B5a, B5b, B5b-1/2/3)

## Context
The executive Results view must turn a raw `/execute` result into the **summary → KPIs → drivers →
detail** hierarchy and let the user **cascade** from a summary down to the underlying detail. Two hard
constraints: (1) **invariant 3** — *never send row/cell data to any model*; all intelligence must be
local and deterministic; (2) it must be **robust** on arbitrary result shapes. Name-only heuristics
proved insufficient — they mislabelled columns (summed an `AVG`; treated a numeric `FISCAL_YEAR`
GROUP BY key as a KPI measure; matched `due` inside `overdue`).

## Decision
Derive everything **client-side and deterministically**, reading only the proposed SQL text and the
already-fetched rows — nothing leaves the browser.

- **SQL-aware classification** (`web/src/lib/derive/sql.ts`): a *fail-safe, non-validating* reader of
  the proposed `SELECT` extracts `GROUP BY → dimensions` and aggregate functions `→ measures + their
  exact aggregation` (SUM/AVG/COUNT/MIN/MAX), and **overrides** the name heuristics in
  `columns.ts`/`kpis.ts`/`chart.ts`. When the SQL can't be read cleanly (`SELECT *`, CTE, set ops,
  window aggs, output/column-count mismatch) it returns `reliable:false` and falls back to name+value
  heuristics. It **never throws**.
- **Cascading drill-down** (`web/src/lib/derive/cascade.ts`): a pure drill-stack — `dimensionOrder`
  descends in GROUP BY order (column-order fallback), `filterRows` ANDs the stack, a shared
  `dimKey`/`NULL_KEY` keeps the chart's group keys and the drill filter aligned (so a `NULL`/"—" bucket
  drills correctly). `pickChart` skips a dimension that is constant in the drilled scope so 3+ dim
  cascades reach real detail. A **date dimension** renders a non-drillable trend line; rather than
  dead-ending, it offers a **Pull-live-detail** path (finding F3).
- **Live "Pull <value> data"** (`web/src/lib/derive/pullDetail.ts`, Decision 3): deterministically wrap
  the **approved** SQL — `SELECT * FROM (<approved>) WHERE <dim> = :v [AND …]` over the active drill
  stack (binds, `IS NULL` for the NULL bucket) — and route it through the **review step for
  re-approval** before `/execute`. A fresh, un-truncated, server-side fetch of exactly that slice; **no
  new LLM call**. Still a plain `SELECT`, so the chokepoint re-validates it.

## Consequences
- An intelligent executive rendering (KPIs, driver chart, cascade) with **zero row data sent to any
  LLM** — invariant 3 holds by construction.
- Correct classification: AVG/MIN/MAX are not silently summed; GROUP BY keys are not treated as KPIs.
- The SQL reader is heuristic/best-effort; on anything it can't parse cleanly it degrades to the
  name+value heuristics rather than failing.

## Security / invariants
- **Invariant 3:** only SQL text + the rows already in the browser are read; nothing is sent to a model.
- **Invariant 1:** the pull-detail wrap is a plain `SELECT`; the server SELECT-only chokepoint
  ([ADR-005](ADR-005-execute-chokepoint.md)) re-validates it, and binds carry the drill values (never
  string-interpolated). Filters only ever carry categorical/numeric dimensions (dates are non-drillable
  lines), so a stringified bind is safe (Oracle implicit-converts for NUMBER).

## Alternatives considered
- **Send the result to an LLM to summarize / pick KPIs:** rejected — directly violates invariant 3 and
  adds latency/cost/nondeterminism to every result.
- **Server-side derivation endpoint:** rejected — the client already holds the rows; a new endpoint adds
  API surface and a round-trip for no benefit. Deterministic client math keeps the server minimal.
- **Re-aggregate the approved query for drill-down instead of filtering local rows:** the *display*
  cascade filters local rows (instant, no DB); the optional **Pull-live-detail** wrap is the deliberate
  live re-fetch when the user wants fresh, un-truncated detail.
