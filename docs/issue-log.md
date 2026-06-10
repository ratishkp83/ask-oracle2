# D12 — Issue / Bug Log

> **Document:** Issue Log · **Version:** 1.0 · **Status:** Living · **Owner:** Engineering · **Last updated:** 2026-06-10

## Bug workflow (mandatory)

`Identify → Reproduce → Root Cause Analysis → Fix Plan → Validation → Documentation Update`

Each defect is logged with **severity** (S1 critical … S4 trivial), **impact**, and **resolution status** (Open / In Progress / Fixed / Closed / Won't Fix). A fix is not "done" until tests + docs are updated.

## Log

| ID | Title | Severity | Impact | Status | Notes / RCA |
|----|-------|----------|--------|--------|-------------|
| BUG-001 | Hardcoded API key + stubbed `/execute` in original `src/api.py` | S1 | Secret exposure; safety not enforced via API | **Fixed** | Consolidated onto wired API; key removed; chokepoint added. Validated by `test_execute_endpoint.py`. |
| BUG-002 | Prefix-only safety check rejected valid `SELECT\n…` and missed stacked/`FOR UPDATE`/PL-SQL | S2 | False rejections + safety gaps | **Fixed** | Replaced with layered sqlglot engine. Regression cases in `test_sql_safety.py`. |
| BUG-003 | `docker-compose.yml` referenced non-existent `Dockerfile` | S3 | `docker compose build` fails | **Fixed** | Repointed to `Dockerfile.api.local`. |
| OPS-004 | `.env` not in `.gitignore` (Groq key tracked) | S1 | Secret leak | **Closed** | Added `.env` to ignore; keys **rotated** by user 2026-06-10 ([RISK-01](risk-register.md)). |
| BUG-005 | App crashes (`StreamlitDuplicateElementId`) once a profile exists — duplicate `Delete selected` button across Connections + Saved Reports tabs | S2 | UI unusable whenever ≥1 saved profile | **Fixed** | Workflow: Identified+Reproduced by `test_app_smoke.py`; RCA = identical auto-generated widget IDs across tabs; Fix = unique `key=` on colliding widgets (+`sys.path` shim); Validated green (51/51). |

## Open items (non-defect, tracked)

- ITM-005: Streamlit UI not browser-verified — see [RISK-04](risk-register.md).
- ITM-006: Migrate legacy `connection.json` (plaintext) to encrypted profiles — see [RISK-09](risk-register.md). **(Phase 4 r1, F5 — FIXED 2026-06-10):** the plaintext-password-at-rest is resolved — `save_connection_config` now **strips the password** before writing, so it is never persisted (session-only); profiles remain the encrypted path (`test_storage.py`). The broader migration of the manual single-connection path onto encrypted profiles (removing `connection.json` entirely) remains open under this item.
- ITM-007: `use_container_width` is deprecated in Streamlit (removal scheduled post-2025-12-31); migrate `st.button`/`st.dataframe`/`st.download_button` calls to `width='stretch'`. Severity S4 (warning only; app functions).
- ITM-008: (deferred from F3) optional NL-question PII scrubbing before external send. Current mitigation: question text is sent by design; tenants set `LLM_POLICY=external_disabled`. Rationale: the question is the user's own intent; scrubbing risks degrading legitimate queries. Revisit with the redaction/policy work.
- ITM-009: pre-existing CORS `allow_origins=["*"]` + `allow_credentials=True` + `0.0.0.0` bind (`src/api.py`) — harden (specific origins, auth) before any multi-tenant deployment. Flagged by Phase-3 reviewer §5; out of Phase-3 scope. **r2: deferral confirmed acceptable** (pre-existing, inert for single-session posture) — hard precondition for any networked/multi-tenant deployment ([RISK-12](risk-register.md)).
- ITM-010: (F7, from r2) `validate_base_url` (`src/core/llm/providers.py`) only checks canonical IP literals via `ipaddress.ip_address`, so integer/hex/octal encodings of loopback (`2130706433`, `0x7f000001`, `017700000001` = 127.0.0.1) are treated as hostnames and allowed. Severity **S4** — **not exploitable on the tested stack** (`getaddrinfo` does not resolve those forms → fails closed at the network layer); platform/resolver-dependent. Fix: reject bare-integer/`0x…` hosts or normalize via `getaddrinfo` + re-apply the private/loopback check. Tracked under [RISK-11](risk-register.md) residual. Linux/Docker-target behavior not yet verified.
- ITM-011: (Phase 4, charter D-B) **list / multi-value bind parameters deferred.** v1 supports scalar binds only (string/number/date); `IN (:list)` expansion needs a safe design (e.g. generating `:p0,:p1,…` binds, not interpolation). Severity S4 (feature gap). Revisit when a report needs multi-value filters.
- ITM-012: (Phase 4) **EBS template SQL not validated against a live instance.** The catalog is proven safe (every template passes `assert_safe_select`) and param-consistent, but standard EBS table/column names vary by version/customization; templates are review-before-run starting points. Live-EBS validation is part of the pre-GA manual/live-DB pass ([RISK-04](risk-register.md) / [RISK-14](risk-register.md)).
- ITM-013: (Phase 4 r1, R1 — S4) **File-store durability/concurrency.** `JsonFileReportStore._save_locked` (and the mirror in `profiles.py`) do a non-atomic truncate+write with a per-process lock — crash-during-write can corrupt the JSON; >1 worker can lose updates. Fix before multi-worker/Phase 7: write temp + `os.replace`, add a file lock, or move to SQLite. Tracked under [RISK-16](risk-register.md).
- ITM-014: (Phase 4 r1, R2 — S4) **Legacy-migration robustness.** `_deserialize` treats any record missing `id`/`name` as legacy and raises uncaught on a malformed v2 record (→ 500 on `list/get`). Harden: distinguish "legacy shape" from "corrupt v2"; skip+log bad records. Add a malformed-store test.
- ITM-016: (Phase 5 r2, F-4 residual — S4) **CI Python version vs dev.** CI ran the suite on **Python 3.11** while local dev/review ran **3.13.2**. **Phase 6 / B5 added a `["3.11","3.13"]` matrix — but the Phase-6 exit-gate review (r1) found that closure PREMATURE** (F-1/F-2): (a) the then-pinned `numpy==1.26.4`/`pandas==2.2.2` had **no cp313 wheels** so the 3.13 leg could not install the set, and (b) `httpx>=0.27` floated to 0.28 which broke `openai==1.43.0` on **every** leg — and since the branch was unpushed, **CI had never actually run**. **Remediated (R6.2):** the validated set was re-pinned to a clean-installable, 3.13-capable configuration (`numpy==2.2.6`, `pandas==2.2.3`, `streamlit==1.58.0`, `fastapi==0.136.3`, `uvicorn==0.49.0`, `Pillow==11.0.0`; `httpx>=0.27,<0.28` keeping `openai==1.43.0`); **proven by a clean-room `pip install -r requirements-dev.txt` + `pytest` → 185 passed on Python 3.13.** Status: **Mitigating → closes when the owner pushes and CI demonstrates green on both legs** (3.11 leg: same pins ship cp311 wheels, code is interpreter-agnostic — wheel-availability-confirmed, CI-run pending push).
- ITM-017: (Phase 6 r1 F-7 — S4, **Phase-7**) **Non-DB `str(exc)` surfaces** still echo raw exception text: `SecretConfigError`→500 (`api.py`), the NL→SQL `except Exception`→400 (`api.py`), and a UI `st.error(str(e))` config path (`app.py`). These are **outside ITM-015's DB-sanitization scope** (driver/connection errors) and **pre-existing/unchanged** in Phase 6; the messages are config/provider guidance, not DSNs/credentials. Optionally route the catch-all LLM/500 surfaces through the same generic+`error_id` treatment in a Phase-7 hardening pass. Non-blocking.
- ITM-015: (Phase 4 r1 F6 + Phase 5 r1 F-2 *400-path* — S3) **Verbatim driver errors** returned as `detail=str(exc)` from `_run_sql`/`/test-connection`/`/profiles/{id}/test` **and `POST /schemas/introspect`** could leak DSN/host/port/username (never the password). **✅ CLOSED — Phase 6 / B2 (`c490910`…HEAD).** Resolved **uniformly** across all DB-touching endpoints (it was originally deferred to Phase 7 specifically to keep the fix consistent across endpoints — Phase 6 delivered exactly that batch): the shared `src/api.py:_db_error` helper (backed by `src/core/errors.log_error`) now returns a generic `detail = "Database error — see server logs."` + `error_id`, logging the full driver detail server-side under that id ([ADR-012](adr/ADR-012-observability-and-error-handling.md)). The same `core/errors` rule is shared by the UI (`sanitize_db_error_for_ui`). Validated by `tests/test_error_handling.py` (asserts no host/DSN/username in any client body; full detail present in the server-side log keyed by `error_id`). *Note: the Phase-5 success-path `warnings[]` leak (F-2 200-path) was already fixed in Phase 5.*

## Phase 3 — independent review findings & remediation (r1 → r2)

Sources: [reviews/phase-3-review-r1.md](reviews/phase-3-review-r1.md) (verdict: FAIL — 2 blocking) → remediated (`29d956b`) → [reviews/phase-3-review-r2.md](reviews/phase-3-review-r2.md) (verdict: **PASS-WITH-FIXES — no open blocking; gate passes**). r2 independently re-executed every probe; 75 tests green.

| ID | Sev | Finding | Disposition | Status (r2-verified) |
|----|-----|---------|-------------|--------|
| F1 | S2 | Confidence `High` on a nonsensical join (design §6 join signal not implemented) | **Fixed** — join predicates validated against `schema.relationships`; capped at Medium when joins present but no relationship metadata | ✅ Fixed (regression: `test_llm_confidence.py`) |
| F2 | S2 | `RetryError[...]` repr leaked as the API error on provider-call failure | **Fixed** — `reraise=True` + wrap in clean `LLMError` | ✅ Fixed (unit + HTTP-layer tests) |
| F3 | S3 | Tripwire scans schema context only; NL question sent verbatim; package wording oversold | **Fixed (wording)** + **Deferred** scrubbing → ITM-008 | ✅ Fixed/Deferred (r2: deferral acceptable) |
| F4 | S3 | Unvalidated per-request `base_url` (SSRF surface) | **Fixed** — `validate_base_url` (https + block private/loopback/link-local/metadata) | ✅ Fixed ([RISK-11](risk-register.md); residuals F7/ITM-010 + DNS-rebinding) |
| F5 | S3 | Column resolution global, not per-table | **Fixed** — per-table (qualified) / referenced-tables (unqualified) resolution | ✅ Fixed |
| F6 | S4 | `api_key` printed by `LLMConfig`/`LLMSettings` repr | **Fixed** — `repr=False` on both | ✅ Fixed |
| F7 | S4 | (r2) `validate_base_url` allows integer/hex/octal IP encodings of loopback | **Backlogged** → ITM-010 (not exploitable on tested stack; non-blocking) | Open (S4) |

## Phase 4 — independent review findings & remediation (r1)

Source: [reviews/phase-4-review-r1.md](reviews/phase-4-review-r1.md) — verdict **PASS-WITH-FIXES** (no S1/S2; 118 tests at review time). Post-remediation suite: **130 tests green** (F2/F3/F4 fixes + F5 fix).

| ID | Sev | Finding | Disposition | Status |
|----|-----|---------|-------------|--------|
| F1 | S3* | A SELECT can call a side-effecting / autonomous-txn PL/SQL function (`DBMS_LOCK.SLEEP` etc.) — parse gate can't prove side-effect-freedom | **Fixed (documented control):** least-privilege read-only DB account made a required deployment precondition ([ADR-009](adr/ADR-009-readonly-db-account-precondition.md), [Deployment §0](07-deployment-plan.md)); guarantee reframed as defense-in-depth (D1/D3 + `sql_safety` docstring); [RISK-15](risk-register.md). *Owner severity call (S3 vs S2) + optional parse denylist pending.* | ✅ Documented |
| F2 | S3 | `SELECT … INTO …` passed the gate (not a read-only projection) | **Fixed** — reject `exp.Into` in `assert_safe_select` | ✅ Fixed (`test_sql_safety.py`) |
| F3 | S3 | `number` params accepted non-finite `nan`/`inf`/`1e400` | **Fixed** — `validate_binds` + `_coerce_value` reject non-finite floats (`math.isfinite`) | ✅ Fixed (`test_bind_safety.py`, `test_reports.py`, `test_reports_api.py`) |
| F4 | S4 | Contract says `/execute` rejects both `profile_id`+`connection` (422); code accepted both | **Fixed** — validator enforces exactly-one | ✅ Fixed (`test_execute_endpoint.py`) |
| F5 | S3 | Manual-entry **Save** writes plaintext password to `connection.json` (pre-existing legacy path) | **Fixed** (owner-approved) — `save_connection_config` strips the password; it is never persisted (session-only). Profiles remain the encrypted-persistence path; full manual→profile migration stays [ITM-006](#) | ✅ Fixed (`test_storage.py`) |
| F6 | S3 | Verbatim driver errors leak DSN/host (never password) | **Deferred to Phase 7** → [ITM-015](#) (inert in local posture; bundle with CORS/auth hardening) | ⏳ Deferred |
| R1 | S4 | Non-atomic file writes + per-process lock | **Backlogged** → [ITM-013](#)/[RISK-16](risk-register.md) (Phase-7 multi-worker gate) | 📋 Backlog |
| R2 | S4 | Fragile legacy migration on corrupt v2 record | **Backlogged** → [ITM-014](#) | 📋 Backlog |

## Phase 5 — independent review findings & remediation (r1)

Source: [reviews/phase-5-review-r1.md](reviews/phase-5-review-r1.md) — verdict **FAIL** (1 blocking, F-1 S2; 155 tests at review time). Post-remediation suite: **159 tests green**. r2 pending (re-review required after a blocking finding).

| ID | Sev | Finding | Disposition | Status |
|----|-----|---------|-------------|--------|
| F-1 | **S2** | `POST /schemas` persisted an arbitrary `definition` blob **verbatim** to plaintext `schemas.json` (stored fake `db_password`, SSN row data, connection string) — "metadata-only persistence" not enforced | **Fixed** (chose to fix over the offered owner-waiver — cheap + also closes F-3): `create_schema` normalizes via `schema_to_dict(schema_from_dict(...))`; `schema_from_dict` is now whitelist-only (drops non-schema keys) | ✅ Fixed (`test_schemas_api.py`, `test_schema_tools.py`) |
| F-2 | S3 | Raw driver exception echoed into the **200** `warnings[]` and the introspect **400** `detail` (host/object names) | **Fixed (200-path)** — `warnings[]` now generic ("…unavailable for this account."), raw `exc` logged server-side only. **Deferred (400-path)** introspect verbatim DB error → [ITM-015](#) (Phase-7, uniform with `/execute`) | ✅ Fixed / ⏳ Deferred (`test_introspection.py`) |
| F-3 | S3 | `schema_from_dict` raised `TypeError` on malformed stored definition; UI **Load** unguarded → Streamlit crash | **Fixed** — tolerant `schema_from_dict` (never raises) **+** UI Load `try/except` | ✅ Fixed (`test_schema_tools.py`) |
| F-4 | S3 | Test venv drifted from pins; **sqlglot unpinned** while the safety layer is parser-version-sensitive | **Fixed** — `sqlglot==30.10.0` (exact, safety-critical); `pydantic==2.13.4`, `oracledb==4.0.1`, `cryptography==48.0.1` pinned to the **validated** set so `pip install -r requirements.txt` reproduces the green suite. Live-Oracle `oracledb` 4.0.1 thin-mode validation at pre-GA ([RISK-04](risk-register.md)) | ✅ Fixed |
| F-5 | S4 | Empty `owner` → 422 vs whitespace → 400 (contract says 400 for blank) | **Fixed** — dropped `owner` `min_length`; blank (empty **and** whitespace) → uniform **400** | ✅ Fixed (`test_schemas_api.py`) |
| N-1 | S4 | (r2, new — introduced by the F-1 fix) `schema_from_dict` kept a column's own `table_name` even when it disagreed with the containing table key | **Fixed at closure** — column `table_name` normalized to the table key; pure-metadata, no invariant impact | ✅ Fixed (`test_schema_tools.py`) |

**r2 verdict: PASS-WITH-FIXES — gate cleared** ([phase-5-review-r2.md](reviews/phase-5-review-r2.md)). F-1 fixed + independently re-verified; F-2 200-path fixed, **400-path deferral confirmed acceptable** (→ ITM-015, Phase-7 uniform across all DB-touching endpoints); F-3/F-4/F-5 closed; N-1 fixed at closure. **F-4 caveat closed:** CI (`.github/workflows/ci.yml`) performs a from-scratch `pip install -r requirements-dev.txt` on a clean runner every push — the standing "green == shipped" clean-room proof (see ITM-016 for the Python-version nuance).

\* F1 severity is an owner decision (S3 with the precondition documented this phase, vs S2 gating) — the marketed "no data modification" guarantee (D1 §6) is now framed as defense-in-depth and backed by the documented read-only-account precondition either way.

## Phase 6 — independent review findings & remediation (r1 → r2)

Source: [reviews/phase-6-review-r1.md](reviews/phase-6-review-r1.md) — verdict **PASS-WITH-FIXES**
(2 blocking S2, both **dependency/CI hygiene external to the Phase-6 code**; all 9 Phase-6
invariants + suite verified green). The observability/error-handling substance cleared the
gate independently; the blocking items were that B5/ITM-016's "CI green on 3.11+3.13" was
**asserted, never run** (branch unpushed) and **not installable** as pinned. Remediated in
R6.2 → re-review **r2 = PASS** ([phase-6-review-r2.md](reviews/phase-6-review-r2.md)).

| ID | Sev | Finding | Disposition | Status |
|----|-----|---------|-------------|--------|
| F-1 | **S2** | Pinned `numpy==1.26.4`/`pandas==2.2.2` have no cp313 wheels → 3.13 CI leg can't install the set; branch unpushed → CI never ran | **Fixed** — re-pinned to a clean-installable 3.13-capable set (`numpy 2.2.6`, `pandas 2.2.3`, `streamlit 1.58.0`, `fastapi 0.136.3`, `uvicorn 0.49.0`, `Pillow 11.0.0`); **clean-room install + 185 green on 3.13** | ✅ Fixed (CI demonstration on push → ITM-016) |
| F-2 | **S2** | `httpx>=0.27` floats to 0.28 which dropped the `proxies` kwarg `openai==1.43.0` uses → 5 LLM tests fail on **both** legs (clean install) | **Fixed** — `requirements-dev.txt` pins `httpx>=0.27,<0.28` (keeps `openai==1.43.0`); clean install green | ✅ Fixed |
| F-3 | S3 | `TextFormatter` interpolates the correlation id raw → CR/LF in an inbound `X-Request-ID` could forge a log line (text format; not reachable over HTTP — h11 rejects CRLF) | **Fixed** — `sanitize_correlation_id` reduces an inbound id to `[A-Za-z0-9_.-]`, bounded ≤128, **at ingress** (protects header echo, body, logs uniformly) | ✅ Fixed (`test_error_handling.py`) |
| F-4 | S4 | `_db_error` logs `get_request_id() or new_error_id()` while the handler reads `get_request_id()` for the body → ids could diverge if middleware were skipped | **Fixed** — `_db_error` binds its id via `set_request_id`; handlers fall back to `new_error_id()` so body `error_id` is never null and always matches the logged id | ✅ Fixed |
| F-5 | S4 | Leak test didn't cover `/schemas/introspect` or assert response **headers** clean | **Fixed** — added an introspect sanitization test + header-cleanliness assertions | ✅ Fixed (185 total) |
| F-6 | Info | Review package says "9 commits (`…→fc55a46`)"; `d059295..HEAD` is now 10 (incl. the package commit `8758d82`) | **Fixed** — package note corrected (code range vs full range) | ✅ Fixed |
| F-7 | Info | Non-DB `str(exc)` surfaces (config 500, LLM 400, a UI config path) still echo raw text — outside ITM-015 scope, pre-existing | **Deferred** → [ITM-017](#) (Phase-7 hardening) | ⏳ Deferred |

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Initial log; Phase-2 defects recorded as Fixed. |
| 1.1 | 2026-06-10 | Engineering | Phase-3 r1 findings F1–F6 logged + remediated; ITM-008/009 added. |
| 1.2 | 2026-06-10 | Engineering | Phase-3 r2 verdict PASS-WITH-FIXES recorded; F7/ITM-010 logged; deferrals (ITM-008/009) confirmed acceptable. |
| 1.3 | 2026-06-10 | Engineering | Phase 4 r1 findings F1–F6/R1–R2 logged; F2/F3/F4 fixed, F1 documented (ADR-009), F5/F6 deferred, R1/R2 backlogged; ITM-013/014/015 added. |
| 1.4 | 2026-06-10 | Engineering | Phase 5 r1 findings F-1…F-5 logged; F-1 (blocking) fixed (metadata-only enforced), F-2 200-path fixed / 400-path → ITM-015, F-3/F-4/F-5 fixed; 159 tests; r2 pending. |
| 1.5 | 2026-06-10 | Engineering | Phase 5 r2 = PASS-WITH-FIXES (gate cleared); N-1 fixed at closure (160 tests); F-2 400-path deferral confirmed; F-4 caveat closed by CI; ITM-016 added. |
| 1.6 | 2026-06-10 | Engineering | Phase 6 build: **ITM-015 CLOSED** (B2 — uniform DB-error sanitization + error_id; ADR-012) and ITM-016 marked closed (B5 — CI matrix). |
| 1.7 | 2026-06-10 | Engineering | Phase 6 exit-gate r1 = PASS-WITH-FIXES: F-1/F-2 (S2) corrected ITM-016's premature closure (pins not 3.13-installable + CI never run) → **re-pinned to a clean-install-proven 3.13-capable set** (185 green); F-3/F-4/F-5 fixed; F-7→ITM-017 (Phase-7). ITM-016 now Mitigating (CI demo pending push). |
| 1.3 | 2026-06-10 | Engineering | Phase 4: ITM-011 (list/multi-value binds deferred) + ITM-012 (templates not live-EBS validated) logged. |
