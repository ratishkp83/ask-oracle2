# D7 — Deployment Plan

> **Document:** Deployment Plan · **Version:** 1.0 · **Status:** Baseline · **Owner:** Engineering/Ops · **Last updated:** 2026-06-10

## 1. Environments

| Env | UI | API | Config source |
|-----|----|----|---------------|
| Local (bare) | `streamlit run src/app.py` | `uvicorn src.api:app` | git-ignored `.env` (via python-dotenv) |
| Local (Docker) | frontend service (node) | api service (`Dockerfile.api.local`) | `env_file: .env` |
| Hosted (Render) | `ask-oracle-reports-ui` | `ask-oracle-reports-api` | Dashboard env vars (`sync: false`) |

## 2. Configuration (environment variables)

| Var | Purpose | Required |
|-----|---------|----------|
| `APP_SECRET_KEY` | Derives Fernet key for profile passwords | **Yes** (for profiles) |
| `GROQ_API_KEY` / `GROQ_MODEL` | Default LLM (Groq) | One LLM key required for NL→SQL |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Default LLM (OpenAI) | Alternative to Groq |
| `MAX_ROWS` / `MAX_EXECUTION_SECONDS` / `MAX_RESULT_BYTES` | Safety limits | No (defaults applied) |
| `STORAGE_DIR` | Location of profiles/reports JSON | No (sensible default) |

> **No secrets in source or `docker-compose.yml`.** All come from env. `.env` is git-ignored.

## 3. Secrets management & rotation runbook

1. Generate `APP_SECRET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. Set provider keys in the appropriate env (local `.env` or Render dashboard).
3. **Rotation (e.g., after exposure — see [risk-register RISK-01](risk-register.md)):** regenerate the key at the provider → update env → restart service. Removing a key from files does **not** un-leak it.
4. **`APP_SECRET_KEY` rotation caveat:** existing encrypted profile passwords cannot be decrypted with a new key; profiles must be re-entered (or a migration run). Documented in `crypto.py`.

## 4. Release procedure

1. Green CI on the branch.
2. Docs current (CHANGELOG entry added).
3. Tag/commit; deploy (Render auto-deploy on push, or `docker compose up --build -d`).
4. Post-deploy: hit `/health`; run profile test against a sandbox.

## 5. Rollback

- Render: redeploy previous successful deploy from dashboard.
- Docker: redeploy previous image/commit.
- Data: `profiles.json`/`reports.json` are file-based; back up `STORAGE_DIR` before destructive changes.

## 6. Monitoring & health

- `/health` for liveness.
- Audit logs (`ask_oracle.audit`) for query attempts (hash + metadata, no secrets).
- **Gap (Phase 6):** Prometheus metrics, structured log shipping, error reference IDs — tracked in [roadmap](roadmap.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Eng/Ops | Baseline; env config, rotation runbook, rollback. |
