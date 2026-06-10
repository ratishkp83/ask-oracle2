# Phase 6 Charter — Observability & Error Handling

> **Document:** Phase Charter · **Version:** 1.4 · **Status:** ✅ CLOSED (exit gate passed) · **Owner:** Product/Engineering · **Last updated:** 2026-06-10

## Lifecycle stage
**CLOSED — 2026-06-10.** Charter approved, decisions D-A…D-G resolved (all as recommended),
design approved, build **B1…B6** complete. **Exit gate PASSED:** independent review
**r1 = PASS-WITH-FIXES** (2 blocking S2 — F-1/F-2, dependency/CI hygiene external to the
Phase-6 code) → remediated → **r2 = PASS** ([r1](../reviews/phase-6-review-r1.md) ·
[r2](../reviews/phase-6-review-r2.md)). ITM-015 closed (uniform DB-error sanitization);
the validated set re-pinned to a **clean-install-proven 3.13-capable** configuration
(F-1/F-2); F-3/F-4/F-5 fixed; F-7→ITM-017 (Phase-7). **185 tests green**; the SELECT-only
chokepoint (`db.py`/`sql_safety.py`) unchanged. Pushed (`d059295..2a88a04`); **CI run #7
green on both 3.11 + 3.13 → ITM-016 CLOSED.** No open residual.

## Context — where we are today (grounding facts)
- **There is no logging configuration anywhere.** No `logging.basicConfig`, no handlers, no
  formatter, no env-driven level. The only emitters are `src/core/audit.py`
  (`ask_oracle.audit`) and two `logger.info` lines in `src/core/introspection.py`. Because
  nothing configures the root logger, those `INFO` records fall below the default `WARNING`
  threshold and **go nowhere** in practice.
- **The audit logger does not emit valid JSON.** `audit_execution` / `audit_profile_usage`
  build a Python `dict` and call `logger.info("%s", payload)` — the output is `str(dict)`
  (single-quoted, `None`/`True` tokens), not machine-parseable JSON. The audit *content
  policy* is already correct and secret-free: it logs a SHA-256 SQL fingerprint, never raw
  SQL, never credentials.
- **No request/correlation IDs, no middleware, no metrics.** The FastAPI app
  (`src/api.py`) has only the (pre-existing, ITM-009) CORS middleware. There is no
  per-request log line, no error reference ID returned to callers, and no counters/timers.
- **Error handling is hand-rolled per endpoint.** Every route raises
  `HTTPException(status_code=…, detail=str(exc))`. Two kinds of `detail` are mixed:
  - **Intentional, safe messages** — validation `ValueError`, duplicate-name `409`, the
    safety layer's rejection `reason`, "Profile not found." These are user-actionable and
    contain no secrets.
  - **Raw driver/connection exceptions** — the `except Exception` arms in `_run_sql`
    ([api.py:362](../../src/api.py)), `/schemas/introspect` ([api.py:543](../../src/api.py)),
    `/test-connection`, and `/profiles/{id}/test` echo `str(exc)`, which can carry
    **DSN/host/port/username** (never the password). This is **ITM-015** (Phase-4 F6 +
    Phase-5 F-2 *400-path*), explicitly deferred here for **uniform** resolution.
- **The UI swallows errors as `st.error(str(e))`** with no reference ID, so a user cannot
  quote anything back to support, and an operator has no server-side breadcrumb to find.
- **Non-negotiables remain in force** (must not regress): SELECT/CTE-only via the single
  chokepoint (`sql_safety.py` → `OracleClient.run_select`; exactly one `cur.execute` in
  `db.py`); AI proposes, never auto-runs; binds are Oracle bind variables (ADR-007);
  secrets via env only; metadata-only persistence. Observability is **additive
  instrumentation around** these paths — it must not alter execution or safety behaviour.

## Objectives
1. **Make the system observable in production** — structured (JSON) application logs with a
   configurable level, emitted to stdout (12-factor; captured by Docker/Render), so the
   already-correct audit records actually surface and are machine-parseable.
2. **Give every request a correlation / error-reference ID** that is logged server-side and
   returned to the caller, so a user-visible failure can be traced to its exact server log
   line.
3. **Resolve ITM-015 uniformly** — sanitize **all** DB/connection driver errors across every
   DB-touching endpoint to a generic client message (+ error-reference ID), logging the full
   detail server-side only. Close the Phase-4/Phase-5 leak strands in one consistent batch.
4. **Add lightweight operational metrics** (counts + latency for query attempts: executed /
   rejected / errored) so an operator has health signal without a vendor stack.
5. Keep everything read-only, secret-free, and governed; code + docs change together.

## Scope — in (subject to Decisions D-A…D-G)
- **Central logging configuration** (`src/core/logging_config.py` or similar): one
  idempotent setup function, called at API and Streamlit startup; **JSON formatter** to
  stdout; level via env (`LOG_LEVEL`, default `INFO`); optional human-readable mode for local
  dev (`LOG_FORMAT=text|json`). Convert the audit payloads to emit as **valid JSON**.
- **Request-correlation middleware** (`src/api.py`): assign a UUID per request (honour an
  inbound `X-Request-ID` if present), bind it to the log context, echo it as an
  `X-Request-ID` response header, and surface it as `error_id` in error bodies.
- **Central exception handling + uniform error envelope:** FastAPI exception handler(s) that
  (a) keep the existing `detail` for intentional/safe errors and **add** `error_id`
  (additive, back-compatible), and (b) for raw driver/connection exceptions return a
  **generic** `detail` ("Database error — see server logs.") + `error_id`, logging the real
  `str(exc)` server-side keyed by that id. A shared sanitizing helper replaces the four
  `except Exception … detail=str(exc)` DB arms. **This closes ITM-015.**
- **In-process metrics** (`src/core/metrics.py`): counters (queries executed / rejected by
  safety / errored) + simple latency aggregation, exposed via a small read-only endpoint
  (e.g. `GET /metrics` JSON), per Decision D-A.
- **UI surfacing:** show the generic message **and** the `error_id` in `st.error(...)` so a
  user can quote the reference.
- **Tests + governed-doc updates in the same change set:** D3 (architecture — logging/metrics/
  error-flow), D5 (API contracts — error envelope, `X-Request-ID`, `/metrics`), D6 (test
  strategy), D7 (deployment — log/metrics ops + env vars), an **ADR** for the observability
  approach, CHANGELOG, traceability, registers, tracker; **close ITM-015** in the issue log.

## Scope — out (explicit non-goals for Phase 6)
- **No external APM / error-tracking vendor** (Sentry, Datadog, New Relic) — Phase 7+.
- **No Prometheus/Grafana/OpenTelemetry stack or scrape infra** unless D-A opts into the
  Prometheus exposition format; default is in-process counters + JSON.
- **No log shipping / aggregation / retention infrastructure** — we emit structured logs to
  stdout; collection is the deployment platform's job (documented in D7, not built here).
- **No alerting / paging / SLO tooling.**
- **No change to the audit content policy** — still secret-free, SQL fingerprint only; we
  change the *format/plumbing*, not *what* is logged.
- **No distributed tracing / span propagation** beyond honouring a single inbound
  `X-Request-ID`.
- **No CORS/auth hardening (ITM-009)** — that stays a Phase-7 precondition; this phase does
  not touch the security posture of the network edge.
- **No persistence of metrics** — in-memory counters reset on restart (acceptable for the
  current single-process posture; noted as a limitation).

## Deliverables
- `src/core/logging_config.py` — central, idempotent logging setup (JSON/text, env-driven).
- Request-ID middleware + central exception handler(s) + shared DB-error sanitizer in
  `src/api.py`.
- `src/core/metrics.py` + a read-only metrics endpoint (shape per D-A).
- Audit logger updated to emit valid JSON (no content change).
- UI: `error_id` surfaced in error displays (`src/app.py`).
- Tests: error-sanitization (assert **no** host/DSN/username in client body, full detail
  **is** logged server-side), `error_id` presence + `X-Request-ID` echo, log-format/JSON
  shape, metrics counters/endpoint, regression that the chokepoint + safety behaviour are
  unchanged.
- Governed docs: this charter (resolved), D3, D5, D6, D7, ADR-012 (observability), CHANGELOG,
  traceability, registers, tracker; **ITM-015 → Closed**.

## Risks
| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R6-1 | Over-sanitizing hides legitimately actionable errors (e.g. `ORA-00942 table does not exist`), degrading self-service | Medium | Sanitize **only** raw driver/connection `Exception` arms; keep safety-layer reasons + validation `ValueError` verbatim (safe + actionable); **always** log full detail server-side under the `error_id` so support can retrieve it |
| R6-2 | New logging accidentally captures secrets/PII (passwords, bind values, raw SQL) | **High** | Server-side error log records `str(exc)` only (driver errors don't echo binds; password never appears in DSN errors); **never** log `conn_cfg.password`, bind dicts, or raw SQL; reuse the audit module's secret-free discipline; add a test asserting no password/bind leakage in emitted logs |
| R6-3 | Refactoring error handling regresses the SELECT-only chokepoint / safety invariants | **High** | No change to `sql_safety.py` or `db.py` execution path; error handling is a wrapper only; full 160-test regression must stay green + new tests; reviewer re-runs safety probes |
| R6-4 | Error-envelope shape change breaks API consumers / the UI | Medium | **Additive** only — keep `detail`, add `error_id`; update D5 + UI in lockstep; contract tests pin both fields |
| R6-5 | Per-request middleware / metrics add latency or contention | Low | Trivial in-process counters + UUID; no I/O on the hot path; metrics are plain integers under a lock or atomic; measured negligible |
| R6-6 | Scope creep (metrics → dashboards → tracing → vendor APM) overloads the phase | Medium | Decisions fix the envelope up front; in-process only, no vendor, no scrape infra; tracing limited to a single inbound header |
| R6-7 | Logging config double-applied (Streamlit re-runs the script each interaction) duplicates handlers / log lines | Low | Idempotent setup (guard on a sentinel / clear existing handlers); test that repeated calls add no duplicate handlers |

## Success criteria (phase exit)
1. Structured **JSON logs** emit to stdout with an env-configurable level; logging is
   configured once at startup; the audit records appear as **valid JSON**.
2. Every API request carries a correlation **`error_id`**, returned in error bodies and
   echoed as an `X-Request-ID` response header, and present on the matching server log line.
3. **ITM-015 closed:** all DB/connection driver errors return a **generic** client `detail` +
   `error_id` with full detail logged server-side — verified across **every** DB-touching
   endpoint; a test asserts no host/DSN/username appears in any client error body.
4. Lightweight **metrics** (executed / rejected / errored counts + latency) are exposed via a
   read-only endpoint (per D-A).
5. The **UI surfaces** the generic message + `error_id`.
6. Full suite green in CI (no regression to the 160 + new tests); governed docs current;
   ADR-012 recorded.
7. **Independent adversarial review + QA returns PASS** ([gate](../process/external-review-gate.md));
   **reviewer agent supplied by the owner**.

## Open decisions (PENDING — owner to resolve; recommendations given)
> Each decision is mine to recommend but the owner's to set, because they fix the phase
> envelope and a contract surface.

- **D-A — Metrics approach.**
  (a) **In-process counters + `GET /metrics` JSON** (zero new deps, fits the single-process
  posture, resets on restart) — **[Recommended]**;
  (b) Prometheus client lib + `/metrics` exposition format (industry standard; adds a dep;
  geared to scraping/multi-instance — more Phase-7);
  (c) Defer metrics entirely; do logging + error IDs only this phase.
  *Recommendation: (a)* — real operator signal now, no dependency, revisit Prometheus when
  Phase 7 makes it networked/multi-instance.

- **D-B — Log format & destination.**
  (a) **JSON to stdout**, level via `LOG_LEVEL`, optional `LOG_FORMAT=text` for local dev
  readability — **[Recommended]**;
  (b) JSON only (no text mode);
  (c) human-readable key=value to stdout.
  *Recommendation: (a)* — 12-factor, captured by Docker/Render, with a dev-friendly escape
  hatch.

- **D-C — Error-envelope shape.**
  (a) **Keep `detail`, add `error_id`** (additive, back-compatible; only DB-error `detail`
  *content* becomes generic) — **[Recommended]**;
  (b) New structured envelope `{error: {id, code, message}}` (cleaner, but a breaking
  contract change for the UI + any API consumer);
  (c) Add `error_id` **and** an `error_code` category alongside `detail`.
  *Recommendation: (a)*, with (c) as a cheap optional add if the owner wants categorised
  errors. Avoid (b) this phase — breaking change for marginal gain.

- **D-D — ITM-015 sanitization breadth.**
  (a) **Sanitize only the raw driver/connection `Exception` arms** (the 4 DB-touching paths);
  leave intentional `ValueError` / safety-`reason` / "not found" messages verbatim —
  **[Recommended]**;
  (b) Sanitize **all** `str(exc)` everywhere (also wraps safe app messages → more opaque,
  worse UX, no security gain).
  *Recommendation: (a)* — closes the actual leak (ITM-015) without degrading actionable
  errors (ties to R6-1).

- **D-E — Correlation-ID handling.**
  (a) **Generate a server-side UUID, honour an inbound `X-Request-ID`, echo it back, reuse it
  as `error_id`** — **[Recommended]**;
  (b) Generate only (ignore inbound headers).
  *Recommendation: (a)* — trivial extra, and future-proofs for a fronting gateway.

- **D-F — Metrics persistence.**
  (a) **In-memory only**, resets on restart (documented limitation) — **[Recommended]**;
  (b) Persist counters to the file store.
  *Recommendation: (a)* — persistence is a Phase-7 concern; avoid file-store churn
  (ITM-013/014 are still open).

- **D-G — Fold in ITM-016 (CI Python matrix) this phase?**
  (a) **Yes — add a 3.11 + 3.13 CI matrix** while we're in the ops/observability area (tiny,
  proves "green == shipped" on both interpreters) — **[Recommended]**;
  (b) No — leave ITM-016 as a standalone backlog item.
  *Recommendation: (a)* — cheap, observability-adjacent, retires a carried item.

## Decisions (resolved 2026-06-10)
Owner approved the charter and resolved **all seven decisions as recommended**.

- **D-A — Metrics approach:** ✅ **In-process counters + `GET /metrics` JSON** (no new deps;
  resets on restart). Prometheus deferred to Phase 7 (networked/multi-instance).
- **D-B — Log format & destination:** ✅ **JSON to stdout**, level via `LOG_LEVEL`
  (default `INFO`), optional `LOG_FORMAT=text` for local-dev readability.
- **D-C — Error-envelope shape:** ✅ **Keep `detail`, add `error_id`** (additive,
  back-compatible). Only the DB-error `detail` *content* becomes generic. No breaking
  restructure. (An optional `error_code` category may be added if cheap — at engineering
  discretion during design, non-breaking.)
- **D-D — ITM-015 sanitization breadth:** ✅ **Sanitize only the raw driver/connection
  `Exception` arms** (the DB-touching paths); intentional `ValueError` / safety-`reason` /
  "not found" messages stay verbatim.
- **D-E — Correlation-ID handling:** ✅ **Generate a server-side UUID, honour an inbound
  `X-Request-ID`, echo it back**, reuse it as `error_id`.
- **D-F — Metrics persistence:** ✅ **In-memory only** (resets on restart; documented
  limitation).
- **D-G — Fold in ITM-016 (CI Python matrix):** ✅ **Yes — add a 3.11 + 3.13 CI matrix**
  this phase (closes ITM-016).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Discovery charter opened; objectives/scope/deliverables/risks/success criteria + open decisions D-A…D-G; **pending owner approval before any code**. |
| 1.1 | 2026-06-10 | Product/Eng | Owner approved; decisions D-A…D-G resolved (all as recommended). Discovery complete → Design (design + build sequence pending owner approval before code). |
| 1.2 | 2026-06-10 | Product/Eng | Design + build sequence approved (Baseline) → Build started; executing B1…B6. |
| 1.3 | 2026-06-10 | Product/Eng | Build B1…B6 complete (182 tests; ITM-015 + ITM-016 CLOSED); review package prepared; exit-gate review (R6.2) pending. |
| 1.4 | 2026-06-10 | Product/Eng | Exit gate PASSED — r1 PASS-WITH-FIXES (F-1/F-2 S2) → re-pinned to a clean-install-proven 3.13-capable set + F-3/F-4/F-5 fixed → r2 PASS; 185 tests; Phase 6 CLOSED. ITM-016 Mitigating (CI demo pending push). |
