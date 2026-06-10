# Reports, Templates & UX — Design (Phase 4)

> **Document:** Design · **Version:** 1.0 · **Status:** Baseline (built; Phase 4 closed — exit gate passed) · **Owner:** Product/Engineering · **Last updated:** 2026-06-10
> Implements [phase-4-charter.md](charters/phase-4-charter.md) (decisions D-A…D-I resolved 2026-06-10).

## 1. Overview
Phase 4 promotes saved reports to **parameterized, profile-bindable, metadata-carrying**
artifacts; ships a curated **EBS template catalog**; and reworks the UI to a **left-nav**.
All query execution continues to flow through the single SELECT/CTE-only safety
chokepoint — parameters are passed as **Oracle bind variables**, never interpolated.

## 2. Data model (D4)

### 2.1 `ReportParam`
| Field | Type | Notes |
|-------|------|-------|
| `name` | str | Bind variable name. Must match `^[A-Za-z_][A-Za-z0-9_]*$`, ≤ 30 chars. |
| `label` | str | UI label. Defaults to `name` if empty. |
| `type` | `string` \| `number` \| `date` | Drives form widget + bind coercion. |
| `required` | bool | Default `True`. |
| `default` | str \| number \| null | Optional default value (date as `YYYY-MM-DD`). |

### 2.2 `Report` (v2)
| Field | Type | Notes |
|-------|------|-------|
| `id` | str | `uuid4().hex`, server-assigned. |
| `name` | str | Unique (case-sensitive); 1–120 chars. |
| `description` | str | Optional, default `""`. |
| `sql` | str | SELECT/CTE; may contain `:param` binds. |
| `parameters` | list[ReportParam] | Default `[]`. |
| `default_profile_id` | str \| null | Optional bound profile (D-H). |
| `template_id` | str \| null | Provenance if created from a template. |
| `created_at`, `updated_at` | str | ISO-8601 UTC. |

`ReportCreate` is the inbound payload (no `id`/timestamps; server assigns). The store is
an ABC (`ReportStore`) with `JsonFileReportStore` (default, `storage/reports.json`) and
`InMemoryReportStore` (tests) — mirroring `ProfileStore`.

### 2.3 Legacy migration (D-A / R4-3)
The old shape was `{ <report-name>: { "sql": "..." } }`. On load, any record lacking an
`id`/`name` field is treated as legacy and converted to a `Report` v2 (`id=uuid4`,
`name=<key>`, `sql=<record.sql>`, `parameters=[]`, timestamps=now). The migrated map is
written back once (idempotent thereafter). A regression test exercises the old shape.

### 2.4 `Template`
Read-only, curated, in-code (`src/core/templates.py`); never persisted:
`id`, `module` (`GL`/`AP`/`AR`/`PO`/`OM`), `name`, `description`, `sql` (`:binds`),
`parameters: list[ReportParam]`. v1 catalog ≈ 13 templates (GL×3, AP×3, AR×2, PO×3, OM×2).
Each carries a "standard EBS reference — review before running" caption; **never auto-runs**.

## 3. Bind-parameter safety (D-B / D-G / R4-1 / R4-5) — the critical path
- `/execute` and `/reports/{id}/run` accept an optional `binds: {name: scalar}` map.
- `OracleClient.run_select(sql, limits=None, binds=None)` calls `cur.execute(sql, binds or {})`.
  **Binds are values, not text** — they never enter the SQL string.
- The SQL-text safety check (`assert_safe_select`) is **unchanged** and still runs first.
- `validate_binds(binds)` (in `src/db.py`) is a chokepoint backstop:
  - keys must match `^[A-Za-z_][A-Za-z0-9_]*$`, ≤ 30 chars;
  - values restricted to scalars: `str`, `int`, `float`, `bool`, `None`, `date`, `datetime`;
  - anything else (dict/list/object) → `ValueError` (fail-closed).
- `coerce_report_binds(parameters, raw_values)` (in `src/core/reports.py`) applies defaults,
  enforces `required`, and coerces per declared `type` (number→int/float, date→`date`,
  string→str) before the values reach `validate_binds`.
- **Scalar binds only in v1** (D-B). `IN (:list)` multi-value expansion is deferred.

### Adversarial expectations (exit gate will probe these)
1. A bind value of `'; DROP TABLE x; --` is bound as an inert literal; the statement stays
   SELECT-only and the value never alters the parsed SQL.
2. A report whose **SQL** is DML/DDL is rejected regardless of binds.
3. Missing required bind → clean 400/validation error; unexpected non-scalar bind → rejected.
4. Bind name not matching the identifier pattern → rejected.

## 4. API contracts (D5)

### 4.1 `/execute` (amended)
Request gains optional `binds: {str: scalar}`. Behaviour otherwise unchanged
(profile-or-inline target, safety gate, limits, audit).

### 4.2 `/reports` (new — D-F parity with `/profiles`)
| Method | Path | Body | Result |
|--------|------|------|--------|
| POST | `/reports` | `ReportCreate` | 201 `Report` |
| GET | `/reports` | — | `[Report]` |
| GET | `/reports/{id}` | — | `Report` / 404 |
| PUT | `/reports/{id}` | `ReportCreate` | `Report` / 404 |
| DELETE | `/reports/{id}` | — | 204 / 404 |
| POST | `/reports/{id}/run` | `{profile_id? , connection? , binds?(raw) , max_rows?}` | execute-shaped result |

`/reports/{id}/run` resolves the target profile (request override → report
`default_profile_id`), coerces `binds` via the report's params, then routes through the
**same** internal execute helper as `/execute` (safety + limits + audit). A missing bound
profile with no override → 400 (UI warns and requires selection — D-H).

### 4.3 `/templates` (new, read-only)
`GET /templates` → `[Template]`; `GET /templates/{id}` → `Template` / 404.

### 4.4 Internal refactor
The body of `/execute` is factored into `_resolve_target(...)` + `_run_sql(...)` so
`/execute` and `/reports/{id}/run` share one chokepoint path (no duplicated safety logic).

## 5. UX (D-E) — sidebar left-nav, single app
- Replace the top `st.tabs(...)` with `st.sidebar.radio("Navigate", SECTIONS)`:
  `Connections · Schema Upload · Explore Schema · Query Builder · Reports · Templates · Settings`.
- Active-connection chooser stays in the sidebar; shared `st.session_state` preserved.
- **Reports** section: list/select report → render a parameter form from `report.parameters`
  → optional profile binding (default + override) → Run (binds coerced, executed via the
  client with binds) → results + CSV/XLSX export; Save/Update/Delete.
- **Templates** section: browse by module → preview SQL (read-only, "review before running")
  → **Load into Query Builder** (sets `generated_sql`) or **Save as report** (persists with
  its parameters).
- `_run_and_display(client, sql, binds=None)` extended to pass binds through.
- Smoke test updated: assert the nav radio options and that every section renders
  exception-free; existing Settings/Connections flows navigate via the nav radio.

## 6. Test plan (D6)
| Area | Tests |
|------|-------|
| Report store | CRUD, duplicate-name, update, delete semantics, file encrypt-n/a, **legacy migration** |
| Bind safety | `validate_binds` accept/reject matrix; injection-as-value stays SELECT-only; DML-with-binds rejected |
| `coerce_report_binds` | defaults applied, required enforced, type coercion (number/date), unknown key rejected |
| `/reports` API | CRUD + 404s; `/reports/{id}/run` happy path (mocked DB) + missing-profile 400 |
| Templates | catalog non-empty; **every template is a safe SELECT**; declared params appear as `:binds` |
| UX | nav radio options; app boots; Reports/Templates render; Settings/Connections still work |

## 7. ADRs
- **ADR-007** — Parameterized reports via bind variables (no string interpolation).
- **ADR-008** — Reports as a core module with API parity (UI + API share one store/chokepoint).

## 8. Out of scope (confirmed, D-I)
Scheduling, charts/visualization, RBAC/sharing, `IN (:list)` multi-value binds, React revival,
EBS schema auto-detection, live-Oracle validation of template SQL (pre-GA RISK-04 pass).

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Initial Phase-4 design (reports v2, bind safety, /reports + /templates, left-nav UX). |
