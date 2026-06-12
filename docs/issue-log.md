# D12 — Issue / Bug Log

> **Document:** Issue Log · **Version:** 1.0 · **Status:** Living · **Owner:** Engineering · **Last updated:** 2026-06-12 (Phase 7 closed)

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
- ITM-006: Migrate legacy `connection.json` (plaintext) to encrypted profiles — see [RISK-09](risk-register.md). **(Phase 4 r1, F5 — FIXED 2026-06-10):** the plaintext-password-at-rest is resolved — `save_connection_config` now **strips the password** before writing, so it is never persisted (session-only); profiles remain the encrypted path (`test_storage.py`). The broader migration of the manual single-connection path onto encrypted profiles (removing `connection.json` entirely) remains open under this item. **✅ CLOSED — Round C1 / B2:** the `connection.json` **write** path is removed (`save_connection_config` deleted; the manual "Save" button retired); `storage.migrate_legacy_connection()` imports any existing file once (session-only) and **deletes it** at startup (also removing a pre-F5 plaintext file). Encrypted profiles are the single persistence path. Validated by `tests/test_storage.py`.
- ITM-007: `use_container_width` is deprecated in Streamlit (removal scheduled post-2025-12-31); migrate `st.button`/`st.dataframe`/`st.download_button` calls to `width='stretch'`. Severity S4 (warning only; app functions). **✅ CLOSED — Round C1 / B1:** all 14 call sites in `src/app.py` migrated to `width="stretch"` (verified on `streamlit==1.58.0`); smoke green.
- ITM-008: (deferred from F3) optional NL-question PII scrubbing before external send. Current mitigation: question text is sent by design; tenants set `LLM_POLICY=external_disabled`. Rationale: the question is the user's own intent; scrubbing risks degrading legitimate queries. Revisit with the redaction/policy work. **✅ CLOSED — Round C1 / B3 (charter D-C):** built behind a **default-off `SCRUB_PII`** env flag — when on, the NL question is masked (email/SSN/card/phone → typed placeholders) **on the external path only** (local stays verbatim) via `src/core/llm/pii.py`, complementing the schema-name redaction. Patterns kept conservative precisely because over-masking can degrade queries (hence opt-in). Validated by `tests/test_pii.py`.
- ITM-009: pre-existing CORS `allow_origins=["*"]` + `allow_credentials=True` + `0.0.0.0` bind (`src/api.py`) — harden (specific origins, auth) before any multi-tenant deployment. Flagged by Phase-3 reviewer §5; out of Phase-3 scope. **r2: deferral confirmed acceptable** (pre-existing, inert for single-session posture) — hard precondition for any networked/multi-tenant deployment ([RISK-12](risk-register.md)). **✅ CLOSED — Phase 6.5 / B1 ([ADR-013](adr/ADR-013-network-edge-hardening.md)):** opt-in `X-API-Key` auth (`APP_API_KEY`; `/health` exempt for liveness, `/metrics` gated) + explicit env-driven CORS (`ALLOWED_ORIGINS`, localhost default; a literal `*` forfeits credentials, so the flagged combination is unrepresentable). The `0.0.0.0` bind is a deployment choice — the network-exposure rule lives in [D7 §2](07-deployment-plan.md). Validated by `tests/test_auth.py`.
- ITM-010: (F7, from r2) `validate_base_url` (`src/core/llm/providers.py`) only checks canonical IP literals via `ipaddress.ip_address`, so integer/hex/octal encodings of loopback (`2130706433`, `0x7f000001`, `017700000001` = 127.0.0.1) are treated as hostnames and allowed. Severity **S4** — **not exploitable on the tested stack** (`getaddrinfo` does not resolve those forms → fails closed at the network layer); platform/resolver-dependent. Fix: reject bare-integer/`0x…` hosts or normalize via `getaddrinfo` + re-apply the private/loopback check. Tracked under [RISK-11](risk-register.md) residual. **✅ CLOSED — Phase 6.5 / B2:** `_numeric_host_to_ipv4` decodes `inet_aton`-style numeric hosts (decimal/hex/octal, 1–4 dot-groups; ASCII-strict) **before** the private/loopback checks, independent of platform resolver behaviour; an all-numeric host that is not a valid IPv4 is rejected **fail-closed**. Validated by the encoding matrix in `tests/test_llm_providers.py`. **Phase-6.5 review r1/R1 hardening:** the host is **NFKC-folded** before the checks, so Unicode compatibility digit forms (e.g. fullwidth `１２７.0.0.1`) collapse to ASCII and are caught too (a genuine internationalized hostname still survives as a hostname). DNS-rebinding remains the separately documented RISK-11 residual.
- ITM-011: (Phase 4, charter D-B) **list / multi-value bind parameters deferred.** v1 supports scalar binds only (string/number/date); `IN (:list)` expansion needs a safe design (e.g. generating `:p0,:p1,…` binds, not interpolation). Severity S4 (feature gap). Revisit when a report needs multi-value filters.
- ITM-012: (Phase 4; **extended Phase 7**) **EBS template SQL + metadata-pack contents not validated against a live EBS instance.** The template catalog (Phase 4) and the EBS metadata packs (Phase 7, `core/ebs_packs.py`) reference standard R12.2 table/column names that vary by version/customization; both are review-before-run. The catalog is proven safe (every template passes `assert_safe_select`) and param-consistent; packs are proven internally consistent + redaction-safe (`test_ebs_packs.py`). **Validation method (defined Phase 7):** (1) **knowledge-based self-audit** done — [reviews/ebs-pack-self-audit.md](reviews/ebs-pack-self-audit.md) (all table names High-confidence; two columns flagged to verify first); (2) **automated live check** — `scripts/ebs_pack_validate.py` introspects a real EBS 12.2 instance through the SELECT-only chokepoint and diffs every pack table/column against `ALL_TAB_COLUMNS` (offline-tested via `test_ebs_pack_validate.py`; needs an instance to run). **Close criteria:** run the validator against a real EBS (a customer/pilot dev-test, an Oracle **Vision** demo, or an OCI EBS image) with a least-privilege read-only account → resolve any `[MISSING …]` → re-run clean → record the output as evidence; likewise spot-run representative templates. There is **no lightweight EBS** (unlike XE/23ai Free), so this remains gated on access to an EBS environment. Tracked alongside [RISK-04](risk-register.md) / [RISK-14](risk-register.md).
- ITM-013: (Phase 4 r1, R1 — S4) **File-store durability/concurrency.** `JsonFileReportStore._save_locked` (and the mirror in `profiles.py`) do a non-atomic truncate+write with a per-process lock — crash-during-write can corrupt the JSON; >1 worker can lose updates. Fix before multi-worker/Phase 7: write temp + `os.replace`, add a file lock, or move to SQLite. Tracked under [RISK-16](risk-register.md). **✅ CLOSED (durability) — Phase 6.5 / B3 ([ADR-014](adr/ADR-014-file-store-durability.md)):** `core/fileio.py::atomic_write_json` (same-dir temp + fsync + `os.replace`) adopted by all four JSON stores; an interrupted write leaves the old or the new complete file, never a torn one (`tests/test_fileio.py`). The **multi-worker concurrency half is deliberately not solved**: one-worker-per-store-directory is the documented deployment constraint (D7); SQLite is the revisit point if a multi-worker deployment is planned.
- ITM-014: (Phase 4 r1, R2 — S4) **Legacy-migration robustness.** `_deserialize` treats any record missing `id`/`name` as legacy and raises uncaught on a malformed v2 record (→ 500 on `list/get`). Harden: distinguish "legacy shape" from "corrupt v2"; skip+log bad records. Add a malformed-store test. **✅ CLOSED — Phase 6.5 / B4 ([ADR-014](adr/ADR-014-file-store-durability.md) §3):** corrupt records (v2 **or** unparseable legacy) are **quarantined** — skipped from serving, logged once per process with an `error_id` (record key + exception type only), and **preserved verbatim on save** (incl. through the in-place legacy-migration save) so corruption never becomes silent data loss. The profile and schema stores had the same uncaught-raise mode and received the same treatment. Validated by `tests/test_store_robustness.py`.
- ITM-016: (Phase 5 r2, F-4 residual — S4) **CI Python version vs dev.** CI ran the suite on **Python 3.11** while local dev/review ran **3.13.2**. **Phase 6 / B5 added a `["3.11","3.13"]` matrix — but the Phase-6 exit-gate review (r1) found that closure PREMATURE** (F-1/F-2): (a) the then-pinned `numpy==1.26.4`/`pandas==2.2.2` had **no cp313 wheels** so the 3.13 leg could not install the set, and (b) `httpx>=0.27` floated to 0.28 which broke `openai==1.43.0` on **every** leg — and since the branch was unpushed, **CI had never actually run**. **Remediated (R6.2):** the validated set was re-pinned to a clean-installable, 3.13-capable configuration (`numpy==2.2.6`, `pandas==2.2.3`, `streamlit==1.58.0`, `fastapi==0.136.3`, `uvicorn==0.49.0`, `Pillow==11.0.0`; `httpx>=0.27,<0.28` keeping `openai==1.43.0`); **proven by a clean-room `pip install -r requirements-dev.txt` + `pytest` → 185 passed on Python 3.13.** **✅ CLOSED — 2026-06-10:** branch pushed (`d059295..2a88a04`); **CI run #7 = success with both matrix legs green** (`test (3.11)` ✅ + `test (3.13)` ✅), so "green == shipped" is now *demonstrated* on every interpreter the matrix targets, not asserted.
- ITM-017: (Phase 6 r1 F-7 — S4, **Phase-7**) **Non-DB `str(exc)` surfaces** still echo raw exception text: `SecretConfigError`→500 (`api.py`), the NL→SQL `except Exception`→400 (`api.py`), and a UI `st.error(str(e))` config path (`app.py`). These are **outside ITM-015's DB-sanitization scope** (driver/connection errors) and **pre-existing/unchanged** in Phase 6; the messages are config/provider guidance, not DSNs/credentials. Optionally route the catch-all LLM/500 surfaces through the same generic+`error_id` treatment in a Phase-7 hardening pass. Non-blocking. **✅ CLOSED — Phase 6.5 / B5 (charter D-F):** `/nl2sql`'s catch-all is split — intentional `ValueError`/`LLMError` texts stay **verbatim** (the ADR-012 rule), any other exception returns the generic `"Could not generate SQL — see server logs."` + `error_id` with full detail logged server-side; the profiles `SecretConfigError` 500 keeps its operator guidance verbatim and gains a server-side breadcrumb keyed to the response's `error_id`; the four UI `SecretConfigError` arms show `(ref: <id>)` via `core.errors.log_error_for_ui`. Validated in `tests/test_error_handling.py`.
- ITM-015: (Phase 4 r1 F6 + Phase 5 r1 F-2 *400-path* — S3) **Verbatim driver errors** returned as `detail=str(exc)` from `_run_sql`/`/test-connection`/`/profiles/{id}/test` **and `POST /schemas/introspect`** could leak DSN/host/port/username (never the password). **✅ CLOSED — Phase 6 / B2 (`c490910`…HEAD).** Resolved **uniformly** across all DB-touching endpoints (it was originally deferred to Phase 7 specifically to keep the fix consistent across endpoints — Phase 6 delivered exactly that batch): the shared `src/api.py:_db_error` helper (backed by `src/core/errors.log_error`) now returns a generic `detail = "Database error — see server logs."` + `error_id`, logging the full driver detail server-side under that id ([ADR-012](adr/ADR-012-observability-and-error-handling.md)). The same `core/errors` rule is shared by the UI (`sanitize_db_error_for_ui`). Validated by `tests/test_error_handling.py` (asserts no host/DSN/username in any client body; full detail present in the server-side log keyed by `error_id`). *Note: the Phase-5 success-path `warnings[]` leak (F-2 200-path) was already fixed in Phase 5.*

- ITM-018: (Phase 7, charter D-A — S4/feature) **Oracle 23ai vector track deferred.** AI Vector
  Search / in-DB ML to augment NL→SQL (semantic glossary/schema matching) needs an Oracle 23ai
  instance to build and test against; the dev box runs XE 21c (no `VECTOR` type). Deferred with a
  recorded design direction ([ADR-016](adr/ADR-016-defer-23ai-vector-track.md)) — **not dropped**.
  Revisit when a 23ai instance is available or a customer requires it; re-open as its own
  chartered effort (design + exit-gate review). Non-blocking; the testable EBS-packs value shipped
  in Phase 7.

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
| F7 | S4 | (r2) `validate_base_url` allows integer/hex/octal IP encodings of loopback | **Backlogged** → ITM-010 (not exploitable on tested stack; non-blocking) | ✅ Closed (Phase 6.5 / B2) |

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
| R1 | S4 | Non-atomic file writes + per-process lock | **Backlogged** → [ITM-013](#)/[RISK-16](risk-register.md) (Phase-7 multi-worker gate) | ✅ Closed (Phase 6.5 / B3; multi-worker = documented D7 constraint) |
| R2 | S4 | Fragile legacy migration on corrupt v2 record | **Backlogged** → [ITM-014](#) | ✅ Closed (Phase 6.5 / B4) |

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
| F-1 | **S2** | Pinned `numpy==1.26.4`/`pandas==2.2.2` have no cp313 wheels → 3.13 CI leg can't install the set; branch unpushed → CI never ran | **Fixed** — re-pinned to a clean-installable 3.13-capable set (`numpy 2.2.6`, `pandas 2.2.3`, `streamlit 1.58.0`, `fastapi 0.136.3`, `uvicorn 0.49.0`, `Pillow 11.0.0`); **clean-room install + 185 green on 3.13**; pushed → **CI run #7 green on both 3.11 + 3.13** (ITM-016 closed) | ✅ Fixed + CI-demonstrated |
| F-2 | **S2** | `httpx>=0.27` floats to 0.28 which dropped the `proxies` kwarg `openai==1.43.0` uses → 5 LLM tests fail on **both** legs (clean install) | **Fixed** — `requirements-dev.txt` pins `httpx>=0.27,<0.28` (keeps `openai==1.43.0`); clean install green | ✅ Fixed |
| F-3 | S3 | `TextFormatter` interpolates the correlation id raw → CR/LF in an inbound `X-Request-ID` could forge a log line (text format; not reachable over HTTP — h11 rejects CRLF) | **Fixed** — `sanitize_correlation_id` reduces an inbound id to `[A-Za-z0-9_.-]`, bounded ≤128, **at ingress** (protects header echo, body, logs uniformly) | ✅ Fixed (`test_error_handling.py`) |
| F-4 | S4 | `_db_error` logs `get_request_id() or new_error_id()` while the handler reads `get_request_id()` for the body → ids could diverge if middleware were skipped | **Fixed** — `_db_error` binds its id via `set_request_id`; handlers fall back to `new_error_id()` so body `error_id` is never null and always matches the logged id | ✅ Fixed |
| F-5 | S4 | Leak test didn't cover `/schemas/introspect` or assert response **headers** clean | **Fixed** — added an introspect sanitization test + header-cleanliness assertions | ✅ Fixed (185 total) |
| F-6 | Info | Review package says "9 commits (`…→fc55a46`)"; `d059295..HEAD` is now 10 (incl. the package commit `8758d82`) | **Fixed** — package note corrected (code range vs full range) | ✅ Fixed |
| F-7 | Info | Non-DB `str(exc)` surfaces (config 500, LLM 400, a UI config path) still echo raw text — outside ITM-015 scope, pre-existing | **Deferred** → [ITM-017](#) (Phase-7 hardening) | ✅ Closed (Phase 6.5 / B5) |

## Phase 6.5 — independent review findings & remediation (r1)

Source: [reviews/phase-6.5-review-r1.md](reviews/phase-6.5-review-r1.md) — verdict
**PASS-WITH-FIXES** (no S1/S2; **236 tests** at review time; all 9 phase invariants verified
green). Reviewer ≠ author. Post-remediation suite: **242 tests green**. The gate is cleared by
the verdict (no blocking findings); all four findings were nonetheless remediated immediately.

| ID | Sev | Finding | Disposition | Status |
|----|-----|---------|-------------|--------|
| R1 | S3 | Unicode **fullwidth-digit** SSRF first-line bypass — `１２７.0.0.1` (U+FF11…) passes `validate_base_url` because the numeric detection is ASCII-only; only httpx's downstream IDNA check then stops it, so the "reject in every encoding" invariant was incomplete | **Fixed** — `validate_base_url` NFKC-folds the host **before** the `_BLOCKED_HOSTS` + numeric/IP checks, so compatibility digit/letter forms collapse to ASCII and are caught at the first-line guard (layer-independent); a genuine internationalized hostname still survives as a hostname (NFKC = the same step an IDNA resolver applies — we fold the encoding, we don't reject non-ASCII outright) | ✅ Fixed (`test_llm_providers.py`: fullwidth dotted/decimal/`localhost` rejected, genuine IDN passes) |
| R2 | S3 | File-descriptor leak in `atomic_write_json` if `os.fdopen` raises after `mkstemp` (theoretical) — the `except` unlinked the temp but never closed `fd` | **Fixed** — `except` now `os.close(fd)` (no-op on the normal path, where the `with` already closed it) before unlink | ✅ Fixed (`src/core/fileio.py`) |
| R3 | S4 | Whitespace-only `ALLOWED_ORIGINS` (e.g. `"   "`) is truthy → skips the localhost default → empty origins list (denies all CORS) instead of the documented default | **Fixed** — `_cors_config` strips before the `or` default, so blank/whitespace falls back to the localhost pair | ✅ Fixed (`test_auth.py::test_cors_whitespace_falls_back_to_default`) |
| R4 | S4 | Undocumented asymmetry: `APP_API_KEY` is read per-request (live rotation) while `ALLOWED_ORIGINS` is read once at import (restart required) | **Fixed (doc)** — noted in `_cors_config` docstring and [D7 §2](07-deployment-plan.md) | ✅ Documented |

## Round C1 — independent review findings & remediation (r1)

Source: [reviews/round-C1-review-r1.md](reviews/round-C1-review-r1.md) — verdict
**PASS-WITH-FIXES** (no S1/S2; reviewer ≠ author; B1–B3 code, range `a395003..f374380`; all
item invariants + the SELECT-only chokepoint verified clean). Post-remediation suite: **262
tests green**. Gate cleared by the verdict; both findings remediated immediately.

| ID | Sev | Finding | Disposition | Status |
|----|-----|---------|-------------|--------|
| C1-R1-F1 | S3 | `migrate_legacy_connection` swallowed `OSError` from `os.remove(CONFIG_FILE)` with a bare `pass` — if the legacy file can't be deleted (locked/read-only), a plaintext connection file could remain at rest with no warning | **Fixed** — the `except OSError` now logs a `warning` via `get_logger("storage")` (the file path + error, **not** the secret value) and still returns the config so startup proceeds | ✅ Fixed (`test_storage.py::test_migrate_warns_and_proceeds_when_delete_fails`) |
| C1-R1-F2 | S4 | TOCTOU in `load_connection_config` between `os.path.exists` and `open` — a concurrent delete would raise `FileNotFoundError` up through startup | **Fixed** — dropped the `exists()` check; `open` directly, `except FileNotFoundError: return None` | ✅ Fixed (`test_storage.py::test_load_returns_none_when_file_missing`) |

## Phase 7 — independent review findings & remediation (r1)

Source: [reviews/phase-7-review-r1.md](reviews/phase-7-review-r1.md) — verdict **PASS** (no
blocking; reviewer ≠ author; all 7 phase invariants verified, incl. chokepoint-untouched and
EBS-context tripwire-safety). Two S4 observations, both remediated. Post-remediation: **293 tests**.

| ID | Sev | Finding | Disposition | Status |
|----|-----|---------|-------------|--------|
| P7-R1-F1 | S4 | Unknown `ebs_modules` (e.g. `["BOGUS"]`) silently ignored by `/nl2sql` — valid 200 but no EBS context and no feedback | **Fixed** — `NL2SQLRequest.ebs_modules` field-validator rejects unknown modules (422 with a clear message) and normalizes case (`['ap']`→`AP`) | ✅ Fixed (`test_packs_api.py`: unknown→422, known-lowercase accepted) |
| P7-R1-F2 | S4 | `/v1` auth test covered `/v1/metrics` only — `/v1/execute` + `/v1/nl2sql` (safety+auth) not exercised | **Fixed** — parametrized `test_v1_post_endpoints_require_auth` asserts 401 without key on both POST paths | ✅ Fixed (`test_v1_prefix.py`) |

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
| 1.8 | 2026-06-11 | Engineering | Phase 6.5 build B1–B5: **ITM-009 CLOSED** (ADR-013 edge auth/CORS), **ITM-010 CLOSED** (encoding decode, fail-closed), **ITM-013 CLOSED** (atomic writes, ADR-014; multi-worker = D7 constraint), **ITM-014 CLOSED** (quarantine), **ITM-017 CLOSED** (non-DB surfaces routed); Phase-3 F7, Phase-4 R1/R2, Phase-6 F-7 statuses updated. |
| 1.9 | 2026-06-11 | Engineering | Phase 6.5 exit-gate review r1 = PASS-WITH-FIXES (no S1/S2); R1–R4 logged + all remediated (R1 NFKC Unicode-digit SSRF fold; R2 fd-close; R3 blank-CORS fallback; R4 doc); 242 tests; ITM-010 closure note extended. |
| 1.10 | 2026-06-12 | Engineering | Round C1 exit-gate review r1 = PASS-WITH-FIXES (no S1/S2); C1-R1-F1 (storage delete-failure now logs a warning) + C1-R1-F2 (load TOCTOU → try/except) remediated; 262 tests. |
| 1.11 | 2026-06-12 | Engineering | Phase 7 build: **T-18 CLOSED** (`/v1` prefix, B5); **ITM-018 added** (23ai vector track deferred, ADR-016); packs need real-EBS validation → still ITM-012. |
| 1.12 | 2026-06-12 | Engineering | ITM-012 extended to cover EBS packs + **validation method defined**: self-audit done (`reviews/ebs-pack-self-audit.md`) + automated live validator (`scripts/ebs_pack_validate.py`, offline-tested); close criteria = run vs a real EBS 12.2, remediate, record evidence. |
| 1.13 | 2026-06-12 | Engineering | Phase 7 exit-gate review r1 = PASS (no blocking); P7-R1-F1 (`ebs_modules` unknown→422) + P7-R1-F2 (`/v1` POST auth tests) remediated; 293 tests. |
| 1.3 | 2026-06-10 | Engineering | Phase 4: ITM-011 (list/multi-value binds deferred) + ITM-012 (templates not live-EBS validated) logged. |
