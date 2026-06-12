# D3 — Architecture

> **Document:** Architecture · **Version:** 1.7 · **Status:** Baseline · **Owner:** Engineering · **Last updated:** 2026-06-12

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
| `core/audit.py` | Secret-free audit logging (SQL SHA-256 only); emits valid JSON via the formatter. |
| `core/logging_config.py` | `configure_logging()` — idempotent structured logging (JSON to stdout; `LOG_LEVEL`/`LOG_FORMAT`); `request_id` `ContextVar` + accessors; `JsonFormatter`/`TextFormatter` ([ADR-012](adr/ADR-012-observability-and-error-handling.md)). Phase 6. |
| `core/errors.py` | Shared (API + UI) DB-error sanitization: `log_error()` (secret-free), `sanitize_db_error_for_ui()`, `GENERIC_*` messages — closes ITM-015 ([ADR-012](adr/ADR-012-observability-and-error-handling.md)). Phase 6. |
| `core/metrics.py` | Thread-safe in-process counters (executed/rejected/errored) + latency; `snapshot()` for `GET /metrics` ([ADR-012](adr/ADR-012-observability-and-error-handling.md)). Phase 6. |
| `core/auth.py` | Opt-in API-key dependency (`X-API-Key` vs env `APP_API_KEY`, constant-time; `/health` exempt) — [ADR-013](adr/ADR-013-network-edge-hardening.md). Phase 6.5. |
| `core/fileio.py` | `atomic_write_json()` — temp + fsync + `os.replace`, shared by all four JSON stores ([ADR-014](adr/ADR-014-file-store-durability.md)). Phase 6.5. |
| `core/reports.py` | Report v2 models + `ReportStore` (JSON/in-memory) + legacy migration; `coerce_report_binds()` (defaults/required/typing, rejects unknown keys). Phase 4. |
| `core/templates.py` | Curated read-only EBS template catalog (GL/AP/AR/PO/OM); parameterized `:bind` SQL, review-before-run. Phase 4. |
| `core/ebs_packs.py` | Curated read-only EBS **metadata** packs (table/column descriptions, join hints, business-term glossary) per module; `build_ebs_context()` feeds opt-in, redaction-safe NL→SQL context ([ADR-015](adr/ADR-015-ebs-metadata-packs.md)). Phase 7. |
| `core/schema_store.py` | `SchemaRecord` + `SchemaStore` (JSON/in-memory); persisted dictionary snapshots, metadata only ([ADR-011](adr/ADR-011-schema-persistence-store.md)). Phase 5. |
| `core/introspection.py` | Live SELECT-only schema introspection from `ALL_*` views via `run_select` (bind-parameterized, scoped/capped, graceful) — [ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md). Phase 5. |
| `db.py` | `OracleClient` (thin mode); `run_select(sql, limits, binds)` enforces limits, returns `QueryResult`; `validate_binds()` chokepoint backstop (scalar-only, never interpolated — [ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)). |
| `nl2sql.py` | NL→SQL orchestration → `NLSQLResult` (sql + explanation + confidence); selects a provider via policy. |
| `core/llm/` | Provider abstraction: `base` (LLMProvider/LLMConfig/NLSQLResult), `providers` (External/Local), `policy` (`LLM_POLICY` toggle + selection), `redaction` (strict external context + tripwire), `confidence` (heuristic), `pii` (optional opt-in NL-question PII scrubbing on external send, `SCRUB_PII`; ITM-008). |
| `schema.py` | Metadata model + CSV/Excel parsers + prompt context; data-dictionary helpers (`find_columns`/`references_out`/`referenced_by`) + serialization. |
| `storage.py` | Storage-dir resolution + one-time legacy `connection.json` migration (`migrate_legacy_connection`, read-and-delete; the write path was retired in Round C1/ITM-006). |
| `api.py` / `app.py` | FastAPI routes / Streamlit UI. |

## 3. Key flows

**NL→SQL (propose only):** UI/API → `generate_sql_from_nl(q, schema, llm)` → `select_provider` (per `LLM_POLICY`) → strict redaction (`build_external_context` + `assert_no_values` for external) → provider call → parse SQL + explanation → `assert_safe_select` → heuristic `assess_confidence` → `NLSQLResult`. **Never executed automatically.**

**Execute (single chokepoint):** request (`profile_id` *or* inline `connection`, optional `binds`) → `_resolve_target` (creds) → `_run_sql`: `assert_safe_select` on the SQL **text** (reject → 400 + audit) → `validate_binds` → `OracleClient.run_select(sql, limits, binds)` → `cur.execute(sql, binds)` under `SafetyLimits` → audit (hash only) → `{columns, rows, elapsed, row_count, truncated}`.

**Run report:** `GET` report → `coerce_report_binds(params, raw_values)` (defaults/required/typing, reject unknown) → resolve target (request override → report `default_profile_id`) → **same** `_run_sql` chokepoint. Binds are bound as values, never interpolated ([ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)); the SELECT-only verdict is independent of bind values.

**Schema introspection (Phase 5):** `introspect_schema(client, owner, table_like)` → SELECT-only
queries over `ALL_TAB_COLUMNS` / `ALL_CONSTRAINTS` / `ALL_CONS_COLUMNS` via the **same**
`run_select` chokepoint (bind-parameterized, capped by `SafetyLimits`, `ALL_*` only) → mappers
build a `Schema` → optionally saved to the `SchemaStore`. Degrades to columns-only on missing
constraint-view privileges ([ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md)).

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
- **Observability (Phase 6):** structured JSON logs to stdout via `configure_logging()`
  (`LOG_LEVEL`/`LOG_FORMAT`); a per-request `request_id` (= client `error_id`) stamped on
  every record and echoed as `X-Request-ID`; raw DB-driver errors sanitized to a generic
  message + `error_id` (full detail server-side) by the shared `core/errors` helper used by
  **both** API and UI; in-process metrics via `GET /metrics` ([ADR-012](adr/ADR-012-observability-and-error-handling.md)).

## 5. Tech stack

Python 3.11/3.13 · FastAPI · Streamlit · python-oracledb (thin) · sqlglot · cryptography (Fernet) · pandas · openai-compatible client (Groq/OpenAI) · Docker Compose / Render.

## 6. Architecture decisions

See [ADR index](adr/). Ratified: ADR-001…012.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Baseline incl. Phase-2 `src/core/` and chokepoint. |
| 1.1 | 2026-06-10 | Engineering | Phase 4: `core/reports` + `core/templates`, bind-through-chokepoint flow, `/reports` + `/templates` endpoints, left-nav UI. |
| 1.2 | 2026-06-10 | Engineering | Phase 5: `core/schema_store` + `core/introspection`, schema-introspection flow (via chokepoint), dictionary helpers; ADR-010/011. |
| 1.4 | 2026-06-11 | Engineering | Phase 6.5: `core/auth.py` (opt-in API-key edge, ADR-013) + `core/fileio.py` (atomic store writes, ADR-014) added to the module table. |
| 1.5 | 2026-06-11 | Engineering | Round C1/B2 (ITM-006): `storage.py` row updated — `connection.json` write path retired; read-and-delete migration only. |
| 1.6 | 2026-06-11 | Engineering | Round C1/B3 (ITM-008): `core/llm/pii.py` added to the `core/llm/` row (optional NL-question PII scrubbing). |
| 1.7 | 2026-06-12 | Engineering | Phase 7 (B1): `core/ebs_packs.py` (curated EBS metadata packs / glossary, ADR-015) added to the module table. |
| 1.3 | 2026-06-10 | Engineering | Phase 6 (B1): `core/logging_config` (structured JSON logging, `request_id`); audit emits JSON; Observability cross-cutting concern; ADR-012. |
