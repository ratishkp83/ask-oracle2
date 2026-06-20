# ADR-023 — Report parameter value-pickers (lookups, FK suggest, run-time auto-derivation)

- **Status:** Accepted
- **Date:** 2026-06-15
- **Deciders:** Product/Engineering (owner-requested)
- **Phase:** v2 / Phase 9 (B6 — Reports)

## Context
A saved report can declare typed parameters bound as `:name` at run time
([ADR-007](ADR-007-parameterized-reports-bind-variables.md)). Until now the run dialog only offered a
free-text input, so a user had to **know the raw value** (e.g. a `department_id`) — unusable for
reference data (departments, ledgers, suppliers, statuses). The owner asked for **dropdowns populated
with real values, fetched live**, and asked whether the system could be "smart enough" to do this for
any custom report without manual setup.

## Decision
Add **value-pickers** in three layers, explicit-first, all read-only:

1. **Persisted lookup (`ReportParam.lookup_sql`).** A parameter may carry an optional `SELECT` returning
   the allowed values — column 1 = the bind value, optional column 2 = a display label. It is **persisted
   with the report and never executed at save time** (additive, backward-compatible backend field).
2. **Live dropdown at run time.** When a parameter has a lookup, the run dialog runs it through the
   **SELECT-only `/execute` chokepoint** ([ADR-005](ADR-005-execute-chokepoint.md)) using the effective
   connection and renders a dropdown (value + label, briefly cached). It **falls back to a typed input**
   when there is no connection, no lookup, or the lookup fails — so a value can always be entered.
3. **Editor assist + run-time auto-derivation.**
   - The report editor exposes a per-parameter **"Value picker SQL"** field plus a **"Suggest…"** control
     that fills it from a **foreign key** in the active data dictionary (a `*_NAME` column is chosen as the
     label when present), then remains editable.
   - **Auto (zero-config):** when a parameter has *no* explicit lookup, the run dialog parses the report
     SQL to map each `:bind` to its column (`web/src/lib/derive/paramLookup.ts`: handles `=`, `IN`,
     `BETWEEN`, bind-on-left; strips table qualifiers) and, if the active dictionary marks that column a
     foreign key, **derives the lookup automatically**.
   - **Precedence:** explicit `lookup_sql` → auto-derived → typed input.

## Rationale / Security
- **Read-only and on-chokepoint.** Lookups are SELECTs executed via `/execute`; the safety engine
  ([ADR-001](ADR-001-sql-safety-engine.md)) re-validates them. No new data path, no new endpoint.
- **No client-side secret** (invariant 4): lookups run against a connection chosen by `profile_id`.
- **Sanitized failures** (invariant 5, [ADR-012](ADR-012-observability-and-error-handling.md)): a failing
  lookup degrades to the typed input rather than blocking the run.
- **Explicit-over-magic.** Pure name-based guessing is unreliable (bind `dept_id` vs column
  `department_id`; ambiguous label columns; worse on real EBS). Making the stored lookup the source of
  truth — with FK *suggestion* and *SQL-derived* auto as conveniences that **degrade to text** — keeps it
  deterministic and avoids silently binding the wrong list.

## Consequences
- Dropdowns work for **any** report parameter, with **one-click setup** (FK suggest) or **zero setup**
  (auto-derivation) when a data dictionary is active.
- One additive backend field (`lookup_sql`); auto-derivation depends on an **active saved schema** and is
  heuristic by nature (documented; falls back gracefully).
- Lookups are **live**, not cached-static, so they reflect changes to reference data.

## Alternatives considered
- **Pure auto-detect from the bind name only:** rejected — fragile, can pick the wrong table/label.
- **A dedicated `/lookup` endpoint:** rejected — `/execute` already is the SELECT-only chokepoint; reuse it.
- **Hardcoded/seeded picklists:** rejected — not data-driven; would drift from the database.
- **Baking lookups into the curated EBS templates:** deferred (content task; needs real-EBS validation,
  [ITM-012](../issue-log.md)) — the auto-derivation covers custom reports without it.
