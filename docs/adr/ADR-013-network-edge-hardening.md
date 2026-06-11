# ADR-013 — Network-edge hardening (opt-in API-key auth + explicit env-driven CORS)

- **Status:** Accepted
- **Date:** 2026-06-11
- **Deciders:** Product/Engineering (Phase 6.5 charter D-A/D-B/D-C, owner-approved)
- **Phase:** 6.5 (Pre-Deployment Hardening)

## Context
Since Phase 2 the FastAPI app shipped `CORSMiddleware` with `allow_origins=["*"]` **and**
`allow_credentials=True`, and no endpoint required authentication — including `/health` and
`/metrics`. The Phase-3 reviewer flagged this (**ITM-009 / RISK-12**) as a hard precondition
for any networked or multi-tenant deployment; the Phase-6 reviewer added the unauthenticated
`/metrics` surface. The posture was acceptable only for the single-user-localhost deployment
the product had so far. The Streamlit UI imports core modules directly (it never calls the
HTTP API), so an API-side credential cannot break the UI.

## Decision
1. **Opt-in static API key** (`src/core/auth.py`): an app-level FastAPI dependency
   (`require_api_key`) compares the `X-API-Key` request header against env **`APP_API_KEY`**
   using `hmac.compare_digest`. **Unset/empty env → no-op** — the historical open posture is
   preserved for local single-user use, and enabling auth is a deployment decision, not a code
   change. Failures return the uniform Phase-6 error envelope (`401`, `detail` +
   `error_id`, `X-Request-ID` echoed). Key material is never logged.
2. **`/health` stays exempt; `/metrics` is gated** (charter D-B): liveness probes on common
   platforms cannot attach headers, and `/health` returns a minimal `{"status": "ok"}` with no
   config detail. `/metrics` (counts/latency only, but operational signal) requires the key
   when auth is enabled.
3. **Explicit, env-driven CORS** (charter D-C): origins come from **`ALLOWED_ORIGINS`**
   (comma-separated), default `http://localhost:8501,http://localhost:3000`. A literal `"*"`
   in the list **forfeits credentials** in code (`allow_credentials=False`), so the
   wildcard+credentials combination that triggered the finding is unrepresentable.

## Consequences
- **ITM-009 / RISK-12 closed at the application layer:** a networked deployment sets
  `APP_API_KEY` + `ALLOWED_ORIGINS` and gets an authenticated API with explicit origins; the
  default localhost posture is unchanged and regression-pinned by the pre-existing test suite
  running with the env unset.
- CORS preflight (`OPTIONS`) is answered by `CORSMiddleware` before routing, so preflights
  are never blocked by auth.
- A single shared key is **not identity**: no users, roles, sessions, or rate limiting. That
  remains the envelope until a real multi-tenant requirement appears (Phase 7+).
- The `0.0.0.0` bind remains a deployment choice (Docker needs it inside the container);
  bind/exposure guidance lives in D7, not code.

## Alternatives considered
- **HTTP Basic:** ubiquitous client support, but credentials-per-request semantics and browser
  popup behaviour buy nothing over a header key for non-browser API consumers.
- **OAuth2/JWT:** real identity and expiry, but heavy dependencies + infrastructure for a
  single-tenant tool; deferred until multi-tenancy is real (D-A).
- **Network-level controls only (reverse proxy / firewall):** does not clear ITM-009 — the
  app would still ship insecure-by-default for anyone who exposes it.
- **Keep `*` but drop credentials:** removes the worst combination yet still invites any
  origin; weaker than the reviewer finding asks (D-C).

## Notes
- Enforcement reads `APP_API_KEY` per request — tests monkeypatch the env without app
  reloads, and key rotation needs no restart.
- Documented in D5 (contract: header, 401 envelope, exemptions) and D7 (env vars, bind
  guidance). Closes the code portion of **ITM-009**; tests in `tests/test_auth.py`.
