# ADR-012 — Observability & error handling (structured logs, request/error IDs, sanitized DB errors, in-process metrics)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product/Engineering (charter D-A…D-G, owner-approved)
- **Phase:** 6 (Observability & Error Handling)

## Context
Through Phase 5 the system had **no logging configuration** (the secret-free audit records
went nowhere and were emitted as `str(dict)`, not JSON), **no request correlation**, **no
metrics**, and four DB-touching endpoints echoed raw driver `str(exc)` that can leak
DSN/host/port/username (**ITM-015**). The product has **two entry points that share one
chokepoint** — the FastAPI API (`src/api.py` → `_run_sql`) and the Streamlit UI
(`src/app.py`) — both calling `OracleClient.run_select` directly; the UI does not go through
HTTP. All of this must be addressed **without changing the SELECT-only execution/safety path**
(`src/db.py`, `src/core/sql_safety.py`).

## Decision
Add an **additive observability layer** around the unchanged chokepoint.

1. **Structured logging** (`src/core/logging_config.py`): one idempotent `configure_logging()`
   on the `ask_oracle` logger namespace, **JSON to stdout** (`LOG_FORMAT=text` for local dev),
   level via `LOG_LEVEL` (default `INFO`). The audit module emits its secret-free payload as
   valid JSON via `extra={"extra_fields": …}`. Content policy is unchanged — SHA-256 SQL
   fingerprint only, never raw SQL or credentials.
2. **Request correlation = error reference id** (`request_id` `ContextVar`): the API
   middleware assigns a `uuid4` per request (honouring an inbound `X-Request-ID`), stamps it
   on every log record, echoes it as the `X-Request-ID` response header, and injects it as
   `error_id` into **every** error body.
3. **Uniform DB-error sanitization** (`src/core/errors.py`, **shared by API and UI**): raw
   driver/connection errors return a **generic** client message (`"Database error — see server
   logs."`) plus the `error_id`, with the full detail logged **server-side only** under that
   id. Intentional/safe messages (validation `ValueError`, safety-layer `reason`, "not
   found"/"duplicate") stay **verbatim**. **This closes ITM-015** across all DB-touching
   endpoints and the UI in one consistent rule.
4. **In-process metrics** (`src/core/metrics.py`): thread-safe counters
   (executed/rejected/errored) + latency aggregate, exposed read-only via `GET /metrics`
   (counts only, no data/secrets). **In-memory**; resets on restart.

Error responses keep `detail` (string/list) and **add** `error_id` — additive, no contract
break; status codes unchanged (DB errors remain `400`).

## Consequences
- Production logs are machine-parseable and captured by Docker/Render stdout; the
  already-correct audit trail finally surfaces.
- A user-visible failure carries a reference id that leads support to the exact server log
  line; clients no longer receive DSN/host/username in DB errors.
- Operators get health signal (query throughput / rejection / error counts + latency) with no
  new dependency.
- `request_id` accessors live in `logging_config` (not `errors`) to avoid an import cycle —
  the formatter is the most central reader of the id.

## Alternatives considered
- **Prometheus client + exposition format:** deferred to Phase 7 (networked/multi-instance);
  in-process counters fit the current single-process posture with zero new deps (D-A).
- **Structured `{error:{id,code,message}}` envelope:** rejected this phase — a breaking
  contract change for the UI and API consumers; the additive `detail`+`error_id` shape gives
  the same traceability without the break (D-C).
- **Sanitize all `str(exc)` everywhere:** rejected — would bury safe, actionable validation
  and safety messages with no security gain; only raw driver/connection errors carry leakable
  infrastructure detail (D-D).
- **API-only middleware for error IDs:** insufficient — the UI bypasses HTTP, so the
  sanitizer must be a shared core helper both entry points call.

## Notes
- `/metrics` and `/health` are unauthenticated in the current single-user posture; gate them
  with the CORS/auth hardening at **Phase 7** ([ITM-009](../issue-log.md) / RISK-12).
- Distributed tracing is limited to honouring a single inbound `X-Request-ID` (no span
  propagation) — by charter scope-out.
