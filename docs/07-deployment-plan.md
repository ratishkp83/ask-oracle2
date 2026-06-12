# D7 — Deployment Plan

> **Document:** Deployment Plan · **Version:** 1.7 · **Status:** Baseline · **Owner:** Engineering/Ops · **Last updated:** 2026-06-12

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
| Local (Docker) | `docker compose --profile ui up --build` (`Dockerfile.local`, Python 3.13-slim) | `docker compose --profile api up --build` (`Dockerfile.api.local`, Python 3.13-slim) | `env_file: .env` — copy `.env.example` → `.env` |
| Hosted (Render) | `ask-oracle2-ui` (`render.yaml`, Python 3.13) | `ask-oracle2-api` (`render.yaml`, Python 3.13) | Dashboard env vars (`sync: false` for secrets) |

> **Docker single-worker constraint (RISK-16):** both Docker services write to the same
> named `storage` volume. Run only **one profile at a time** (`--profile api` *or*
> `--profile ui`). Concurrent writes to the same JSON store are not safe. On Render each
> service has its own ephemeral filesystem (no shared store; storage resets on redeploy
> unless a Render Disk is mounted at `/opt/render/project/src/storage`).

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
| `APP_API_KEY` | Enables API auth: every endpoint except `/health` then requires `X-API-Key` ([ADR-013](adr/ADR-013-network-edge-hardening.md)) | **Yes for any networked exposure**; unset = open (localhost only) |
| `ALLOWED_ORIGINS` | CORS origins, comma-separated explicit list (a literal `*` forfeits credentials; blank/whitespace falls back to the default). **Read once at startup — changing it requires a process restart** (unlike `APP_API_KEY`, which is read per-request) | No (default `http://localhost:8501,http://localhost:3000`) |
| `LLM_POLICY` | Controls external-LLM access: `local_external` (default — use external if key present), `local_only` (no external sends), `external_disabled` (block all LLM) | No (default `local_external`) |
| `SCRUB_PII` | When truthy, masks PII (email/SSN/card/phone) in the NL question before an **external** LLM send (ITM-008). Opt-in — over-masking can degrade queries | No (default **off**) |

> **No secrets in source or `docker-compose.yml`.** All come from env. `.env` is git-ignored.

> **Network exposure rule (ADR-013):** binding beyond localhost (e.g. `--host 0.0.0.0`, which
> Docker requires *inside* the container) is only acceptable when **either** the port is not
> published beyond a trusted network **or** `APP_API_KEY` is set and `ALLOWED_ORIGINS` lists
> the real origins. Never publish the API with auth unset.

## 3. Secrets management & rotation runbook

1. Generate `APP_SECRET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. Set provider keys in the appropriate env (local `.env` or Render dashboard).
3. **Rotation (e.g., after exposure — see [risk-register RISK-01](risk-register.md)):** regenerate the key at the provider → update env → restart service. Removing a key from files does **not** un-leak it.
4. **`APP_SECRET_KEY` rotation caveat:** existing encrypted profile passwords cannot be decrypted with a new key; profiles must be re-entered (or a migration run). Documented in `crypto.py`.

## 4. Release procedure

1. Green CI on the branch.
2. Docs current (CHANGELOG entry added).
3. **Confirm the connecting Oracle account is least-privilege read-only** (§0 / [ADR-009](adr/ADR-009-readonly-db-account-precondition.md)).
4. **Confirm `APP_SECRET_KEY` is set** in the target environment (profiles cannot be created without it).
5. **For any networked / non-localhost exposure:** confirm `APP_API_KEY` is set and `ALLOWED_ORIGINS` lists only trusted origins (ADR-013). Never deploy to a public URL without auth.
6. Tag/commit; deploy (Render auto-deploy on push, or `docker compose --profile api up --build -d` / `docker compose --profile ui up --build -d`).
7. Post-deploy: hit `/health`; run a profile test against a sandbox.

## 5. Render persistent storage (ITM-019)

Render free-plan services have **ephemeral filesystems** — `STORAGE_DIR` is wiped on every
redeploy. For production use you must add a **Render Disk** (the simplest path — no code
change required) or accept ephemeral state for short-lived pilots.

### Why Render Disk (not SQLite / PostgreSQL)
The existing JSON+atomic-write stores are production-quality (ADR-014; atomic temp+fsync+`os.replace`,
corrupt-record quarantine). SQLite still requires a disk for persistence (same cost, more code).
PostgreSQL adds an external DB dependency that conflicts with the product's identity. Render Disk
is mount-and-forget: the app writes to `STORAGE_DIR` exactly as it does locally.

### Setup steps (per service)
1. In the Render dashboard, upgrade the service plan from **free → starter** (or higher).
2. Under the service's **Disks** tab, click **Add Disk**:
   - **Name:** `ask-oracle2-api-storage` (or `-ui-storage` for the UI service)
   - **Mount path:** `/opt/render/project/src/storage` (must match `STORAGE_DIR`)
   - **Size:** 1 GB (sufficient for profiles/reports/schemas at any realistic scale)
3. Alternatively, uncomment the `disk:` block in `render.yaml` and redeploy — Render will
   provision the disk automatically on the next deploy.

### Disk independence
Each Render service (api, ui) has its **own disk**. Profiles/reports created in the UI service
are not visible to the API service and vice versa — they have separate filesystems. This matches
the single-worker-per-store constraint (RISK-16) and is expected behavior; users of the API
manage their own profiles via the API.

### Rollback / data safety
- Always back up `STORAGE_DIR` before destructive operations (`profiles.json`, `reports.json`,
  `schemas.json`).
- Render Disk data persists across redeployments but not across disk deletions. Use Render's
  disk snapshot feature (if available on your plan) for additional protection.
- `APP_SECRET_KEY` rotation invalidates all encrypted profile passwords (re-entry required) —
  see §3 rotation runbook.

## 6. Rollback

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
  (in-memory; resets on restart; counts only). **Auth-gated when `APP_API_KEY` is set**
  (Phase 6.5, ADR-013); `/health` alone stays open for liveness probes.
- **Deferred to Phase 7:** Prometheus/scrape exposition + an APM/error-tracking vendor —
  tracked in [roadmap](roadmap.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Eng/Ops | Baseline; env config, rotation runbook, rollback. |
| 1.1 | 2026-06-10 | Eng/Ops | Phase 4 r1/F1: §0 required least-privilege read-only DB account (ADR-009) + release-checklist gate. |
| 1.2 | 2026-06-10 | Eng/Ops | Phase 6: `LOG_LEVEL`/`LOG_FORMAT` env vars; §6 rewritten for structured JSON logs, error reference IDs, and `/metrics` (ADR-012); Prometheus/APM deferred to Phase 7. |
| 1.3 | 2026-06-11 | Eng/Ops | Phase 6.5 (B1): `APP_API_KEY`/`ALLOWED_ORIGINS` env vars + network-exposure rule (ADR-013); `/metrics` auth-gated when enabled. |
| 1.4 | 2026-06-11 | Eng/Ops | Phase 6.5 review r1/R4: documented `ALLOWED_ORIGINS` is read once at startup (restart to change) vs `APP_API_KEY` per-request; blank-value fallback noted. |
| 1.5 | 2026-06-11 | Eng/Ops | Round C1/B3: `SCRUB_PII` env flag added (optional NL-question PII scrubbing on external send; ITM-008). |
| 1.7 | 2026-06-12 | Eng/Ops | ITM-019 resolved: decision = Render Disk (no code change; existing JSON stores are correct); `render.yaml` adds commented `disk:` blocks with setup instructions for both services; §5 "Render persistent storage" section added (why Render Disk, setup steps, disk independence, rollback). Monitoring section renumbered to §7. |
| 1.6 | 2026-06-12 | Eng/Ops | Deployment GA-readiness hardening: `render.yaml` adds `APP_SECRET_KEY`/`APP_API_KEY`/`ALLOWED_ORIGINS`/`LOG_LEVEL`/`LOG_FORMAT`/`STORAGE_DIR` + Python 3.13.0; Dockerfiles pinned to Python 3.13-slim (matches CI matrix); `docker-compose.yml` adds Compose profiles (`--profile api|ui|frontend`), named `storage` volume, `ui` (Streamlit) service; `.env.example` adds 6 missing vars (`APP_API_KEY`, `ALLOWED_ORIGINS`, `LLM_POLICY`, `SCRUB_PII`, `LOG_LEVEL`, `LOG_FORMAT`); §2 adds `LLM_POLICY`; §4 release checklist adds APP_SECRET_KEY/APP_API_KEY/ALLOWED_ORIGINS gates; §1 Docker notes updated for profiles + single-worker constraint. |
