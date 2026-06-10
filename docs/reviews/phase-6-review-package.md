# Phase 6 — Review Package (input to the independent gate)

> **Prepared:** 2026-06-10 · For: owner-supplied independent reviewer · Gate: [external-review-gate](../process/external-review-gate.md)
> Hand the **filled Context block** below (plus this package) to the reviewer along with the [Adversarial Review & QA Prompt](../process/adversarial-reviewer-prompt.md). The reviewer (a fresh-context agent, **not** the author) writes findings to `docs/reviews/phase-6-review-r1.md`.

## Change set
- **Code range:** `d059295..fc55a46` — the 9 Phase-6 build commits (`6b0671c → fc55a46`).
  *(Note: `d059295..HEAD` resolves through the R6.1 package-prep commit `8758d82` → 10 commits;
  a literal `git diff d059295..HEAD` is +1 doc commit over the code range — see review r1 F-6.)*
- **Diff:** `git diff d059295..fc55a46` (25 files, +1472/−55).
- **Primary new code:**
  - `src/core/logging_config.py` — idempotent structured logging (JSON/text), `request_id` `ContextVar` + accessors, `JsonFormatter`/`TextFormatter`.
  - `src/core/errors.py` — framework-agnostic DB-error sanitization shared by API + UI (`log_error`, `sanitize_db_error_for_ui`, `GENERIC_*`).
  - `src/core/metrics.py` — thread-safe in-process counters + latency; `snapshot()`.
  - `src/api.py` — `request_id_middleware`; exception handlers (HTTPException / RequestValidationError / catch-all `Exception`); `_db_error` helper; the four DB-error arms refactored; metrics wired into `_run_sql`; `GET /metrics`.
  - `src/app.py` — three UI driver-error surfaces routed through the shared sanitizer; `configure_logging()` at startup.
  - `src/core/audit.py` — emits valid JSON via `extra_fields` (content unchanged).
  - `.github/workflows/ci.yml` — Python 3.11 + 3.13 matrix.
- **Commits:** `6b0671c` charter · `76f2d3c` decisions · `0b61061` design · `c490910` B1 (logging) · `ada0354` B2 (errors+middleware, **ITM-015**) · `1e65ae8` B3 (metrics) · `9a9c27e` B4 (UI) · `ee125d6` B5 (CI matrix, **ITM-016**) · `fc55a46` B6 (docs).

## Filled Context block (paste into the adversarial prompt)
- **Phase under review:** Phase 6 — Observability & Error Handling.
- **Charter:** [charters/phase-6-charter.md](../charters/phase-6-charter.md) · **Design:** [observability-error-handling-design.md](../observability-error-handling-design.md) · **ADR:** [ADR-012](../adr/ADR-012-observability-and-error-handling.md).
- **Change set:** `d059295..HEAD`.
- **Phase-specific invariants to attack (in addition to the standing list in the prompt):**
  1. **No new execution path — the chokepoint is untouched.** Confirm there is still exactly
     **one** `oracledb.connect` (`db.py:113`) and **one** `cur.execute` (`db.py:141`), and that
     `sql_safety.py`/`db.py` are unchanged in this range (`git diff d059295..HEAD -- src/db.py
     src/core/sql_safety.py` should be empty). Observability must be instrumentation *around*
     the chokepoint only.
  2. **DB-error sanitization is complete and leak-free (ITM-015).** Across **every**
     DB-touching path — `/execute`, `/reports/{id}/run`, `/schemas/introspect`,
     `/test-connection`, `/profiles/{id}/test`, **and** the UI (`_try_connect`, introspection,
     `_run_and_display`) — a raw driver/connection error must return only
     `"Database error — see server logs."` + an `error_id`. **Attack:** make `run_select` raise
     exceptions whose text embeds host/DSN/username/password/ORA-codes; confirm **none** appears
     in the client body **or** response headers, but the full text **does** appear in the
     server-side log keyed by the **same** `error_id`. Grep the diff for any surviving DB-arm
     `detail=str(exc)`.
  3. **Safe messages are NOT over-sanitized.** Validation `ValueError`, the safety layer's
     rejection `reason`, and "not found"/"duplicate" must stay **verbatim** (they are
     user-actionable, secret-free). Confirm a DML rejection still returns the real reason, not
     the generic DB message; confirm `/schemas/introspect` blank-owner still returns its `400`
     message.
  4. **Logs are secret-free.** No password, bind value, or raw SQL in any emitted record — audit
     logs a SHA-256 fingerprint only; the error log records `str(exc)` + type only. **Attack:**
     run a query / supply a bind containing a secret-looking literal and confirm it is absent
     from emitted log lines. Check that `conn_cfg.password` is never logged.
  5. **Correlation-id integrity + header-injection.** `error_id` must equal the request's
     `X-Request-ID`; an inbound `X-Request-ID` is honoured, otherwise one is generated; the id
     is present on **every** error body (incl. validation `422` and the catch-all `500`).
     **Attack:** send a malicious inbound `X-Request-ID` (CRLF, very long, control chars,
     HTML/JS) and check it cannot inject a response header or otherwise misbehave when reflected
     into the header/body. (Starlette is expected to reject invalid header bytes — verify.)
  6. **`/metrics` exposes counts only.** No data/SQL/secrets; in-memory; thread-safe under
     concurrency. Confirm counters (`queries_executed`/`rejected`/`errored`) move correctly and
     that nothing sensitive can surface in the snapshot.
  7. **Logging is idempotent.** `configure_logging()` is called at both API and UI startup and
     Streamlit re-runs the script each interaction — confirm repeated calls add **no** duplicate
     handlers (no doubled/multiplying log lines) and refresh level/format in place.
  8. **The error envelope is additive (no contract break).** `detail` is unchanged for all
     existing errors; `error_id` is a new sibling key; status codes are unchanged (DB errors
     stay `400`). Confirm `/openapi.json` still builds and no existing consumer field was
     removed or retyped.
  9. **No regression** to the standing invariants — SELECT/CTE-only, AI-proposes-never-runs,
     binds-as-values (ADR-007), secrets-via-env, metadata-only persistence — none weakened by
     the new middleware/handlers.

## Test status
- `pytest -q` → **182 passed** locally (mocked DB throughout — no live Oracle/LLM calls).
- New suites: `test_logging_config.py` (7), `test_error_handling.py` (10), `test_metrics.py` (5) — **+22** over Phase 5's 160.
- The **ITM-015 leak proof** lives in `test_error_handling.py::test_db_error_is_sanitized_but_logged_server_side` (+ `test_other_db_endpoints_are_also_sanitized`, `test_ui_sanitizer_returns_ref_and_logs_full_detail`).
- Run: `pip install -r requirements-dev.txt` then `APP_SECRET_KEY=… PYTHONPATH=. pytest -q`. CI now runs this on **Python 3.11 + 3.13**.

## Known limitations / not covered (verify or flag)
- **No live Oracle.** Sanitization is exercised with synthetic driver exceptions; the mechanism
  is error-agnostic (it catches `Exception` and never echoes `str(exc)`), but real `ORA-`
  payloads, headers, and `truncated`/latency under real volume are not auto-tested (pre-GA
  RISK-04). The reviewer should reason about whether any real driver-error surface escapes the
  catch.
- **Catch-all 500 + contextvar.** `error_id` in the catch-all `Exception` handler relies on the
  `request_id` contextvar set by `request_id_middleware` propagating to the outer
  `ServerErrorMiddleware` scope (Starlette `BaseHTTPMiddleware` context semantics). It is
  covered by `test_unhandled_error_returns_generic_500`, but is worth an independent check; note
  the unhandled-500 response may **not** carry the `X-Request-ID` *header* (it still carries
  `error_id` in the body) — confirm that's acceptable.
- **`/metrics` + `/health` are unauthenticated** (counts only, no data) — a Phase-7 auth item
  ([ITM-009](../issue-log.md) / [RISK-12](../risk-register.md)), flagged not built.
- **Metrics are in-memory** (reset on restart; single-process) — by decision D-F.
- **UI** verified via headless `AppTest` only (no browser/visual pass).

## Expected reviewer output
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + exact `file:line` + repro), blocking list (default: open S1/S2), QA results, could-not-verify — saved to `docs/reviews/phase-6-review-r1.md`.
