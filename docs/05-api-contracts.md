# D5 — API Contracts

> **Document:** API Contracts · **Version:** 1.10 · **Status:** Baseline · **Owner:** Engineering · **Last updated:** 2026-06-12
> Service: `Ask Oracle Reports API` v2.2.0 · Swagger: `/docs` · OpenAPI: `/openapi.json`

## Conventions

- **Authentication** *(Phase 6.5, opt-in — [ADR-013](adr/ADR-013-network-edge-hardening.md))*:
  when env `APP_API_KEY` is set, every endpoint **except `GET /health`** requires the request
  header `X-API-Key: <key>`; missing/wrong key → `401 { "detail": "Not authenticated.",
  "error_id": … }`. With the env var unset (the default), no endpoint requires a key — the
  historical single-user posture is unchanged. CORS origins come from env `ALLOWED_ORIGINS`
  (comma-separated; default `http://localhost:8501,http://localhost:3000`); a literal `*`
  forfeits credentials.
- **Error envelope** *(Phase 6)*: every error body is `{ "detail": <string | list>, "error_id": <hex> }`.
  `detail` is unchanged from before — business errors are a `string`, request-validation
  errors are a `list` (HTTP 422). `error_id` is **additive** and equals the request's
  correlation id. ([ADR-012](adr/ADR-012-observability-and-error-handling.md))
- **Correlation** *(Phase 6)*: every response carries an `X-Request-ID` header. A client may
  supply `X-Request-ID` on the request to set the id; otherwise the server generates one. The
  same value is the `error_id` in error bodies and the key for the matching server log line.
- **DB/driver errors are sanitized** *(Phase 6, ITM-015)*: `/execute`, `/reports/{id}/run`,
  `/schemas/introspect`, `/test-connection`, and `/profiles/{id}/test` return a **generic**
  `detail = "Database error — see server logs."` (+ `error_id`) for raw driver/connection
  failures; the full detail is logged server-side only. Safety-rejection reasons and
  validation messages are **not** sanitized — they stay verbatim.
- Passwords/keys are **never** returned in any response.
- **Versioning** *(Phase 7, T-18)*: every route is mounted **twice** — at the root (back-compat)
  **and** under **`/v1`** (e.g. `/v1/execute`, `/v1/packs`). Both forms are identical and both are
  covered by the same auth dependency, exception handlers, and middleware. The auth exemption
  covers **both** `/health` and `/v1/health` (liveness probes).

## Endpoints

### GET /health
→ `200 { "status": "ok" }` — minimal body; **always exempt from auth** (liveness probes).

### GET /metrics  *(Phase 6, read-only)*
In-process operational metrics — query counts + latency only (no data, SQL, or secrets);
**in-memory**, resets on restart. **Requires `X-API-Key` when auth is enabled** (ADR-013).
→ `200 { "counters": { "queries_executed", "queries_rejected", "queries_errored" }, "latency_seconds": { "count", "avg", "max" } }`

### POST /profiles
Body: `{ name, host, port?=1521, service_name?, sid?, username, password, environment?=DEV }` (service_name **or** sid required)
→ `201 ProfilePublic` · `409` duplicate name / missing service|sid · `500` `APP_SECRET_KEY` not configured

### GET /profiles
→ `200 ProfilePublic[]`

### GET /profiles/{id}
→ `200 ProfilePublic` · `404` not found

### DELETE /profiles/{id}
→ `204` · `404` not found

### POST /profiles/{id}/test
→ `200 { ok: true, elapsed_seconds }` · `404` not found · `400` connection error

### POST /test-connection
Body: `ConnectionConfig { host, port?=1521, service_name?, sid?, username, password }` (service_name or sid required)
→ `200 { ok, elapsed_seconds, columns, rows }` · `400` connection error

### POST /nl2sql
Body: `{ natural_language, schema_csv?, relationships_csv?, model?, llm?, ebs_modules? }`
`llm = { provider?, model?, api_key?, base_url? }` (omitted fields fall back to server env; `api_key` used transiently, never logged/persisted).
`ebs_modules?` *(Phase 7, opt-in)*: list of EBS modules (`["GL","AP","AR","PO","OM"]`) whose curated **metadata** packs (table/column descriptions + glossary, no row data) are appended to the external prompt context — covered by the same redaction tripwire ([ADR-015](adr/ADR-015-ebs-metadata-packs.md)). Omitted/empty → unchanged behaviour.
→ `200 { sql, explanation, confidence: { level, reasons[] } }`
  - `explanation`: short rationale (may be `null` if the model omitted it).
  - `confidence.level`: `"High" | "Medium" | "Low"` — deterministic heuristic (schema coverage + parse + identifier resolution); **not** a correctness guarantee.
→ `400` (no schema, unsafe generation, LLM/key error, or `LLM_POLICY` disallows the only available provider) — these intentional messages stay verbatim; an **unexpected** failure returns the generic `detail = "Could not generate SQL — see server logs."` + `error_id` with full detail logged server-side (Phase 6.5, ITM-017)
- Provider/redaction governed by `LLM_POLICY` (`local_only` | `local_external` | `external_disabled`); external prompts carry **schema names only**.

### POST /execute  *(single safety chokepoint)*
Body: `{ sql, profile_id?, connection?, max_rows?, binds? }` — provide **exactly one** of `profile_id` / `connection`
→ `200 { columns, rows, elapsed_seconds, row_count, truncated }`
→ `400` unsafe SQL (with reason), invalid bind, or DB error · `404` unknown profile · `422` neither/both target supplied

- `binds` *(Phase 4)*: optional `{ name: scalar }` map bound as Oracle **bind variables**
  (`:name`), passed to the driver as values — **never interpolated** into `sql` (ADR-007).
  Names must match `^[A-Za-z_][A-Za-z0-9_]*$` (≤30 chars); values must be scalar
  (string/number/bool/null/date); non-scalars are rejected `400`. The SQL-text safety
  check is unchanged and still runs first.

**Example — reject (safety reason verbatim + error_id):**
```
POST /execute { "sql": "DELETE FROM emp", "connection": {...} }
→ 400 { "detail": "Only SELECT/CTE queries are allowed; received a DELETE statement.",
        "error_id": "9f2c…" }
```
**Example — DB/driver error (sanitized, ITM-015):**
```
POST /execute { "sql": "SELECT 1 FROM DUAL", "connection": {...bad host...} }
→ 400 { "detail": "Database error — see server logs.", "error_id": "1a7b…" }
   (full ORA-/DSN detail is logged server-side under error_id 1a7b…, never returned)
```
**Example — success:**
```
POST /execute { "sql": "SELECT 1 FROM DUAL", "profile_id": "ab12…" }
→ 200 { "columns": ["1"], "rows": [[1]], "elapsed_seconds": 0.03, "row_count": 1, "truncated": false }
```

### Saved reports *(Phase 4)*
`Report = { id, name, description, sql, parameters[], default_profile_id?, template_id?, created_at, updated_at }`
`ReportParam = { name, label, type∈{string,number,date}, required, default? }` — `name` is the bind name.

#### POST /reports
Body: `ReportCreate { name, description?, sql?, parameters?[], default_profile_id?, template_id? }`
→ `201 Report` · `409` duplicate name

#### GET /reports → `200 Report[]`
#### GET /reports/{id} → `200 Report` · `404` not found
#### PUT /reports/{id}
Body: `ReportCreate` → `200 Report` · `404` not found · `409` duplicate name
#### DELETE /reports/{id} → `204` · `404` not found

#### POST /reports/{id}/run  *(executes via the /execute chokepoint)*
Body: `{ profile_id?, connection?, binds?, max_rows? }` — `binds` are **raw** values keyed by
parameter name; they are coerced via the report's declared params (defaults applied,
`required` enforced, typed, unknown keys rejected) then bound as values.
Connection target: `profile_id`/`connection` from the request, else the report's
`default_profile_id`.
→ `200 { columns, rows, elapsed_seconds, row_count, truncated }`
→ `400` unsafe SQL / bad-or-missing bind / no connection target · `404` unknown report or bound profile

### Templates *(Phase 4, read-only)*
`Template = { id, module∈{GL,AP,AR,PO,OM}, name, description, sql, parameters[] }` — curated
standard-EBS starter queries; review before running; never auto-executed.
#### GET /templates → `200 Template[]`
#### GET /templates/{id} → `200 Template` · `404` not found

### EBS metadata packs *(Phase 7, read-only — [ADR-015](adr/ADR-015-ebs-metadata-packs.md))*
`EbsPack = { module∈{GL,AP,AR,PO,OM}, name, tables[TableNote], glossary[GlossaryTerm] }` —
`TableNote = { table, description, key_columns[], joins[] }`; `GlossaryTerm = { term, table, column?, note? }`.
Curated **metadata only** (no row data); review-before-run like templates.
#### GET /packs → `200 EbsPack[]`
#### GET /packs/{module} → `200 EbsPack` (case-insensitive) · `404` `"Unknown EBS module."`

### Saved schemas & introspection *(Phase 5)*
`SchemaRecord = { id, name, source∈{upload,introspection}, profile_id?, table_count, created_at, updated_at, definition }`
— `definition` is the serialized schema (tables/columns/relationships); **metadata only**.
`SchemaSummary` = `SchemaRecord` without `definition` (list view).

#### POST /schemas
Body: `{ name, definition? }` **or** `{ name, schema_csv, relationships_csv? }` (provide one source)
→ `201 SchemaRecord` · `409` duplicate name · `422` no source
#### GET /schemas → `200 SchemaSummary[]`
#### GET /schemas/{id} → `200 SchemaRecord` (full) · `404` not found
#### DELETE /schemas/{id} → `204` · `404` not found

#### POST /schemas/introspect  *(SELECT-only, via the chokepoint — [ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md))*
Body: `{ profile_id? | connection?, owner, table_like?="%", save?=false, name? }` — provide
**exactly one** of `profile_id`/`connection`. Builds a schema from `ALL_*` data-dictionary
views (bind-parameterized, capped by `SafetyLimits`); `ALL_*` only; columns-only + a warning
if constraint views aren't visible.
→ `200 { definition, table_count, warnings[], truncated, saved?: SchemaSummary }`
→ `400` blank owner / DB error · `404` unknown profile · `409` duplicate name (when `save`) · `422` neither/both target

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Baseline; profiles + safe /execute + per-user llm documented. |
| 1.1 | 2026-06-10 | Engineering | Phase 4: `/execute` gains optional `binds` (bound, never interpolated; ADR-007). |
| 1.2 | 2026-06-10 | Engineering | Phase 4: `/reports` CRUD + `/reports/{id}/run` (runs via chokepoint) and read-only `/templates` documented. |
| 1.3 | 2026-06-10 | Engineering | Phase 5: `/schemas` CRUD + `/schemas/introspect` (SELECT-only dictionary introspection via the chokepoint). |
| 1.4 | 2026-06-10 | Engineering | Phase 6 (B2): additive `error_id` on every error body; `X-Request-ID` correlation header; DB/driver errors sanitized to a generic message (ITM-015); ADR-012. |
| 1.5 | 2026-06-10 | Engineering | Phase 6 (B3): read-only `GET /metrics` (in-process query counts + latency). |
| 1.6 | 2026-06-11 | Engineering | Phase 6.5 (B1): opt-in `X-API-Key` auth (`APP_API_KEY`; `/health` exempt, `/metrics` gated) + env-driven CORS (`ALLOWED_ORIGINS`); service v2.2.0; ADR-013 (closes ITM-009). |
| 1.7 | 2026-06-11 | Engineering | Phase 6.5 (B5): `/nl2sql` unexpected failures return generic detail + `error_id` (ITM-017); intentional `ValueError`/`LLMError` and the profiles `SecretConfigError` 500 stay verbatim (now with a server-side breadcrumb). |
| 1.8 | 2026-06-12 | Engineering | Phase 7 (B2): `/nl2sql` gains optional `ebs_modules[]` (opt-in EBS metadata-pack context; ADR-015). |
| 1.9 | 2026-06-12 | Engineering | Phase 7 (B4): read-only `GET /packs` + `GET /packs/{module}` (curated EBS metadata packs; ADR-015). |
| 1.10 | 2026-06-12 | Engineering | Phase 7 (B5): every route also mounted under **`/v1`** (T-18) via an `APIRouter` included twice; back-compat preserved; `/v1/health` also auth-exempt. |
