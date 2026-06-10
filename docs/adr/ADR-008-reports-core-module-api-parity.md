# ADR-008 — Reports are a core module with API parity

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product/Engineering
- **Phase:** 4 (Reports, Templates & UX)

## Context
Before Phase 4, saved reports were a thin UI-only feature: `src/storage.py` persisted
`{ name: { sql } }` and only the Streamlit app read/wrote it — there was **no `/reports`
API**. That diverged from the profiles/execute architecture (ADR-005), where UI and API
share one core store and one execution path, and it left the report run path untested.

## Decision
Promote reports to a first-class **core module** with **API parity**, mirroring
`core/profiles.py`:

- `src/core/reports.py` owns the Report v2 model, the `ReportStore` ABC
  (`JsonFileReportStore` default + `InMemoryReportStore` for tests), legacy migration,
  and `coerce_report_binds`.
- `src/api.py` exposes `/reports` CRUD and `POST /reports/{id}/run`. The run endpoint
  coerces parameters then executes through the **same** internal chokepoint helper
  (`_run_sql`) used by `/execute` — refactored out so there is exactly one safety +
  limits + audit path (preserves ADR-005).
- The Streamlit Reports/Templates sections call the same core store directly (as the UI
  already does for profiles).
- Curated templates live in `src/core/templates.py` and are exposed read-only via
  `/templates`.

## Consequences
- One source of truth for reports; the run path is exercised by API tests
  (`tests/test_reports_api.py`) with the DB monkeypatched.
- The legacy `{name:{sql}}` file is migrated to v2 on first load (idempotent).
- The old `storage.py` report helpers are removed (dead code).
- Slightly more surface than a UI-only feature, accepted for coherence and testability.

## Alternatives considered
- **Keep reports UI-only this phase:** rejected — perpetuates the asymmetry and leaves
  the parameterized-run path (the riskiest new code) without API-level tests.
- **A separate microservice for reports:** rejected — unjustified for a single-process app.
