# Ask Oracle Reports — Phase 2 Review Guide

**Phase 2 — Hardened Connectivity & Safety.** This document is the hand-off pack
for external code review and QA of the connectivity and SQL-safety work. It
summarises what changed, gives a focused review prompt, a QA prompt with
concrete test cases, and a security checklist.

---

## 1. What changed

### New `src/core/` package (single source of truth)
| Module | Responsibility |
|---|---|
| `core/config.py` | `SafetyLimits` (max_rows / max_execution_seconds / max_result_bytes) + `load_safety_limits()` from env. |
| `core/sql_safety.py` | `assert_safe_select()` → `SafetyResult`; `is_safe_select()`; `SqlSafetyError`. Layered parser + denylist policy. |
| `core/crypto.py` | Fernet encrypt/decrypt of secrets at rest; key derived from `APP_SECRET_KEY`. |
| `core/profiles.py` | `ConnectionProfile` models, `ProfileStore` ABC, `JsonFileProfileStore`, `InMemoryProfileStore`. Passwords encrypted; `ProfilePublic` never exposes them. |
| `core/audit.py` | Secret-free audit logging (SQL SHA-256 fingerprint, never raw SQL or credentials). |

### Modified
- `src/db.py` — `OracleClient.run_select()` returns a `QueryResult` and enforces all three limits (row cap, `call_timeout`, result-size cap with a `truncated` flag). Routes through `core.sql_safety`. `execute_query()` kept as a backwards-compatible 3-tuple wrapper for the Streamlit app.
- `src/nl2sql.py` — removed its duplicate `sql_is_safe_select`; now imports the central one. Added `LLMConfig` + `resolve_model()`/`_client_from_config()` so the provider/model/API key are **customizable per user/request**, with the server env config as fallback. Keys are used transiently, never logged or persisted.
- `src/api.py` — consolidated onto the wired version; **removed the hardcoded API key**; added `load_dotenv()`; added `/profiles` CRUD + `/profiles/{id}/test`; `/execute` now accepts `profile_id` **or** inline `connection`, is the single safety chokepoint, and audits every attempt. `/nl2sql` accepts an optional `llm` override (`LLMSettings`).
- `src/app.py` (Streamlit) — added a **Connections** screen (add/list/test/delete profiles via the encrypted `ProfileStore`), a profile-aware "Active Connection" sidebar selector, and a **Settings** screen for per-session LLM provider/model/key. Query results now surface the `truncated` flag.
- `docker-compose.yml` — **removed the inline OpenAI key**; reads secrets from a git-ignored `.env` via `env_file`; points at an existing Dockerfile.
- `.gitignore` — now ignores `.env`, `__pycache__/`, `.venv/`, `storage/`.
- `.env.example` — documents `APP_SECRET_KEY` and the safety-limit env vars.
- `requirements.txt` — adds `sqlglot` and `cryptography`. New `requirements-dev.txt` for `pytest`/`httpx`.

### Safety policy (layered, fail-closed)
1. Parse with sqlglot (Oracle dialect); reject parse failures and stacked statements.
2. Root must be SELECT / UNION / INTERSECT / MINUS (CTE allowed; parenthesised SELECT allowed).
3. Reject any DML/DDL/PL-SQL node anywhere in the AST, and any row-locking (`FOR UPDATE`).
4. Keyword denylist backstop over normalised, comment- and literal-stripped SQL.

---

## 2. Code review prompt (connectivity & safety)

> You are reviewing **Phase 2 (Hardened Connectivity & Safety)** of *Ask Oracle
> Reports*, a commercial read-only reporting layer for Oracle DB / EBS. The
> product guarantee is **SELECT-only execution**: all DML/DDL/PL-SQL must be
> rejected, AI proposes SQL but never auto-runs it, and credentials are treated
> as secrets. Review with a production, safety-first mindset.
>
> Focus areas:
> 1. **SQL safety (`src/core/sql_safety.py`)** — Can any non-SELECT reach the
>    database? Probe for bypasses: stacked statements, comment tricks
>    (`/* */`, `--`), `WITH` wrapping DML, `FOR UPDATE`, PL/SQL blocks,
>    DML inside subqueries, hints, and dialect quirks sqlglot might mis-parse.
>    Is fail-closed behaviour correct, and are false-rejections of valid Oracle
>    SELECTs acceptable/documented?
> 2. **Single chokepoint** — Confirm *every* execution path (API `/execute`,
>    Streamlit `execute_query`, NL→SQL) routes through the one safety layer, with
>    no second, weaker copy of the check.
> 3. **Credential handling (`crypto.py`, `profiles.py`, `api.py`)** — Is the
>    password ever logged, returned by the API, or written in cleartext? Is the
>    Fernet key derivation sound? What happens if `APP_SECRET_KEY` is missing or
>    rotated? Is `ProfilePublic` guaranteed password-free?
> 4. **Limits (`config.py`, `db.py`)** — Are `max_rows`, `max_execution_seconds`
>    (`call_timeout`), and `max_result_bytes` actually enforced and not bypassable
>    via `max_rows` overrides? Is `truncated` reported honestly?
> 5. **Audit (`audit.py`)** — Confirm no raw SQL or secrets are logged; only
>    hashes/metadata. Is the audit emitted on both success and rejection?
> 6. **Error handling** — Are DB/connection errors surfaced as clean 4xx without
>    leaking DSNs, credentials, or stack traces?
>
> Deliver: concrete bypasses (with the exact SQL that defeats the layer, if any),
> security issues ranked by severity, and any place a second source of truth has
> crept back in.

---

## 3. QA prompt + concrete test cases

> QA the connectivity and safety behaviour of *Ask Oracle Reports* Phase 2. Use
> the API (`/docs`) and the Streamlit UI. Verify safe queries succeed and unsafe
> queries are rejected with a clear message, and that connection failures are
> handled gracefully.

### 3.1 SQL safety — must be ACCEPTED (return rows / 200)
- `SELECT 1 FROM DUAL`
- `SELECT employee_id, salary FROM employees WHERE ROWNUM <= 50`
- `WITH q AS (SELECT id FROM emp) SELECT * FROM q`
- `SELECT a FROM t1 UNION SELECT a FROM t2`
- `SELECT * FROM (SELECT id FROM emp) x`
- `SELECT id FROM emp WHERE status = 'DELETE'`  *(DML word only inside a string)*
- `SELECT update_date FROM emp`  *(column name contains a keyword)*
- A `SELECT` formatted with a newline immediately after `SELECT`.

### 3.2 SQL safety — must be REJECTED (HTTP 400, clear reason; no DB hit)
- `INSERT INTO emp (id) VALUES (1)`
- `UPDATE emp SET salary = 0`
- `DELETE FROM emp`
- `MERGE INTO emp ...`
- `TRUNCATE TABLE emp`
- `DROP TABLE emp` / `ALTER TABLE emp ...` / `CREATE TABLE x (...)`
- `GRANT SELECT ON emp TO bob`
- `BEGIN NULL; END;` *(PL/SQL block)*
- `SELECT * FROM emp; DROP TABLE emp` *(stacked statements)*
- `SELECT * FROM emp FOR UPDATE` *(row locking)*
- Empty / whitespace-only input.

### 3.3 Limits
- A query returning more than `MAX_ROWS` rows → response capped, `truncated: true`.
- A deliberately slow query → fails near `MAX_EXECUTION_SECONDS` with a clean error.
- `max_rows` in the request larger than the global cap → still capped at the global cap.

### 3.4 Connectivity & error handling
- Wrong password → `400` with a helpful message, **no credentials echoed**.
- Unreachable host / wrong port → graceful timeout/error, no stack trace leak.
- Missing both `service_name` and `sid` → validation error.
- `/execute` with neither `profile_id` nor `connection` → `422`.
- `/execute` with an unknown `profile_id` → `404`.

### 3.5 Profiles & secrets
- Create a profile, then `GET /profiles` and `GET /profiles/{id}` → **password never appears** in any response.
- Inspect `storage/profiles.json` → password is ciphertext, not cleartext.
- Duplicate profile name → `409`.
- `POST /profiles/{id}/test` with valid creds → `{ ok: true }`; with bad creds → `400`.

---

## 4. Automated tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

- `tests/test_sql_safety.py` — accept/reject matrix for the safety layer (incl. literal/identifier false-positive guards, stacked statements, FOR UPDATE, PL/SQL).
- `tests/test_profiles.py` — encryption-at-rest, decrypt round-trip, no password leakage, duplicate-name and service/sid validation.
- `tests/test_execute_endpoint.py` — `/execute` rejects unsafe SQL, requires a target, 404 on unknown profile, success path (Oracle driver monkeypatched); `/profiles` CRUD with password never returned.
- `tests/test_nl2sql_config.py` — per-user LLM resolution: explicit model wins, provider defaults, Groq base-url wiring, env fallback (no network calls).

> Status at hand-off: the full suite (**51 tests**) passes locally, including
> headless `AppTest` UI smoke (`test_app_smoke.py`) that executes every screen.
> The UI smoke caught and verified the fix for BUG-005 (duplicate widget ID). A
> manual pass against a real Oracle sandbox (connection success, live NL→SQL,
> browser visuals) is still recommended before external GA.

---

## 5. Security checklist — committed secrets (action required)

Phase 2 removed inline secrets from source and `docker-compose.yml` and added
`.env` to `.gitignore`. **This does not un-leak keys that were previously
committed.** Treat the following as compromised and rotate:

- [ ] **Rotate the Groq API key** (was in `.env` / compose) in the Groq console.
- [ ] **Rotate the OpenAI API key** (was in `docker-compose.yml` / `src/api.py`) in the OpenAI dashboard.
- [ ] Set the new keys as environment variables only (local `.env`, Render dashboard) — never in source.
- [ ] Generate and set `APP_SECRET_KEY` (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
- [ ] (Optional but recommended) Purge the old keys from git history (`git filter-repo` / BFG) and force-push, or rotate-only if history scrubbing is impractical.
- [ ] Confirm `git status` shows `.env` as ignored before the next commit.

---

## 6. Suggested updates to `ask-oracle-techspec.md`

Concrete edits to reflect Phase 2 decisions (small, additive):

1. **§3.1 Connectivity** — replace "Connection profiles: Saved, named profiles
   with optional environment tags" with the concrete model: `id, name, host,
   port, service_name|sid, username, password (encrypted at rest via Fernet /
   APP_SECRET_KEY), environment ∈ {DEV,TEST,PROD}`. State that passwords are
   never returned by the API (`ProfilePublic`).
2. **§3.2 Governance & safety** — replace the prefix-check description with the
   layered policy: sqlglot parse (Oracle dialect) → SELECT/CTE root → no
   DML/DDL/PL-SQL nodes → no `FOR UPDATE` → keyword denylist backstop;
   **fail-closed**. Add the explicit forbidden set and note stacked statements
   are rejected.
3. **§3.2 / §4.3** — document the three configurable limits and their env vars:
   `MAX_ROWS` (1000), `MAX_EXECUTION_SECONDS` (30), `MAX_RESULT_BYTES` (5 MB),
   and the `truncated` response flag.
4. **§4.2 Security** — state that **no secrets live in source or compose**; all
   come from env (`.env` locally, dashboard on Render); `APP_SECRET_KEY` is
   required for profile storage. Audit logs contain a SQL SHA-256 fingerprint
   only — never raw SQL or credentials.
5. **§5.1 Architecture** — add the `src/core/` package (config, sql_safety,
   crypto, profiles, audit) and note `/execute` is the single execution
   chokepoint shared by API and UI; rename the app from "Smart Report Builder"
   to "Ask Oracle Reports" for consistency.
