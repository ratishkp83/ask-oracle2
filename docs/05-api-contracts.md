# D5 — API Contracts

> **Document:** API Contracts · **Version:** 1.0 · **Status:** Baseline · **Owner:** Engineering · **Last updated:** 2026-06-10
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
→ `200 { sql }` · `400` (no schema, LLM/key error, or unsafe generation)

### POST /execute  *(single safety chokepoint)*
Body: `{ sql, profile_id?, connection?, max_rows? }` — provide **exactly one** of `profile_id` / `connection`
→ `200 { columns, rows, elapsed_seconds, row_count, truncated }`
→ `400` unsafe SQL (with reason) or DB error · `404` unknown profile · `422` neither/both target supplied

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
