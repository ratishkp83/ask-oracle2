# D3 — Architecture

> **Document:** Architecture · **Version:** 1.1 · **Status:** Baseline · **Owner:** Engineering · **Last updated:** 2026-06-10

## 1. Container view

```
┌──────────────┐     ┌──────────────────────────┐     ┌───────────────┐
│ Streamlit UI │     │  FastAPI service          │     │ Oracle DB/EBS │
│ (src/app.py) │     │  (src/api.py)             │     │ (thin mode)   │
│  Connections │     │  /health /profiles        │────▶│  SELECT only  │
│  Ask / SQL   │────▶│  /test-connection /nl2sql │     └───────────────┘
│  Reports     │     │  /execute  /reports[/run] │
│  Templates   │     │  /templates               │     ┌───────────────┐
│  Settings    │     └─────────────┬─────────────┘     │ LLM provider  │
└──────┬───────┘                   │                   │ Groq / OpenAI │
       │ (direct import)           │                   └───────────────┘
       ▼                           ▼                          ▲
┌──────────────────────────────────────────────┐             │
│ src/core/ (single source of truth)            │── nl2sql ───┘
│  sql_safety · config · crypto · profiles ·    │
│  reports · templates · audit                  │
└───────────────┬───────────────────────────────┘
                │ reads/writes (encrypted)
                ▼
        storage/ (profiles.json, reports.json) — git-ignored
```

Both the UI and the API converge on `src/core/`. The React/Vite scaffold exists but is not the active UI.

## 2. Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `core/sql_safety.py` | `assert_safe_select()` — layered, fail-closed SELECT/CTE enforcement (see [ADR-001](adr/ADR-001-sql-safety-engine.md)). |
| `core/config.py` | `SafetyLimits` + `load_safety_limits()` from env. |
| `core/crypto.py` | Fernet encrypt/decrypt; key derived from `APP_SECRET_KEY` ([ADR-002](adr/ADR-002-encrypted-profiles.md)). |
| `core/profiles.py` | Profile models + `ProfileStore` (JSON/in-memory); passwords encrypted, never in `ProfilePublic`. |
| `core/audit.py` | Secret-free audit logging (SQL SHA-256 only). |
| `core/reports.py` | Report v2 models + `ReportStore` (JSON/in-memory) + legacy migration; `coerce_report_binds()` (defaults/required/typing, rejects unknown keys). Phase 4. |
| `core/templates.py` | Curated read-only EBS template catalog (GL/AP/AR/PO/OM); parameterized `:bind` SQL, review-before-run. Phase 4. |
| `db.py` | `OracleClient` (thin mode); `run_select(sql, limits, binds)` enforces limits, returns `QueryResult`; `validate_binds()` chokepoint backstop (scalar-only, never interpolated — [ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)). |
| `nl2sql.py` | NL→SQL orchestration → `NLSQLResult` (sql + explanation + confidence); selects a provider via policy. |
| `core/llm/` | Provider abstraction: `base` (LLMProvider/LLMConfig/NLSQLResult), `providers` (External/Local), `policy` (`LLM_POLICY` toggle + selection), `redaction` (strict external context + tripwire), `confidence` (heuristic). |
| `schema.py` | Metadata model + CSV/Excel parsers + prompt context. |
| `storage.py` | JSON persistence for manual connection config + storage dir resolution. |
| `api.py` / `app.py` | FastAPI routes / Streamlit UI. |

## 3. Key flows

**NL→SQL (propose only):** UI/API → `generate_sql_from_nl(q, schema, llm)` → `select_provider` (per `LLM_POLICY`) → strict redaction (`build_external_context` + `assert_no_values` for external) → provider call → parse SQL + explanation → `assert_safe_select` → heuristic `assess_confidence` → `NLSQLResult`. **Never executed automatically.**

**Execute (single chokepoint):** request (`profile_id` *or* inline `connection`, optional `binds`) → `_resolve_target` (creds) → `_run_sql`: `assert_safe_select` on the SQL **text** (reject → 400 + audit) → `validate_binds` → `OracleClient.run_select(sql, limits, binds)` → `cur.execute(sql, binds)` under `SafetyLimits` → audit (hash only) → `{columns, rows, elapsed, row_count, truncated}`.

**Run report:** `GET` report → `coerce_report_binds(params, raw_values)` (defaults/required/typing, reject unknown) → resolve target (request override → report `default_profile_id`) → **same** `_run_sql` chokepoint. Binds are bound as values, never interpolated ([ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)); the SELECT-only verdict is independent of bind values.

**Profile test:** resolve (decrypt) → `SELECT 1 FROM DUAL` → ok/elapsed.

## 4. Cross-cutting concerns

- **Safety:** one enforcer, used by API, UI, and NL→SQL post-check. The parse gate proves
  a statement *is* a read-only SELECT/CTE; it cannot prove a SELECT has no side effects
  (a SELECT may call a side-effecting/autonomous-txn function). The "no data modification"
  guarantee therefore requires **defense in depth**: the parse gate **plus** a required
  least-privilege read-only DB account ([ADR-009](adr/ADR-009-readonly-db-account-precondition.md), [Deployment §0](07-deployment-plan.md)).
- **Secrets:** env-only; no inline keys; `.env` git-ignored; profile passwords encrypted at rest.
- **Audit:** every attempt (allowed/rejected) logged with SQL fingerprint, never raw SQL/creds.
- **Limits:** centrally configured; per-request `max_rows` may only narrow.

## 5. Tech stack

Python 3.11/3.13 · FastAPI · Streamlit · python-oracledb (thin) · sqlglot · cryptography (Fernet) · pandas · openai-compatible client (Groq/OpenAI) · Docker Compose / Render.

## 6. Architecture decisions

See [ADR index](adr/). Ratified: ADR-001…009.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Baseline incl. Phase-2 `src/core/` and chokepoint. |
| 1.1 | 2026-06-10 | Engineering | Phase 4: `core/reports` + `core/templates`, bind-through-chokepoint flow, `/reports` + `/templates` endpoints, left-nav UI. |
