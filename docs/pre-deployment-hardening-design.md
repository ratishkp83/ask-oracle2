# Pre-Deployment Hardening — Design + Build Sequence (Phase 6.5)

> **Document:** Design · **Version:** 1.1 · **Status:** Baseline (owner-approved 2026-06-11) · **Owner:** Engineering · **Last updated:** 2026-06-11
> Charter: [charters/phase-6.5-charter.md](charters/phase-6.5-charter.md) (decisions D-A…D-F resolved 2026-06-11, all as recommended).

## 1. Purpose & scope recap
Close the four carried code preconditions gating any networked/multi-tenant deployment —
**ITM-009** (CORS/auth, RISK-12), **ITM-010** (`base_url` numeric-IP encodings), **ITM-013/014**
(file-store atomicity + corrupt-record robustness, RISK-16), **ITM-017** (non-DB `str(exc)`
surfaces) — additively, around the unchanged SELECT-only chokepoint. No change to
`sql_safety.py` / `db.py` execution paths; no new dependencies.

## 2. Current state (grounding, verified in code at `13e7928`)
- `src/api.py:65-71` — `CORSMiddleware` with `allow_origins=["*"]` + `allow_credentials=True`;
  no endpoint requires auth. `/health` (`:254`) already returns a minimal `{"status": "ok"}`;
  `/metrics` (`:259`) is open with a docstring deferring gating to ITM-009.
- Phase 6 already provides: `request_id_middleware` (`api.py:77`) binding a sanitized
  correlation id; exception handlers that inject `error_id` into **every** error body;
  `core/errors.py` (`log_error`, `sanitize_db_error_for_ui`); `core/metrics.py`.
  Phase 6.5 builds on these — no parallel machinery.
- `validate_base_url` (`src/core/llm/providers.py:20`) — blocks IP literals via
  `ipaddress.ip_address(host)`; integer/hex/octal encodings (e.g. `2130706433`, `0x7f000001`,
  `017700000001`) take the `ValueError` arm and pass as "hostnames".
- Four stores truncate-and-rewrite in place: `storage.py:34`, `core/profiles.py:136`,
  `core/reports.py:233` (`_save_locked`), `core/schema_store.py:130`.
- `core/reports.py:194` `_deserialize` — a v2-shaped record (`id`+`name` present) goes straight
  to `Report(**rec)`; a malformed one raises uncaught `ValidationError` → 500 on `list`/`get`.
  The legacy arm migrates anything else.
- ITM-017 surfaces: `api.py:280` (`SecretConfigError` → 500 `str(exc)`); `api.py:376-377`
  (`/nl2sql` catch-all → 400 `str(exc)`, mixing intentional `LLMError` text with raw
  pandas/network/provider exceptions); UI `SecretConfigError` arms (`app.py:196/247/285/716`).
  `SecretConfigError` messages are app-generated constants (`crypto.py`) — safe, actionable.
- The Streamlit UI imports core directly; it never calls the HTTP API.

## 3. Target design (additive layers; chokepoint untouched)
```
client ──► CORSMiddleware (explicit env-driven origins)          [B1]
       ──► request_id_middleware (Phase 6, unchanged)
       ──► require_api_key dependency (app-level; /health exempt) [B1]
       ──► routes ──► …chokepoint unchanged…
stores ──► atomic_write_json (temp + fsync + os.replace)          [B3]
       ──► corrupt-v2 records: skip-and-log, preserved on save    [B4]
errors ──► ITM-017 arms classified per D-F via core/errors        [B5]
llm    ──► validate_base_url: numeric-host normalization first    [B2]
```

## 4. Component designs

### 4.1 `src/core/auth.py` (new) — D-A / D-B
- `require_api_key(request: Request) -> None` — FastAPI dependency, registered app-wide via
  `FastAPI(dependencies=[Depends(require_api_key)])`.
- Reads `APP_API_KEY` from env **per request** (cheap; testable via monkeypatch; no import-order
  trap). **Unset/empty → no-op** (opt-in, default-off preserves the current single-user posture).
- Exempt paths: `{"/health"}` only (path checked against `request.url.path`). `/metrics` is
  deliberately *not* exempt (D-B). CORS preflight `OPTIONS` is handled by `CORSMiddleware`
  before routing, so preflights are never blocked.
- When set: compare `X-API-Key` header via `hmac.compare_digest`; missing/wrong →
  `HTTPException(401, detail="Not authenticated.")`. The Phase-6 handlers already inject
  `error_id` and the middleware echoes `X-Request-ID` — the 401 envelope is uniform for free.
  No key material is ever logged (only "auth failed" + `error_id`).

### 4.2 CORS configuration (`src/api.py`) — D-C
- `ALLOWED_ORIGINS` env: comma-separated explicit origins; whitespace-tolerant parse; default
  `http://localhost:8501,http://localhost:3000`.
- Invariant enforced in code: if the parsed list contains `"*"`, credentials are force-disabled
  (`allow_credentials=False`); explicit origins get `allow_credentials=True`. The `*`+credentials
  combination becomes unrepresentable.
- D7 documents both env vars + the 0.0.0.0-inside-container guidance (the `api.py:664` run
  comment is updated to point at D7).

### 4.3 `validate_base_url` hardening (`src/core/llm/providers.py`) — ITM-010
- New helper `_numeric_host_to_ipv4(host: str) -> Optional[str]`, pure Python (no reliance on
  platform `inet_aton` quirks): split on `.` (1–4 components); each component must parse as
  decimal / `0x…` hex / `0…` octal (C `inet_aton` rules); combine per `inet_aton` semantics
  (last component fills the remaining bytes). Returns the canonical dotted-quad, or `None` if
  any component is non-numeric (a real hostname).
- Flow: after the existing `_BLOCKED_HOSTS` check, run the helper **before**
  `ipaddress.ip_address`. If it yields an IP → run the existing private/loopback/link-local/
  reserved/multicast checks against it. **Fail-closed:** a host whose components are all numeric
  but which does not form a valid IPv4 (e.g. `4294967296`, `1.2.3.4.5`) is rejected — an
  all-numeric host is never a legitimate public hostname.
- IPv6 literals already reach `ipaddress.ip_address` via `urlparse().hostname` (brackets
  stripped) — unchanged. DNS-rebinding stays the documented residual (charter scope-out).

### 4.4 `src/core/fileio.py` (new) — D-D / ITM-013
- `atomic_write_json(path, payload, *, indent=2, default=None) -> None`:
  `os.makedirs(parent, exist_ok=True)` → `tempfile.mkstemp(dir=parent, prefix=".<name>.", suffix=".tmp")`
  → `json.dump` → `flush` + `os.fsync` → close → `os.replace(tmp, path)`; `try/finally` unlinks
  the temp file on failure. Same-directory temp guarantees same-volume `os.replace` atomicity on
  both Windows and POSIX.
- Adopted by all four stores (`storage.py`, `core/profiles.py`, `core/reports.py`,
  `core/schema_store.py`) — each replaces its `open(..., "w") + json.dump` body; JSON shape,
  indent, and `default=` behaviour byte-identical; store public APIs and locks unchanged.
- Multi-**worker** concurrency remains a documented single-worker-per-store-directory
  constraint (D7) — per D-D, SQLite is deferred until a multi-worker deployment is planned.

### 4.5 Corrupt-record robustness (`src/core/reports.py`) — D-E / ITM-014
- `_deserialize` distinguishes three shapes per record:
  1. **v2** (`dict` with `id`+`name`): `Report(**rec)` wrapped in `try/except ValidationError` —
     on failure the record is **quarantined**, not migrated, not served.
  2. **legacy** (anything else): migrated as today, also wrapped — unparseable legacy records
     quarantine rather than raise.
  3. **quarantined**: counted + logged once per load via `core.errors.log_error`
     (context `report_store.corrupt_record`, keyed by `error_id`; logs the record *key* and
     exception type — never the record body, which could embed SQL).
- **No silent data loss:** `_deserialize` returns the quarantined raw records alongside the good
  ones, and `_save_locked` writes them back **verbatim under their original keys**. A corrupt
  record survives create/update/delete cycles on other records until an operator repairs it;
  `list`/`get` simply don't serve it. The in-place migration save in `_load_locked` also
  preserves quarantined records.
- `delete`/`update` against a quarantined id → 404 (it is not served); documented in D5.
- Profile and schema stores: verified for the same failure mode in B4 — `profiles.py` and
  `schema_store.py` deserialization get the same skip-and-quarantine treatment **only if** a
  malformed-record test shows the same uncaught-raise behaviour; otherwise a covering test is
  added and no code changes (kept minimal; findings recorded in the build notes).

### 4.6 ITM-017 surfaces — D-F
- `api.py:280` (`SecretConfigError` → 500): message stays **verbatim** (app-generated constant);
  add a `core.errors.log_error` call (context `profiles.secret_config`) so the 500 has a
  server-side breadcrumb. `error_id` is already injected by the Phase-6 handlers.
- `api.py:352-377` (`/nl2sql`): the broad `except Exception → 400 str(exc)` is split:
  - `except LLMError` → 400, **verbatim** (our own validation text, e.g. base_url rejections);
  - `except Exception` → `log_error(context="nl2sql")` → 400 with **generic** detail
    ("Could not generate SQL — see server logs (ref: <error_id>)" wording finalized in build) —
    raw pandas/network/provider text never reaches the client. (UX tradeoff accepted at D-F: a
    malformed-CSV message goes generic; the operator retrieves detail by `error_id`.)
- UI (`app.py:196/247/285/716`): `SecretConfigError` text stays verbatim; each arm adds a
  logged reference — `log_error(...)` + `st.error(f"{e} (ref: {error_id})")` — mirroring the
  Phase-6 UI pattern. No new sanitization machinery; reuse `core/errors`.

## 5. Contract & ops changes (D5 / D7) — all additive / opt-in
- **New request header (opt-in):** `X-API-Key` — required on every endpoint except `/health`
  when `APP_API_KEY` is set; 401 (uniform envelope: `detail` + `error_id`) otherwise. Unset →
  no behaviour change.
- **New env vars (D7):** `APP_API_KEY` (enables auth), `ALLOWED_ORIGINS` (default
  `http://localhost:8501,http://localhost:3000`).
- `/metrics`: response shape unchanged; now auth-gated when auth is enabled.
- `/nl2sql` 400 `detail`: generic for unexpected failures (was raw text); `LLMError` text
  unchanged. `/reports`,`/schemas` `list`/`get`: corrupt records absent instead of 500.
- No breaking change for the default (env-unset) posture; CI/tests run with env unset except
  where the auth/CORS tests set it explicitly.

## 6. Build sequence (each step = one commit; code + its direct tests/docs together)
| Step | Content | Closes |
|------|---------|--------|
| **B1** | `core/auth.py` + app-level dependency + CORS env parse/invariant; tests (auth on/off matrix, exemption, 401 envelope, CORS config); D5/D7 + **ADR-013 (network-edge hardening)**; `api.py` `/metrics` docstring + run-comment updated | ITM-009 / RISK-12 |
| **B2** | `_numeric_host_to_ipv4` + `validate_base_url` flow; encoding-bypass test matrix (decimal/hex/octal/dotted/overflow/IPv6 regression) | ITM-010 |
| **B3** | `core/fileio.py` + adoption in 4 stores; round-trip + temp-cleanup + interrupted-write tests; **ADR-014 (file-store durability)**; D3 update | ITM-013 / RISK-16 |
| **B4** | `_deserialize` quarantine + preserve-on-save; malformed-store tests (corrupt v2, corrupt legacy, mixed, persistence of quarantined raw); profiles/schema-store verification | ITM-014 |
| **B5** | ITM-017 arms (api 500, nl2sql split, UI refs); leak tests (raw text absent, verbatim classes intact, `error_id` present) | ITM-017 |
| **B6** | Governed-doc sweep: charter status, D3/D5/D6/D7 reconciliation, CHANGELOG, traceability, issue log (**close ITM-009/010/013/014/017**), risk register (RISK-12/16), tracker; review package (R6.5.1) | — |

## 7. Test plan (all offline; no live Oracle; no new deps)
- **Auth:** key unset → all endpoints behave as today (regression: existing 185 tests run
  env-unset and must stay green untouched); key set → 401 without/with-wrong key on a sampled
  endpoint matrix + `/metrics`, 200 with key, `/health` exempt, 401 body carries `error_id` +
  `X-Request-ID` echo; no key material in logs.
- **CORS:** default origins applied; env override parsed; `*` in env → credentials forced off.
- **SSRF:** each encoding of `127.0.0.1`/`10.x` rejected (decimal int, `0x` hex, octal, 2/3-part
  dotted, mixed-base dotted); `4294967296` + `1.2.3.4.5` rejected fail-closed; public IP +
  hostname + `[::1]` behaviour unchanged.
- **Atomicity:** helper round-trips; temp file cleaned on simulated dump failure; target
  untouched when the write raises mid-dump (old content intact — the "interrupted write" proxy);
  all four stores still serialize byte-identically.
- **Corruption:** store with one corrupt v2 record → `list`/`get` serve the rest, log emitted;
  corrupt record still present in the file after a `create()` of another report; corrupt legacy
  record quarantined likewise.
- **ITM-017:** nl2sql unexpected-exception body contains no raw exception text but does contain
  `error_id`; `LLMError` and `SecretConfigError` text verbatim; UI arms show `(ref: …)`.
- Full suite green on **3.11 + 3.13** in CI.

## 8. Risk → mitigation mapping (from charter)
| Charter risk | Design answer |
|---|---|
| R6.5-1 auth breaks consumers | opt-in env gate (4.1); default posture regression-tested untouched |
| R6.5-2 CORS breaks consumers | env-driven origins + documented default (4.2, D7) |
| R6.5-3 store refactor corrupts data | byte-identical serialization, same-volume `os.replace`, quarantine-preserve (4.4/4.5), round-trip tests |
| R6.5-4 over-sanitizing hides guidance | D-F verbatim classes (`SecretConfigError`, `LLMError`) (4.6) |
| R6.5-5 authN/Z scope creep | one static key, no identity/sessions; anything more is Phase 7+ |
| R6.5-6 chokepoint regression | `sql_safety.py`/`db.py` untouched; full regression + reviewer probes |

## 9. Rollback / safety
- Every layer is independently revertible: unset `APP_API_KEY` → auth off; unset
  `ALLOWED_ORIGINS` → shipped localhost default; `fileio` adoption is a drop-in write-path swap
  (read path unchanged); quarantine only widens availability; ITM-017 narrows information flow
  only. Each build step is one commit for clean bisect/revert.

## 10. Notes / minor
- ADR numbering: **ADR-013** network-edge hardening (auth + CORS), **ADR-014** file-store
  durability (atomic writes + quarantine). Recorded in B1/B3 respectively.
- `/health` body is already minimal (`{"status": "ok"}`) — D-B needs no body change, only the
  documented exemption.
- The `0.0.0.0` item in ITM-009 is documentation (D7 bind guidance), not app code — the bind is
  chosen by the deployment command.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-11 | Engineering | Initial design + build sequence B1…B6 per resolved decisions D-A…D-F; pending owner approval before any code. |
| 1.1 | 2026-06-11 | Engineering | Owner approved as-is → Baseline; build started at B1. |
