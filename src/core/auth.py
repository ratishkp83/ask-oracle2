"""Opt-in API-key authentication for the HTTP API (ADR-013, closes ITM-009).

Enforcement is keyed entirely off the environment: when ``APP_API_KEY`` is
unset or empty the dependency is a no-op and the API keeps its historical
open, single-user posture. When set, every endpoint except ``/health``
requires the key in the ``X-API-Key`` request header. ``/health`` stays open
because container/orchestrator liveness probes generally cannot attach
headers; ``/metrics`` is deliberately gated (charter D-B).

The Streamlit UI is unaffected — it imports core modules directly and never
calls the HTTP API.
"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

API_KEY_ENV = "APP_API_KEY"
API_KEY_HEADER = "X-API-Key"

# Liveness probes can't send headers on most platforms; everything else is gated.
# Both health paths (root and the /v1 mount) are probe endpoints.
EXEMPT_PATHS = frozenset({"/health", "/v1/health"})


def require_api_key(request: Request) -> None:
    """App-level FastAPI dependency: enforce the API key when one is configured.

    Reads the env var per request so tests (and key rotation) need no module
    reload. Comparison is constant-time. The 401 goes through the standard
    exception handlers, so the body carries ``error_id`` and the response
    echoes ``X-Request-ID`` like every other error. The key value itself is
    never logged.
    """
    expected = os.environ.get(API_KEY_ENV) or ""
    if not expected:
        return
    path = request.url.path
    if path in EXEMPT_PATHS:
        return
    # When the bundled SPA is served at root (SERVE_SPA), the API lives under /v1
    # ONLY — so the static app shell + assets (every non-/v1 path) stay public and
    # the app can load; the SPA itself sends the key on its /v1 calls.
    if (
        os.getenv("SERVE_SPA", "").lower() in ("1", "true", "yes")
        and path != "/v1"
        and not path.startswith("/v1/")
    ):
        return
    provided = request.headers.get(API_KEY_HEADER) or ""
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Not authenticated.")
