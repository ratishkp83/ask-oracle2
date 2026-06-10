# Smart Report Builder (Oracle)

An intuitive Streamlit app that connects to Oracle Database and lets users build reports using either raw SQL or plain English (NL → SQL via OpenAI). Schema understanding comes from uploaded metadata (CSV/Excel) so no DB metadata permissions are required.

## Features
- Secure Oracle connection (host, port, service name/SID, username, password)
- Upload schema CSV/Excel with table/column/PK/FK info
- Upload relationship CSV to define join paths
- Explore tables and relationships
- Query in two modes: Natural Language or Raw SQL
- Execute against Oracle and view results
- Export to CSV/Excel
- Save favorite reports
- Dark mode UI

## Quickstart
1. Python 3.9+ recommended.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY=your_key
   ```
4. Run the app:
   ```bash
   streamlit run src/app.py
   ```

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
- Only SELECT/CTE queries are allowed. Every query (raw, NL→SQL, or saved
  report) is validated by a single central safety layer (`src/core/sql_safety.py`):
  it parses the SQL with sqlglot, requires a read-only SELECT/CTE root, rejects
  stacked statements, DML/DDL/PL-SQL, and `FOR UPDATE`, and applies a keyword
  denylist as a backstop. The layer is fail-closed.
- Configurable runtime limits: `MAX_ROWS`, `MAX_EXECUTION_SECONDS`,
  `MAX_RESULT_BYTES` (see `.env.example`).
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

Endpoints:
- GET /health
- POST /test-connection
  - body: ConnectionConfig (inline, not persisted)
- Connection profiles (passwords encrypted at rest; never returned):
  - POST /profiles — create; body: { name, host, port?, service_name?, sid?, username, password, environment? }
  - GET /profiles — list (ProfilePublic, no password)
  - GET /profiles/{id} — fetch one
  - DELETE /profiles/{id} — remove
  - POST /profiles/{id}/test — open SELECT 1 FROM DUAL using stored credentials
- POST /nl2sql
  - body: { natural_language, schema_csv?, relationships_csv?, model? }
- POST /execute (always routed through the safety layer)
  - body: { sql, profile_id? , connection?: ConnectionConfig, max_rows? }
  - provide exactly one of profile_id or connection
  - returns: { columns, rows, elapsed_seconds, row_count, truncated }

Run the API with Docker compose (already included) or locally with:
```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```
