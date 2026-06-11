# Phase 6.5 Charter — Pre-Deployment Hardening (carried preconditions)

> **Document:** Phase Charter · **Version:** 1.2 · **Status:** 🔄 Build (design approved 2026-06-11; executing B1…B6) · **Owner:** Product/Engineering · **Last updated:** 2026-06-11

## Lifecycle stage
**Discovery OPENED 2026-06-11; owner approved and resolved decisions D-A…D-F (all as
recommended) the same day → Design.** This mini-phase bundles the four carried **code** preconditions
that gate any networked/multi-tenant deployment (and therefore Phase 7) into one charter → one
design → one build → one independent exit-gate review:

- **ITM-009 / RISK-12** — CORS `*` + credentials + no auth (incl. unauthenticated `/health` + `/metrics`).
- **ITM-010** — `validate_base_url` accepts integer/hex/octal IP encodings of loopback (SSRF residual, Phase-3 r2 F7).
- **ITM-013/014 / RISK-16** — non-atomic file-store writes; fragile legacy-migration on corrupt v2 records.
- **ITM-017** — non-DB `str(exc)` surfaces (config 500, NL→SQL 400, UI config paths) outside the Phase-6 ITM-015 treatment.

**Out of this bundle:** **RISK-04** (manual UI + live-Oracle pass) stays a separate, owner-scheduled
pre-GA activity — it needs a real Oracle instance, not code.

## Context — grounding facts (verified against HEAD `2ba0a56`, 185 tests green)
- **ITM-009.** `src/api.py:66-68` sets `allow_origins=["*"]` with `allow_credentials=True`; no
  endpoint requires authentication; `/health` (`api.py:254`) and `/metrics` (`api.py:259`) are
  explicitly open (the `/metrics` docstring defers gating to "Phase 7 (ITM-009)"). The `0.0.0.0`
  bind is a run-comment / deployment default (`api.py:664`, Docker), not application code — it is
  addressed by documentation (D7), not a code change.
- **ITM-010.** `validate_base_url` (`src/core/llm/providers.py:20`) blocks IP literals via
  `ipaddress.ip_address(host)`, which does **not** parse integer (`https://2130706433/`), hex
  (`https://0x7f000001/`), or octal (`https://017700000001/`) encodings — those take the
  `ValueError` arm, are treated as hostnames, and pass. DNS-rebinding (a hostname that *resolves*
  private) remains a separately documented residual and is **not** in scope.
- **ITM-013.** Four JSON stores truncate-and-rewrite in place under a per-process lock only:
  `src/storage.py:34`, `src/core/profiles.py:136`, `src/core/reports.py:233`,
  `src/core/schema_store.py:130`. A crash mid-write can corrupt the file; more than one worker
  process can interleave or lose updates.
- **ITM-014.** `JsonFileReportStore._deserialize` (`src/core/reports.py`) treats any record
  missing `id`/`name` as *legacy shape*; a malformed **v2** record raises uncaught → HTTP 500 on
  `list`/`get`. "Legacy" and "corrupt" are not distinguished.
- **ITM-017** (Phase-6 r1 F-7). Three non-DB surfaces still echo raw `str(exc)`:
  the profiles-create `SecretConfigError` → 500 (`api.py:280`); the `/nl2sql` catch-all → 400
  (`api.py:377` — mixes intentional `LLMError` text with raw network/provider exceptions); and UI
  `SecretConfigError` paths (`app.py:196/247/285/716`). Note: `SecretConfigError` messages are
  **app-generated constants** (`src/core/crypto.py`) — operator-actionable and secret-free.
- **The Streamlit UI imports core modules directly** (e.g. `OracleClient` at `app.py:714`); it
  does **not** call the HTTP API. API auth therefore cannot break the UI — it affects HTTP
  consumers only.
- **Non-negotiables remain in force** (must not regress): SELECT/CTE-only via the single
  chokepoint (`sql_safety.py` → `OracleClient.run_select`; exactly one `cur.execute`/`connect` in
  `db.py`); AI proposes, never auto-runs; bind variables never interpolated (ADR-007); secrets via
  env only; metadata-only persistence; read-only DB account precondition (ADR-009). This phase
  must not touch the execution path.

## Objectives
1. **Clear every code precondition gating networked/multi-tenant deployment** —
   ITM-009/010/013/014/017 and their risk-register counterparts (RISK-12, RISK-16) — in one
   gated phase, so Phase 7 (and any deployment beyond single-user-localhost) has a clean runway.
2. **Harden the network edge:** explicit CORS origins and opt-in API authentication, including a
   deliberate, documented posture for `/health` and `/metrics`.
3. **Close the SSRF encoding bypass** in `validate_base_url`.
4. **Make the file stores durable:** atomic writes everywhere; corrupt records degrade gracefully
   instead of taking endpoints down.
5. **Finish the error-surface hygiene Phase 6 started:** the remaining non-DB `str(exc)` surfaces
   get the generic-message + `error_id` treatment (or a deliberate verbatim classification).
6. Keep everything read-only, secret-free, and governed; code + docs change together; exit via
   the independent adversarial review gate (reviewer ≠ author).

## Scope — in (subject to Decisions D-A…D-F)
- **API authentication** (per D-A/D-B): a FastAPI dependency enforcing a static API key from env
  (`APP_API_KEY`), enabled only when the variable is set; 401 with the uniform error envelope
  (`detail` + `error_id`) otherwise; exemptions per D-B.
- **CORS hardening** (per D-C): origins from env (`ALLOWED_ORIGINS`, comma-separated), sane
  localhost default; never `*` + credentials together.
- **`validate_base_url` hardening** (ITM-010): detect/normalize numeric host encodings
  (integer, hex, octal, dotted variants) before the allow/deny check; reject private/loopback in
  any encoding; tests for each form.
- **Shared atomic-write helper** (per D-D): write temp file in the same directory → flush+fsync →
  `os.replace`; adopted by all four stores (`storage.py`, `profiles.py`, `reports.py`,
  `schema_store.py`); JSON shape unchanged.
- **Corrupt-record robustness** (per D-E, ITM-014): distinguish *legacy shape* from *corrupt v2*
  in the report store; skip-and-log bad records (with `error_id`-keyed server detail); verify the
  profile/schema stores' deserialization tolerates malformed records the same way.
- **ITM-017 surfaces** (per D-F): route the three non-DB surfaces through the Phase-6
  `core/errors` treatment; classification of intentional vs raw messages per D-F.
- **Tests + governed-doc updates in the same change set:** D3 (architecture — auth dependency,
  atomic store writes), D5 (API contracts — 401 envelope, auth header, CORS/env), D7 (deployment —
  `APP_API_KEY`/`ALLOWED_ORIGINS` env vars, bind-address guidance), ADR(s) for edge hardening and
  store durability (numbering fixed at design), CHANGELOG, traceability, registers, tracker;
  **close ITM-009/010/013/014/017**; disposition RISK-12/RISK-16.

## Scope — out (explicit non-goals for Phase 6.5)
- **RISK-04** — manual UI + live-Oracle validation pass (owner-scheduled; needs a real instance).
- **Multi-user auth** — no users/roles/sessions/OAuth2/JWT; a single shared API key is the
  envelope (multi-tenant identity is Phase 7+ if ever).
- **Rate limiting / WAF / TLS termination** — deployment-platform concerns, documented in D7 only.
- **SQLite or DB-backed store migration** — unless D-D selects it; the recommendation keeps JSON.
- **DNS-rebinding resolution** for `base_url` — remains a documented residual.
- **ITM-006/007/008** (legacy `connection.json` migration, Streamlit `use_container_width`
  deprecation, NL-question PII scrubbing) — stay backlog; not part of this bundle.
- **No change to the SELECT-only chokepoint or safety behaviour.**

## Deliverables
- Auth dependency + CORS configuration in `src/api.py` (shape per D-A/D-B/D-C), env-driven,
  default-compatible with the current single-user localhost posture.
- Hardened `validate_base_url` (`src/core/llm/providers.py`) + encoding-bypass tests.
- A shared atomic-write helper (location at design; e.g. `src/core/fileio.py`) adopted by all
  four JSON stores; malformed-record handling in `reports.py` (+ verified in profiles/schema
  stores).
- ITM-017 surfaces routed through `core/errors` (generic + `error_id`, or verbatim-classified
  per D-F).
- Tests: auth on/off matrix (401/200, exemptions, envelope shape), CORS config, encoding-bypass
  rejection, atomic-write behaviour, corrupt-store resilience (list/get keep serving), ITM-017
  no-leak assertions; full regression green on 3.11 + 3.13.
- Governed docs per Scope-in; issue log closes ITM-009/010/013/014/017; risk register
  dispositions RISK-12/RISK-16.

## Risks
| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R6.5-1 | Auth breaks existing HTTP consumers / local workflows | Medium | **Opt-in**: enforced only when `APP_API_KEY` is set; default (unset) behaviour unchanged; UI unaffected (direct core imports); contract tests pin both modes |
| R6.5-2 | CORS tightening breaks a legitimate browser consumer | Low | Env-driven `ALLOWED_ORIGINS` with documented localhost default; D7 documents how to widen per deployment |
| R6.5-3 | Atomic-write refactor corrupts or loses store data | **High** | Shared helper, byte-identical JSON output, round-trip + crash-simulation tests; stores' public APIs unchanged |
| R6.5-4 | Over-sanitizing ITM-017 hides actionable config guidance (e.g. "APP_SECRET_KEY is not set…") | Medium | D-F classifies app-generated constants (`SecretConfigError`, `LLMError`) as safe-verbatim; only unexpected exception text goes generic; mirrors Phase-6 R6-1 discipline |
| R6.5-5 | Scope creep toward a full authN/Z platform | Medium | Decisions fix the envelope: one static key, no identity, no sessions; anything more is Phase 7+ |
| R6.5-6 | Regression to chokepoint / safety invariants | **High** | `sql_safety.py`/`db.py` untouched; full 185-test regression + reviewer re-runs safety probes |

## Success criteria (phase exit)
1. **Auth:** with `APP_API_KEY` set, every non-exempt endpoint returns 401 (uniform envelope,
   `error_id`) without/with a wrong key and succeeds with the right one; with it unset, behaviour
   is unchanged (documented). Exemptions exactly per D-B.
2. **CORS:** origins come from env; the shipped default is explicit (no `*`); `*` + credentials
   is impossible.
3. **SSRF:** `validate_base_url` rejects loopback/private/link-local in decimal-integer, hex,
   octal, and dotted encodings; tests prove each.
4. **Durability:** all four stores write via temp-file + fsync + `os.replace`; an interrupted
   write leaves either the old or the new complete file, never a torn one.
5. **Robustness:** a malformed v2 record is skipped and logged (server-side detail keyed by
   `error_id`); `list`/`get` keep serving good records; a malformed-store test exists.
6. **Error hygiene:** the ITM-017 surfaces never echo unexpected raw exception text to a client;
   intentional messages (per D-F) carry an `error_id` alongside; leak tests assert it.
7. Full suite green in CI on **3.11 + 3.13**; governed docs + ADRs current;
   **ITM-009/010/013/014/017 closed**; RISK-12/RISK-16 dispositioned.
8. **Independent adversarial review + QA returns PASS** ([gate](../process/external-review-gate.md));
   reviewer ≠ author, supplied by the owner.

## Open decisions (PENDING — owner to resolve; recommendations given)
> Each decision is mine to recommend but the owner's to set, because they fix the phase envelope
> and a contract surface.

- **D-A — API auth mechanism.**
  (a) **Static API key via `X-API-Key` header, value from env `APP_API_KEY`, enforced by a
  FastAPI dependency, enabled only when the env var is set** (zero new deps; fits the env-only
  secret policy and the single-tenant posture; opt-in keeps local dev frictionless) —
  **[Recommended]**;
  (b) HTTP Basic (ubiquitous tooling support, but credentials-in-every-request semantics and
  browser popup behaviour);
  (c) OAuth2/JWT (proper identity, but a heavy dependency + infrastructure for a single-tenant
  tool — Phase 7+ if ever);
  (d) No app-level auth; rely on network controls only (does **not** clear ITM-009).
  *Recommendation: (a).*

- **D-B — `/health` + `/metrics` posture.**
  (a) **`/health` stays unauthenticated** (container/orchestrator liveness probes need it) **with
  a minimal body** (status only, no version/config detail); **`/metrics` requires auth** when
  auth is enabled — **[Recommended]**;
  (b) Both behind auth (breaks liveness probes unless the platform can send headers);
  (c) Both open (does not clear the reviewer's finding on `/metrics`).
  *Recommendation: (a).*

- **D-C — CORS policy.**
  (a) **`ALLOWED_ORIGINS` env (comma-separated explicit origins), default
  `http://localhost:8501,http://localhost:3000`** (Streamlit + the inactive Vite scaffold);
  `allow_credentials=True` only ever with explicit origins — **[Recommended]**;
  (b) Keep `*` but drop `allow_credentials` (still permissive; weaker than the finding asks);
  (c) Hardcoded origin list (no per-deployment flexibility).
  *Recommendation: (a).*

- **D-D — File-store durability approach.**
  (a) **Shared atomic-write helper (temp + fsync + `os.replace`), keep the JSON stores**
  (minimal blast radius; solves crash-corruption; the per-process lock stays the documented
  single-worker constraint) — **[Recommended]**;
  (b) Migrate stores to SQLite (also solves multi-worker concurrency, but a much larger change —
  revisit when a multi-worker deployment is actually planned).
  *Recommendation: (a)* — note that multi-**worker** concurrency remains a documented limitation
  either way this phase; D7 records "single worker per store directory".

- **D-E — Corrupt-record policy (ITM-014).**
  (a) **Skip-and-log** (server-side detail + `error_id`; `list`/`get` keep serving good records)
  — **[Recommended]**;
  (b) Fail-closed (any corrupt record disables the whole store — safer-sounding but turns one bad
  record into a full outage of saved reports).
  *Recommendation: (a)* — these are saved report definitions, not financial records; availability
  wins, with a loud log line.

- **D-F — ITM-017 message classification.**
  (a) **Keep app-generated intentional messages verbatim and add `error_id`** —
  `SecretConfigError` (constants in `crypto.py`, operator guidance) and `LLMError` (our own
  validation text, e.g. the base_url rejections); **sanitize everything else** caught by those
  arms (raw network/provider/driver text → generic + `error_id`) — **[Recommended]**;
  (b) Fully generic on all three surfaces (uniform but hides "set APP_SECRET_KEY" from the very
  person who must act on it).
  *Recommendation: (a)* — same intentional-vs-raw discipline Phase 6 applied (D-D there), extended
  to the non-DB surfaces.

## Decisions (resolved 2026-06-11)
Owner approved the charter and resolved **all six decisions as recommended**.

- **D-A — API auth mechanism:** ✅ **Static API key** via `X-API-Key` header, value from env
  `APP_API_KEY`, enforced by a FastAPI dependency; **opt-in** — enforced only when the env var
  is set (default/unset behaviour unchanged; UI unaffected — direct core imports).
- **D-B — `/health` + `/metrics` posture:** ✅ **`/health` stays unauthenticated with a minimal
  status-only body; `/metrics` requires the API key** when auth is enabled.
- **D-C — CORS policy:** ✅ **`ALLOWED_ORIGINS` env** (comma-separated explicit origins),
  default `http://localhost:8501,http://localhost:3000`; `allow_credentials` only ever with
  explicit origins — `*` + credentials becomes impossible.
- **D-D — File-store durability:** ✅ **Shared atomic-write helper** (temp + fsync +
  `os.replace`), JSON stores kept; multi-worker concurrency remains a documented single-worker
  constraint (D7).
- **D-E — Corrupt-record policy:** ✅ **Skip-and-log** (server-side detail keyed by `error_id`;
  `list`/`get` keep serving good records).
- **D-F — ITM-017 message classification:** ✅ **App-generated intentional messages
  (`SecretConfigError`, `LLMError`) stay verbatim + gain `error_id`; everything else caught by
  those arms goes generic + `error_id`.**

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-11 | Product/Eng | Discovery charter opened; bundles ITM-009/010/013/014/017 (RISK-12/16) as one pre-deployment hardening mini-phase; objectives/scope/deliverables/risks/success criteria + open decisions D-A…D-F; **pending owner approval before any code**. |
| 1.1 | 2026-06-11 | Product/Eng | Owner approved; decisions D-A…D-F resolved (all as recommended). Discovery complete → Design (design + build sequence pending owner approval before code). |
| 1.2 | 2026-06-11 | Product/Eng | Design + build sequence approved by owner ([pre-deployment-hardening-design.md](../pre-deployment-hardening-design.md)) → Build; executing B1…B6. |
