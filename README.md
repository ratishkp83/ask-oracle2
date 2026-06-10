# Ask Oracle Reports

A commercial, AI-assisted, **read-only** reporting layer for Oracle Database and
Oracle E-Business Suite (EBS). Connect → Ask (plain English → SQL) or write SQL →
review → run → export. Schema understanding comes from uploaded metadata (CSV/Excel),
so no DB metadata permissions are required. NL→SQL is provider-agnostic (Groq default,
OpenAI optional).

> **Governance:** `/docs` is the source of truth. New here? Read
> [`docs/HANDOFF.md`](docs/HANDOFF.md) then [`docs/00-governance-index.md`](docs/00-governance-index.md).

## Features
- **Connection profiles** — named Oracle connections; passwords **encrypted at rest** (Fernet), never returned.
- **Schema metadata** — upload table/column/PK/FK CSV/Excel (+ optional relationships) and explore tables/joins.
- **Ask in English or SQL** — NL→SQL proposes SQL + explanation + a confidence heuristic; you review/edit before running.
- **Saved reports** — parameterized via **bind variables**, optional connection-profile binding, run + export.
- **EBS templates** — curated GL/AP/AR/PO/OM starter queries (review before running).
- **Export** — CSV / Excel.
- **Left-nav UI** — Connections · Schema Upload · Explore Schema · Query Builder · Reports · Templates · Settings.

## Quickstart
1. Python 3.11+ recommended.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and set at least one LLM key (Groq by default) and
   `APP_SECRET_KEY` (required for connection profiles):
   ```bash
   cp .env.example .env   # then edit
   ```
4. Run the app:
   ```bash
   streamlit run src/app.py
   ```
5. **Connect with a least-privilege, read-only Oracle account** — this is a required
   deployment precondition (see Safety below and [ADR-009](docs/adr/ADR-009-readonly-db-account-precondition.md)).

## Schema File Format
Upload a CSV/Excel with columns:
- table_name
- column_name
- data_type
- is_primary_key (true/false or Y/N)
- is_foreign_key (true/false or Y/N)
- references_table (optional)
- references_column (optional)

Relationships CSV/Excel (optional):
- from_table, from_column, to_table, to_column, relationship_type (optional)

See `samples/` for examples.

## Safety
The "no data modification" guarantee is delivered by **defense in depth** — both layers
are required ([ADR-009](docs/adr/ADR-009-readonly-db-account-precondition.md)):

1. **Application layer.** Only SELECT/CTE queries are allowed. Every query (raw, NL→SQL,
   saved report, or template) is validated by a single central safety chokepoint
   (`src/core/sql_safety.py`): it parses the SQL with sqlglot, requires a read-only
   SELECT/CTE root, rejects stacked statements, DML/DDL/PL-SQL, `SELECT … INTO`, and
   `FOR UPDATE`, and applies a keyword denylist as a backstop. The layer is fail-closed.
   Report/template parameters are passed as **Oracle bind variables — never interpolated**
   into SQL ([ADR-007](docs/adr/ADR-007-parameterized-reports-bind-variables.md)).
2. **Database layer (required).** Connect with a **least-privilege, read-only Oracle
   account** (`CREATE SESSION` + `SELECT` only; no DML, no `EXECUTE` on side-effecting
   packages). A parse gate proves a statement *is* a SELECT, but cannot prove a SELECT
   has no side effects (a SELECT can call a function that writes) — the read-only account
   is what guarantees no writes. See [`docs/07-deployment-plan.md` §0](docs/07-deployment-plan.md).

- Configurable runtime limits: `MAX_ROWS`, `MAX_EXECUTION_SECONDS`, `MAX_RESULT_BYTES` (see `.env.example`).
- NL→SQL only *proposes* SQL; it is never executed automatically. Always review.

## Secrets & configuration
- No API keys live in source or in `docker-compose.yml`. All secrets come from
  environment variables (a git-ignored `.env` locally; dashboard env vars on
  Render). Copy `.env.example` to `.env` and fill in your values.
- `APP_SECRET_KEY` is **required** to save/use connection profiles — it encrypts
  stored passwords at rest (Fernet). Generate one with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- If a key was ever committed, treat it as compromised and **rotate it** at the
  provider; removing it from the repo does not un-leak it.

## Notes
- Uses python-oracledb thin mode; no Oracle client installation required.
- If you need a wallet or different auth, extend `src/db.py` accordingly.

## Run with Docker (recommended)
- Build and start:
  ```bash
  docker compose up --build -d
  ```
- Open `http://localhost:8501`
- Provide Oracle connection details in the sidebar
- Upload your schema CSV/Excel (see `samples/`), optionally relationships CSV

To stop:
```bash
docker compose down
```

## REST API (Swagger)
A FastAPI backend exposes Swagger UI and OpenAPI:
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

Endpoints (full contract: [`docs/05-api-contracts.md`](docs/05-api-contracts.md)):
- GET /health
- POST /test-connection — body: ConnectionConfig (inline, not persisted)
- Connection profiles (passwords encrypted at rest; never returned):
  - POST /profiles — create; body: { name, host, port?, service_name?, sid?, username, password, environment? }
  - GET /profiles — list (ProfilePublic, no password)
  - GET /profiles/{id} — fetch one
  - DELETE /profiles/{id} — remove
  - POST /profiles/{id}/test — open SELECT 1 FROM DUAL using stored credentials
- POST /nl2sql
  - body: { natural_language, schema_csv?, relationships_csv?, model?, llm? }
  - returns: { sql, explanation, confidence: { level, reasons[] } }
- POST /execute (always routed through the safety chokepoint)
  - body: { sql, profile_id? , connection?: ConnectionConfig, max_rows?, binds? }
  - provide **exactly one** of profile_id or connection; `binds` are bound as values, never interpolated
  - returns: { columns, rows, elapsed_seconds, row_count, truncated }
- Saved reports (CRUD + run via the chokepoint):
  - POST /reports · GET /reports · GET /reports/{id} · PUT /reports/{id} · DELETE /reports/{id}
  - POST /reports/{id}/run — body: { profile_id?, connection?, binds?, max_rows? }; binds coerced to the report's declared parameters
- Templates (read-only EBS catalog):
  - GET /templates · GET /templates/{id}

Run the API with Docker compose (already included) or locally with:
```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```
