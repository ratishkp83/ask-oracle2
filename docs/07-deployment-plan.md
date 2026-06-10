# D7 — Deployment Plan

> **Document:** Deployment Plan · **Version:** 1.2 · **Status:** Baseline · **Owner:** Engineering/Ops · **Last updated:** 2026-06-10

## 0. Required database account (read-only) — **non-negotiable precondition**

Ask Oracle Reports must connect with a **least-privilege, read-only Oracle account**.
The application's SELECT/CTE-only safety layer proves the tool *issues* only read-only
statements; the read-only account is what guarantees those statements **cannot modify
data** even if a SELECT invokes a side-effecting/autonomous-transaction function (see
[ADR-009](adr/ADR-009-readonly-db-account-precondition.md), review finding F1). Both
layers are required; neither alone delivers the "no data modification" guarantee.

Provision an account with **only**:
- `CREATE SESSION`;
- `SELECT` on the specific target objects (or a read-only role / `SELECT ANY TABLE` only
  if the deployment explicitly accepts that breadth);
- **no** `INSERT` / `UPDATE` / `DELETE` / `MERGE`;
- **no** `EXECUTE` on side-effecting packages (`DBMS_LOCK`, `DBMS_SCHEDULER`/`DBMS_JOB`,
  `UTL_FILE`/`UTL_HTTP`/`UTL_SMTP`/`UTL_TCP`, `DBMS_AQ`, …).

```sql
-- Illustrative; scope SELECT grants to the objects the analysts need.
CREATE USER ask_oracle_ro IDENTIFIED BY <strong-secret>;
GRANT CREATE SESSION TO ask_oracle_ro;
GRANT SELECT ON apps.ap_invoices_all TO ask_oracle_ro;   -- repeat per object/view
-- Do NOT grant any DML, EXECUTE on writing packages, or DBA roles.
```

Onboarding/release checklist must confirm the connecting profile uses such an account.

## 1. Environments

| Env | UI | API | Config source |
|-----|----|----|---------------|
| Local (bare) | `streamlit run src/app.py` | `uvicorn src.api:app` | git-ignored `.env` (via python-dotenv) |
| Local (Docker) | frontend service (node) | api service (`Dockerfile.api.local`) | `env_file: .env` |
| Hosted (Render) | `ask-oracle2-ui` | `ask-oracle2-api` | Dashboard env vars (`sync: false`) |

## 2. Configuration (environment variables)

| Var | Purpose | Required |
|-----|---------|----------|
| `APP_SECRET_KEY` | Derives Fernet key for profile passwords | **Yes** (for profiles) |
| `GROQ_API_KEY` / `GROQ_MODEL` | Default LLM (Groq) | One LLM key required for NL→SQL |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Default LLM (OpenAI) | Alternative to Groq |
| `MAX_ROWS` / `MAX_EXECUTION_SECONDS` / `MAX_RESULT_BYTES` | Safety limits | No (defaults applied) |
| `STORAGE_DIR` | Location of profiles/reports JSON | No (sensible default) |
| `LOG_LEVEL` | Logging level (`DEBUG`/`INFO`/`WARNING`/…) | No (default `INFO`) |
| `LOG_FORMAT` | `json` (stdout, 12-factor) or `text` (human-readable, local dev) | No (default `json`) |

> **No secrets in source or `docker-compose.yml`.** All come from env. `.env` is git-ignored.

## 3. Secrets management & rotation runbook

1. Generate `APP_SECRET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. Set provider keys in the appropriate env (local `.env` or Render dashboard).
3. **Rotation (e.g., after exposure — see [risk-register RISK-01](risk-register.md)):** regenerate the key at the provider → update env → restart service. Removing a key from files does **not** un-leak it.
4. **`APP_SECRET_KEY` rotation caveat:** existing encrypted profile passwords cannot be decrypted with a new key; profiles must be re-entered (or a migration run). Documented in `crypto.py`.

## 4. Release procedure

1. Green CI on the branch.
2. Docs current (CHANGELOG entry added).
3. **Confirm the connecting Oracle account is least-privilege read-only** (§0 / [ADR-009](adr/ADR-009-readonly-db-account-precondition.md)).
4. Tag/commit; deploy (Render auto-deploy on push, or `docker compose up --build -d`).
5. Post-deploy: hit `/health`; run profile test against a sandbox.

## 5. Rollback

- Render: redeploy previous successful deploy from dashboard.
- Docker: redeploy previous image/commit.
- Data: `profiles.json`/`reports.json` are file-based; back up `STORAGE_DIR` before destructive changes.

## 6. Monitoring & health

- `/health` for liveness.
- **Structured JSON logs to stdout** (Phase 6, [ADR-012](adr/ADR-012-observability-and-error-handling.md)):
  configured by `configure_logging()` at startup; `LOG_LEVEL`/`LOG_FORMAT` env-controlled.
  The platform (Docker/Render) captures stdout — **log shipping/aggregation/retention is the
  deployment platform's responsibility**, not built into the app.
- **Audit logs** (`ask_oracle.audit`) for query attempts (SHA-256 hash + metadata, no secrets),
  now emitted as valid JSON.
- **Error reference IDs:** every error response carries an `error_id` (= the `X-Request-ID`
  correlation id) that keys the matching server-side log line — quote it in support tickets.
  DB-driver detail is logged server-side only, never returned to clients (ITM-015 closed).
- **`GET /metrics`** (Phase 6): in-process query counts (executed/rejected/errored) + latency
  (in-memory; resets on restart; counts only). **Unauthenticated** like `/health` — gate
  behind auth before any multi-tenant/networked exposure (Phase 7, [ITM-009](issue-log.md)).
- **Deferred to Phase 7:** Prometheus/scrape exposition + an APM/error-tracking vendor —
  tracked in [roadmap](roadmap.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Eng/Ops | Baseline; env config, rotation runbook, rollback. |
| 1.1 | 2026-06-10 | Eng/Ops | Phase 4 r1/F1: §0 required least-privilege read-only DB account (ADR-009) + release-checklist gate. |
| 1.2 | 2026-06-10 | Eng/Ops | Phase 6: `LOG_LEVEL`/`LOG_FORMAT` env vars; §6 rewritten for structured JSON logs, error reference IDs, and `/metrics` (ADR-012); Prometheus/APM deferred to Phase 7. |
