# Observability & Error Handling — Design + Build Sequence (Phase 6)

> **Document:** Phase-6 Design · **Version:** 1.1 · **Status:** ✅ Baseline (owner-approved 2026-06-10) — in Build · **Owner:** Product/Engineering · **Last updated:** 2026-06-10
> **Charter:** [charters/phase-6-charter.md](charters/phase-6-charter.md) (Discovery complete; decisions D-A…D-G resolved as recommended).

## 1. Purpose & scope recap
Turn the system observable and harden error responses, **additively** and **without
touching the SELECT-only execution/safety path**. Delivers, per the resolved decisions:
structured JSON logging (D-B), per-request correlation/error IDs (D-E), uniform DB-error
sanitization that **closes ITM-015** (D-C/D-D), lightweight in-process metrics (D-A/D-F), and
a CI Python matrix that **closes ITM-016** (D-G).

## 2. Current state (grounding, verified in code)
- **No logging configuration** anywhere; the only emitters are `src/core/audit.py` and two
  lines in `src/core/introspection.py`. Audit logs `logger.info("%s", payload)` → emits
  `str(dict)`, **not valid JSON**. Content policy is already secret-free (SHA-256 SQL
  fingerprint; never raw SQL or credentials).
- **No middleware besides CORS; no request IDs; no metrics.**
- **Two entry points share one chokepoint.** Both the **API** (`src/api.py` → `_run_sql` /
  endpoints) and the **Streamlit UI** (`src/app.py` → `_run_and_display`, others) call
  `OracleClient.run_select` **directly**. The UI does **not** call the HTTP API. ⇒ any
  sanitization/error-ID mechanism must live in a **shared core helper** both paths invoke,
  not only in API middleware.
- **Raw driver `str(exc)` leaks** at four API arms — `_run_sql` ([api.py:362](../src/api.py)),
  `/schemas/introspect` ([api.py:543](../src/api.py)), `/test-connection`
  ([api.py:253](../src/api.py)), `/profiles/{id}/test` ([api.py:232](../src/api.py)) — and
  in the UI `_run_and_display` `st.error(f"Execution error: {e}")`
  ([app.py:579](../src/app.py)). This is **ITM-015**.
- **Test conventions:** `fastapi.testclient.TestClient`; DB never touched —
  `OracleClient.run_select` is monkeypatched; rejection/validation paths return before any DB
  call. New tests follow this pattern (no live Oracle).

## 3. Target architecture (additive layers around the unchanged chokepoint)

```
            ┌──────────────────────── src/api.py (FastAPI) ───────────────────────┐
 request →  │ RequestIdMiddleware → route → _run_sql / endpoint → OracleClient ────┼─┐
            │   • sets request_id contextvar (honour inbound X-Request-ID)         │ │
            │   • echoes X-Request-ID response header                              │ │
            │ exception handlers: HTTPException / ValidationError / Exception      │ │
            │   • inject "error_id" (= request_id) into every error body           │ │
            └─────────────────────────────────────────────────────────────────────┘ │
                                                                                      │  both call
            ┌──────────────────────── src/app.py (Streamlit) ─────────────────────┐  │  the same
 user    →  │ _run_and_display / test paths → OracleClient.run_select ─────────────┼──┤  chokepoint
            │   • on driver error → core.errors sanitizer (own error_id)           │  │  (unchanged)
            └─────────────────────────────────────────────────────────────────────┘  │
                                                                                      ▼
   src/core/logging_config.py   src/core/errors.py        src/core/metrics.py   OracleClient.run_select
   • configure_logging()        • GENERIC_DB_DETAIL       • thread-safe counters  (src/db.py — NOT touched:
   • JsonFormatter (+text)      • log_db_error(...)        • observe_latency()      single cur.execute,
   • reads request_id contextvar• request_id contextvar    • snapshot()            SELECT/CTE gate, binds)
                                  helpers
```

**Invariant guard:** `src/db.py` and `src/core/sql_safety.py` are **not modified**. Phase 6
is instrumentation *around* them. The single `cur.execute`, the SELECT/CTE gate, and bind
handling (ADR-007) are untouched; the full 160-test regression must stay green.

## 4. Component designs

### 4.1 `src/core/logging_config.py` (new)  — D-B
- `configure_logging() -> None`: **idempotent** (guards against duplicate handlers — Streamlit
  re-runs the script top-to-bottom on every interaction). Reads env:
  - `LOG_LEVEL` (default `INFO`).
  - `LOG_FORMAT` ∈ {`json` (default), `text`} — `text` is a human-readable line for local dev.
- Installs a single `StreamHandler` to **stdout** on the `ask_oracle` logger namespace (and
  configures propagation so `ask_oracle.audit`, `ask_oracle.introspection`, etc. inherit it).
- `class JsonFormatter(logging.Formatter)`: emits one JSON object per line:
  `{"ts","level","logger","msg", "request_id"?, ...structured_fields}`. It pulls
  `request_id` from the `request_id` contextvar (§4.2) when set, and merges a reserved
  `record.__dict__["extra_fields"]` dict (the structured-logging convention below).
- **Structured-logging convention:** callers attach structured data via
  `logger.info("event_name", extra={"extra_fields": {...}})`. The formatter promotes those
  keys to top level. No secrets/PII by policy (enforced by what callers pass, same discipline
  as audit today).

### 4.2 `src/core/errors.py` (new) — D-C / D-D / D-E
- `GENERIC_DB_DETAIL = "Database error — see server logs."`
- `request_id: ContextVar[str | None]` + `set_request_id(value)` / `get_request_id()`.
- `new_error_id() -> str` — `uuid4().hex` (used when there is no request scope, e.g. UI).
- `log_db_error(exc, *, context: str, error_id: str, logger) -> None`: emits a single
  **server-side** `logger.error("db_error", extra={"extra_fields": {"error_id", "context",
  "error": str(exc), "error_type": type(exc).__name__}})`. **Never** logs `conn_cfg.password`,
  bind values, or raw SQL.
- **API helper** `db_http_error(exc, *, context, logger) -> HTTPException`: resolves
  `error_id = get_request_id() or new_error_id()`, calls `log_db_error(...)`, returns
  `HTTPException(status_code=400, detail=GENERIC_DB_DETAIL)`. (Status stays **400** — no
  contract change; the handler in §4.3 attaches `error_id` to the body.)
- **UI helper** `sanitize_db_error_for_ui(exc, *, context, logger) -> tuple[str, str]`:
  generates its own `error_id`, logs, returns `(error_id, GENERIC_DB_DETAIL)` for display as
  `"<generic> (ref: <error_id>)"`.
- **Scope (D-D):** only *raw driver/connection* `Exception` arms use these. Intentional
  `ValueError` (validation), `SqlSafetyError`/safety `reason`, and "not found"/"duplicate"
  messages stay **verbatim** — they are safe and user-actionable.

### 4.3 `src/api.py` changes — D-C / D-E
- Call `configure_logging()` at module import (startup).
- **`RequestIdMiddleware`** (`@app.middleware("http")`): `rid = request.headers.get("X-Request-ID")
  or new_error_id()`; `set_request_id(rid)`; call route; set `response.headers["X-Request-ID"] = rid`.
- **Exception handlers** (make `error_id` appear on every error body — success criterion #2):
  - `@app.exception_handler(StarletteHTTPException)` → `JSONResponse(status_code=exc.status_code,
    content={"detail": exc.detail, "error_id": get_request_id()}, headers=exc.headers)`.
    *Additive:* `detail` unchanged for all existing safe errors (404/409/safety-400/…).
  - `@app.exception_handler(RequestValidationError)` → keep the `detail` list, add `error_id`
    (status 422). Additive.
  - `@app.exception_handler(Exception)` (catch-all) → log server-side + `JSONResponse(500,
    {"detail": "Internal server error.", "error_id": get_request_id()})`. Defense-in-depth.
- **Refactor the four DB-error arms** from `raise HTTPException(400, detail=str(exc))` to
  `raise db_http_error(exc, context="<execute|introspect|test-connection|profile-test>",
  logger=...)`. **This closes ITM-015.**
- **Out of scope (D-D):** `/nl2sql`'s `except Exception` stays as-is (LLM/parse domain, already
  guarded by `test_nl2sql_provider_failure_is_clean`; provider failures wrap in clean
  `LLMError`). It still gains `error_id` via the handler.

### 4.4 `src/core/metrics.py` (new) + `GET /metrics` — D-A / D-F
- Module-level **thread-safe** registry (a dict guarded by `threading.Lock`):
  counters `queries_executed`, `queries_rejected` (safety), `queries_errored`; latency
  aggregate `latency_seconds_sum`, `latency_count`, `latency_max` (→ avg derivable).
- API: `increment(name, n=1)`, `observe_latency(seconds)`, `snapshot() -> dict`, `reset()`
  (test-only).
- **Wiring** (next to the existing `audit.*` calls in `_run_sql`): success → `increment(
  "queries_executed")` + `observe_latency(elapsed)`; safety reject → `increment(
  "queries_rejected")`; DB error → `increment("queries_errored")`. (Mirror UI counters where
  cheap; API is the metrics source of truth this phase.)
- `GET /metrics` returns `snapshot()` JSON (counts + latency only — **no data, no secrets**).
- **D-F:** in-memory only; resets on restart (documented limitation). **Note:** `/metrics`
  (like `/health`) is unauthenticated in the current single-user posture — it exposes only
  aggregate counts; **gate it with the CORS/auth hardening at Phase 7 (ITM-009)**.

### 4.5 `src/core/audit.py` change (format only, not content)
- Switch the two `logger.info("%s", payload)` calls to the structured convention:
  `logger.info(payload["event"], extra={"extra_fields": payload})` so records emit as **valid
  JSON** under `JsonFormatter`. **No change to *what* is logged** (still fingerprint-only,
  secret-free). Reconcile any test that asserts the old `%s` string form.

### 4.6 `src/app.py` (UI) change — D-C surfacing
- `_run_and_display` and the other direct-`run_select` `except` blocks: on a driver error,
  call `sanitize_db_error_for_ui(...)` and `st.error(f"{msg} (ref: {error_id})")`. Safety
  rejections (`SqlSafetyError`) keep their explicit reason. Call `configure_logging()` once at
  app startup.

### 4.7 CI matrix — D-G (closes ITM-016)
- `.github/workflows/ci.yml`: `strategy.matrix.python-version: ["3.11", "3.13"]` (fail-fast
  false), parametrize `actions/setup-python`. Proves the pinned set green on both interpreters.

## 5. API contract changes (D5) — all additive
| Surface | Before | After |
|---------|--------|-------|
| Any error body | `{"detail": <str|list>}` | `{"detail": <unchanged>, "error_id": <hex>}` |
| DB/driver-error bodies (4 endpoints) | `detail = str(exc)` (leaks host/DSN/user) | `detail = "Database error — see server logs."` + `error_id`; full detail server-side |
| Every response | — | `X-Request-ID` header (generated or echoed from inbound) |
| New endpoint | — | `GET /metrics` → `{counts…, latency…}` JSON |
Status codes unchanged (DB errors remain **400**). `detail` stays a string/list (no shape
break). No request schema changes.

## 6. Build sequence (each step = one commit; code + its direct docs/tests together)
1. **B1 — Logging core.** `logging_config.py` (+ `JsonFormatter`), audit JSON emission, wire
   `configure_logging()` into `api.py` + `app.py`. Tests: `test_logging_config.py`
   (idempotent handlers; valid-JSON output; `LOG_LEVEL`; audit round-trips JSON, no
   secret/SQL). Doc: D3 (logging) + ADR-012 (draft).
2. **B2 — Errors + request IDs + sanitization (closes ITM-015).** `errors.py`,
   `RequestIdMiddleware`, the three exception handlers, refactor the four DB arms. Tests:
   `test_error_handling.py` (no host/DSN/user in body; full detail in `caplog`; `error_id`
   present; `X-Request-ID` echoed + honoured; safe 404/409/safety-400 keep verbatim detail +
   gain `error_id`; catch-all 500 via `TestClient(raise_server_exceptions=False)`). Docs: D5
   (contract), ADR-012 (finalize), **issue-log ITM-015 → Closed**.
3. **B3 — Metrics.** `metrics.py` + `/metrics`; wire counters/latency into `_run_sql`. Tests:
   `test_metrics.py` (increments on executed/rejected/errored; `/metrics` JSON; no secrets).
   Doc: D3/D5.
4. **B4 — UI surfacing.** `app.py` driver-error blocks → `sanitize_db_error_for_ui` + ref id;
   `configure_logging()` at startup. Test: UI smoke stays green (+ assertion the error path
   shows a ref).
5. **B5 — CI matrix (closes ITM-016).** `ci.yml` 3.11 + 3.13. Doc: issue-log ITM-016 → Closed.
6. **B6 — Doc consolidation + phase close-prep.** D6 (test strategy), D7 (deployment: log/metrics
   ops + `LOG_LEVEL`/`LOG_FORMAT` env), CHANGELOG, traceability, registers, governance index
   (add this design doc + ADR-012), charter → "built; exit-gate review next", tracker
   P6-1…P6-7/P6-G → Completed. Then prepare the **R6.1 review package**.

## 7. Test plan (all offline; no live Oracle)
- **New:** `test_logging_config.py`, `test_error_handling.py`, `test_metrics.py`.
- **Regression:** full existing suite (160) must stay green; reviewer re-runs safety probes
  (`test_sql_safety.py`, `test_execute_endpoint.py`, `test_bind_safety.py`).
- **Leak assertion (the ITM-015 proof):** monkeypatch `run_select` to raise an exception whose
  message embeds `dbhost.internal:1521 user=SCOTT`; assert that string is **absent** from the
  HTTP body **and** the UI message, but **present** in `caplog` (server-side), keyed by the
  `error_id`.
- **Secret-safety assertion:** assert no password / bind value / raw SQL appears in any emitted
  log record (R6-2).

## 8. Risk → mitigation mapping (from charter)
- **R6-1** over-sanitizing → D-D scope: only raw driver arms; safe messages verbatim; full
  detail always server-side under `error_id`.
- **R6-2** secret leakage into logs → server-side error log records `str(exc)`/type only; never
  password/binds/SQL; explicit test.
- **R6-3** chokepoint regression → `db.py`/`sql_safety.py` untouched; full regression + reviewer
  probes.
- **R6-4** contract break → additive only (keep `detail`; add `error_id`); D5 + UI in lockstep;
  contract tests.
- **R6-5** latency → trivial in-process integers under a lock; no hot-path I/O.
- **R6-6** scope creep → in-process metrics only; no vendor/scrape/tracing.
- **R6-7** Streamlit re-run duplicates handlers → idempotent `configure_logging()`; test.

## 9. Rollback / safety
Each step is independently revertable; none alters execution or safety semantics. If any build
step regresses a test, revert that commit — earlier steps remain valid. The exit-gate reviewer
(owner-supplied, reviewer ≠ author) must return PASS before close.

## 10. Notes / minor
- `error_code` category (D-C optional) **not** included — envelope kept minimal (`detail` +
  `error_id`); can be added additively later if needed.
- Distributed tracing limited to honouring a single inbound `X-Request-ID` (no span
  propagation) — by charter scope-out.
- `/metrics` + `/health` auth is a **Phase-7** concern (ITM-009); flagged, not built here.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Proposed design + build sequence (B1…B6) for owner approval; grounded in verified current state; additive contract changes; shared core sanitizer for API + UI. |
| 1.1 | 2026-06-10 | Product/Eng | **Owner approved as-is** → Baseline; Build started. Minor refinement: `request_id` accessors live in `core/logging_config` (not `errors`) to avoid an import cycle (formatter is the central reader). |
