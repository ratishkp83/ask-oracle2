# ADR-010 — Live schema introspection via the SELECT-only chokepoint

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product/Engineering
- **Phase:** 5 (Data Dictionary Browser & Schema Tools)

## Context
Through Phase 4, schema metadata could only be supplied by **uploading** CSV/Excel — a
real friction point. Phase 5 (charter D-A) adds **live introspection**: auto-building the
dictionary from Oracle's data-dictionary views. This means the app issues new queries
against the database, so it must not weaken the read-only guarantees (ADR-001/005/009).

## Decision
Introspection reuses the **existing single execution chokepoint** — there is **no new
path** to the database:

- All dictionary queries run through `OracleClient.run_select`, which calls
  `assert_safe_select` first. They are plain **SELECTs** over `ALL_TAB_COLUMNS`,
  `ALL_CONSTRAINTS`, and `ALL_CONS_COLUMNS` (each proven a safe SELECT in tests).
- Queries are **bind-parameterized** (`:owner`, `:table_like`) — values are never
  interpolated into the SQL ([ADR-007](ADR-007-parameterized-reports-bind-variables.md)).
- **`ALL_*` views only** (objects visible to the connected least-privilege account), never
  `DBA_*`.
- **Scoped + capped:** an `owner`/schema is required and a name filter is encouraged;
  results are bounded by `SafetyLimits` (`truncated` surfaced). No full-catalog crawl.
- **Graceful degradation:** if the constraint views aren't visible to the account, the
  introspection returns a columns-only schema plus a warning rather than failing.
- The module is split into SQL **builders**, pure **mappers** (rows → `Schema`), and an
  **orchestrator**, so the safety of the SQL and the correctness of the mapping are unit-
  tested without a live database.

## Consequences
- Auto-loads the dictionary, removing the manual-upload burden, with the same safety
  posture as `/execute`.
- Introspection inherits the read-only-account guarantee (ADR-009): the dictionary queries
  cannot write, and neither can anything else the account runs.
- Large catalogs (e.g. full EBS) require scoping; an unscoped crawl is intentionally not
  supported.

## Alternatives considered
- **A dedicated introspection connection/path bypassing the safety layer:** rejected —
  would create a second execution path and undermine the single-chokepoint invariant.
- **`DBA_*` views:** rejected — require elevated privileges contrary to ADR-009.
