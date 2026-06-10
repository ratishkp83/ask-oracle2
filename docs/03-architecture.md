# D3 — Architecture

> **Document:** Architecture · **Version:** 1.0 · **Status:** Baseline · **Owner:** Engineering · **Last updated:** 2026-06-10

## 1. Container view

```
┌──────────────┐     ┌──────────────────────────┐     ┌───────────────┐
│ Streamlit UI │     │  FastAPI service          │     │ Oracle DB/EBS │
│ (src/app.py) │     │  (src/api.py)             │     │ (thin mode)   │
│  Connections │     │  /health /profiles        │────▶│  SELECT only  │
│  Ask / SQL   │────▶│  /test-connection         │     └───────────────┘
│  Reports     │     │  /nl2sql  /execute        │
│  Settings    │     └─────────────┬─────────────┘     ┌───────────────┐
└──────┬───────┘                   │                   │ LLM provider  │
       │ (direct import)           │                   │ Groq / OpenAI │
       ▼                           ▼                   └───────────────┘
┌──────────────────────────────────────────────┐            ▲
│ src/core/ (single source of truth)            │            │
│  sql_safety · config · crypto · profiles ·    │── nl2sql ──┘
│  audit                                        │
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
| `db.py` | `OracleClient` (thin mode); `run_select()` enforces limits, returns `QueryResult`. |
| `nl2sql.py` | NL→SQL orchestration → `NLSQLResult` (sql + explanation + confidence); selects a provider via policy. |
| `core/llm/` | Provider abstraction: `base` (LLMProvider/LLMConfig/NLSQLResult), `providers` (External/Local), `policy` (`LLM_POLICY` toggle + selection), `redaction` (strict external context + tripwire), `confidence` (heuristic). |
| `schema.py` | Metadata model + CSV/Excel parsers + prompt context. |
| `storage.py` | JSON persistence for reports/connection config + storage dir resolution. |
| `api.py` / `app.py` | FastAPI routes / Streamlit UI. |

## 3. Key flows

**NL→SQL (propose only):** UI/API → `generate_sql_from_nl(q, schema, llm)` → `select_provider` (per `LLM_POLICY`) → strict redaction (`build_external_context` + `assert_no_values` for external) → provider call → parse SQL + explanation → `assert_safe_select` → heuristic `assess_confidence` → `NLSQLResult`. **Never executed automatically.**

**Execute (single chokepoint):** request (`profile_id` *or* inline `connection`) → resolve creds → `assert_safe_select` (reject → 400 + audit) → `OracleClient.run_select` under `SafetyLimits` (`call_timeout`, row cap, byte cap) → audit (hash only) → `{columns, rows, elapsed, row_count, truncated}`.

**Profile test:** resolve (decrypt) → `SELECT 1 FROM DUAL` → ok/elapsed.

## 4. Cross-cutting concerns

- **Safety:** one enforcer, used by API, UI, and NL→SQL post-check.
- **Secrets:** env-only; no inline keys; `.env` git-ignored; profile passwords encrypted at rest.
- **Audit:** every attempt (allowed/rejected) logged with SQL fingerprint, never raw SQL/creds.
- **Limits:** centrally configured; per-request `max_rows` may only narrow.

## 5. Tech stack

Python 3.11/3.13 · FastAPI · Streamlit · python-oracledb (thin) · sqlglot · cryptography (Fernet) · pandas · openai-compatible client (Groq/OpenAI) · Docker Compose / Render.

## 6. Architecture decisions

See [ADR index](adr/). Ratified: ADR-001…005.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Baseline incl. Phase-2 `src/core/` and chokepoint. |
