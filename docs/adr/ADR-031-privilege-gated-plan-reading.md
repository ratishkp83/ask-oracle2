# ADR-031 — Privilege-gated query plan reading (optional, static-first)

- **Status:** Proposed (B2 — awaiting owner sign-off; optional, default OFF)
- **Date:** 2026-06-18
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 11 (D-F, B6)

## Context
The highest-fidelity way to catch a slow query is to read its **execution plan** (full table scans, bad join order, cartesian/nested-loop over millions of rows). But the classic approach collides with our constraints: `EXPLAIN PLAN FOR <stmt>` is **not a SELECT** (fails `assert_safe_select`) and needs a writable plan table; `DBMS_XPLAN.DISPLAY_CURSOR` needs `V$` grants a least-privilege read-only account usually lacks. We must not assume either is available, and must never widen the chokepoint.

## Decision
**Static-first, real-plan opt-in.** The always-on default is the static sqlglot heuristics (ADR-029 §2.2), which need no DB privileges. Real plan reading is an **optional enhancement**, default **OFF** (`PLAN_READING_ENABLED`):

- At onboarding, **probe** whether the account can read a plan (via a guarded test). Persist the capability; if absent, the feature stays disabled with no error.
- When enabled and available, read the plan via a **SELECT** against `DBMS_XPLAN.DISPLAY_CURSOR` (a table function) on a **separate, explicitly-guarded diagnostic path** — never as user SQL. `EXPLAIN PLAN FOR` is **never** routed through the user chokepoint.
- The plan feeds higher-fidelity `PlanWarning`s (full-scan/bad-join) and can seed self-heal (D-H). When unavailable, static heuristics remain the sole source.

## Consequences
- Where privileges allow, warnings become optimizer-accurate; where they don't, the product still works on static heuristics — **no hard dependency** on grants we can't guarantee.
- Keeps the SELECT-only chokepoint intact (the diagnostic read is a SELECT; `EXPLAIN PLAN FOR` is excluded).
- Adds onboarding complexity (a privilege probe) — justified only as an opt-in; off by default.

## Security / invariants
- **Invariant 1:** the only plan-read path is a SELECT through a guarded diagnostic call; the user chokepoint is unchanged; no DML/DDL (`EXPLAIN PLAN FOR`/plan-table writes) is ever issued.
- **Invariant 3:** a plan exposes operations/object names/cardinalities — **structure/statistics, not row values**; nothing from a plan is sent to a model except, optionally, plan **shape** text on the self-heal path (no rows).
- **Invariant 5:** probe/read failures degrade silently to static-only, logged server-side.

## Alternatives considered
- **Mandatory EXPLAIN PLAN:** rejected — needs a writable plan table a read-only account lacks, and isn't a SELECT.
- **Always-on DISPLAY_CURSOR:** rejected — `V$` grants aren't guaranteed; would error on most least-privilege accounts.
- **No plan reading at all:** acceptable fallback (static heuristics) — which is exactly why this is optional, not required.
