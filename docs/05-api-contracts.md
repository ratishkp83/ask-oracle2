# D5 — API Contracts

> **Document:** API Contracts · **Version:** 1.1 · **Status:** Baseline · **Owner:** Engineering · **Last updated:** 2026-06-10
> Service: `Ask Oracle Reports API` v2.0.0 · Swagger: `/docs` · OpenAPI: `/openapi.json`

## Conventions

- Errors use FastAPI's `{ "detail": <string | list> }`. Business errors are `string`; request-validation errors are a `list` (HTTP 422).
- Passwords/keys are **never** returned in any response.
- **Versioning (planned):** introduce a `/v1` path prefix before external GA (tracked in [task-tracker](task-tracker.md)).

## Endpoints

### GET /health
→ `200 { "status": "ok" }`

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
Body: `{ natural_language, schema_csv?, relationships_csv?, model?, llm? }`
`llm = { provider?, model?, api_key?, base_url? }` (omitted fields fall back to server env; `api_key` used transiently, never logged/persisted)
→ `200 { sql, explanation, confidence: { level, reasons[] } }`
  - `explanation`: short rationale (may be `null` if the model omitted it).
  - `confidence.level`: `"High" | "Medium" | "Low"` — deterministic heuristic (schema coverage + parse + identifier resolution); **not** a correctness guarantee.
→ `400` (no schema, unsafe generation, LLM/key error, or `LLM_POLICY` disallows the only available provider)
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

**Example — reject:**
```
POST /execute { "sql": "DELETE FROM emp", "connection": {...} }
→ 400 { "detail": "Only SELECT/CTE queries are allowed; received a DELETE statement." }
```
**Example — success:**
```
POST /execute { "sql": "SELECT 1 FROM DUAL", "profile_id": "ab12…" }
→ 200 { "columns": ["1"], "rows": [[1]], "elapsed_seconds": 0.03, "row_count": 1, "truncated": false }
```

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Baseline; profiles + safe /execute + per-user llm documented. |
| 1.1 | 2026-06-10 | Engineering | Phase 4: `/execute` gains optional `binds` (bound, never interpolated; ADR-007). |
