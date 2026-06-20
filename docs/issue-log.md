# D12 — Issue / Bug Log

> **Document:** Issue Log · **Version:** 1.26 · **Status:** Living · **Owner:** Engineering · **Last updated:** 2026-06-18 (**🎉 PHASE 10 CLOSED** — exit-gate r1 = PASS-WITH-FIXES [reviewer ≠ author]; all 5 invariants hold; 4 S4 (F1–F4) remediated; gates `tsc --build`/vitest **160**/vite/pytest 446; **live XE end-to-end confirmed** [run → live fan-out → download → real email]. Open backlog: ITM-026, ITM-031. Prior: **BUG-013 FIXED**; **ITM-034 CLOSED**; **PHASE 9 CLOSED**)

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
| BUG-006 | `Dockerfile.api.local` and `Dockerfile.local` excluded from git tracking by the `*.local` glob in `.gitignore` (a Vite-generated catch-all pattern) | S3 | Anyone cloning the repo had no Dockerfiles — `docker compose up` would fail immediately; deploy artifacts silently missing since repo init | **Fixed** — added negation exceptions `!Dockerfile.local` + `!Dockerfile.*.local` to `.gitignore`; both files committed for the first time in `f353ebc` (2026-06-12 deployment hardening). |

| BUG-007 | NL→SQL emitted non-Oracle SQL — a trailing `;` (and `LIMIT` for top-N), both rejected by Oracle as **ORA-00933** at execution (surfaced in the v2 Phase-8 UI demo) | S3 | NL→SQL unusable for top-N and for any query the model terminated with `;`; the generic sanitized error gave no hint | **Fixed** — `_parse_sql_and_explanation` strips a trailing statement terminator (`re.sub(r"[;\s]+\Z", "", sql)`); `SYSTEM_PROMPT` now mandates `FETCH FIRST n ROWS ONLY`/`ROWNUM` (never `LIMIT`) and no trailing semicolon. 7 tests (`tests/test_nl2sql_sql_cleanup.py`); SELECT-only chokepoint untouched. Pre-existing (shared with v1). |
| BUG-008 | A saved profile's `current_schema` was silently dropped at execution: `_resolve_target` + `test_profile` built `OracleConnectionConfig` without it, so `db.py`'s `ALTER SESSION SET CURRENT_SCHEMA` never ran. Surfaced in the Phase-9 Inc-3 live e2e — the AI's natural **unqualified** SQL (`FROM EMPLOYEES`) hit **ORA-00942** while schema-qualified SQL worked. | S3 | The AI's own proposed SQL wouldn't run without manual schema-qualification, undercutting propose→approve→run; ADR-018's per-profile default schema was inert on the API path (only the Streamlit path applied it). | **Fixed** — pass `current_schema=resolved.current_schema` into the `OracleConnectionConfig` in both `_resolve_target` (profile branch) and `test_profile`; value still validated by `validate_schema_name`; SELECT-only chokepoint untouched. Regression: `tests/test_execute_endpoint.py::test_execute_via_profile_applies_current_schema` (+ `_without_schema_passes_none`); 427 tests. Verified live vs XE: unqualified `SELECT COUNT(*) FROM EMPLOYEES` 200, and the full ask→run happy-path now succeeds on the model's unqualified SQL. |
| BUG-009 | A failed report run showed the backend's operator-facing sanitized message **"Database error — see server logs."** to the end user (found in owner testing of the Phase-9 B6 Reports screen). | S3 | Developer-facing copy leaked to a CXO user; not actionable and not on-brand. | **Fixed** ([ADR-024](adr/ADR-024-user-readable-error-presentation.md)) — `_db_error` detail is now friendly + support-oriented (full driver detail still logged server-side; `error_id` unchanged), and a single frontend policy (`friendlyError`/`errorMessage` in `web/src/lib/api/client.ts`) passes safe server messages through with the reference id while substituting a generic "contact IT support" message only for network/bodyless failures. 3 backend assertions updated; `web/src/lib/api/errorMessage.test.ts` added. Verified live (friendly copy + ref shown). |
| BUG-010 | An off-topic prompt (e.g. **"how to swim"**) still generated a `SELECT` and ran it (immediately under Auto-run) — NL→SQL had no relevance gate, only the SELECT-only safety check (found in owner testing of the Ask flow). | S3 | Irrelevant questions returned bogus results instead of a clear "not a data question" notice; wasted live runs. | **Fixed** ([ADR-025](adr/ADR-025-off-topic-nl-guard.md)) — conservative off-topic guard: the model emits a `CANNOT_ANSWER:` sentinel for non-data questions; the generator returns `NLSQLResult(answerable=False, message=…)` (only when no SQL fence — prefer SQL if both); `POST /nl2sql` returns `answerable`+`message` (additive); the Ask page shows a calm notice and proposes/runs nothing (incl. Auto-run). Chokepoint unchanged. 2 backend + 1 frontend test added. Verified live (Groq): "how to swim" declined, real questions still answered. |
| BUG-011 | A data-*shaped* question needing a column the schema lacks — **"what is count of woman"** with no gender column — produced a **fabricated proxy** (`WHERE SUBSTR(EMAIL, LENGTH(EMAIL)-1, 1) = 'a'`) and ran it (found in owner testing). | S3 | Returned a confident but meaningless answer to a question the data can't support. | **Fixed** ([ADR-025](adr/ADR-025-off-topic-nl-guard.md), guard strengthened) — `SYSTEM_PROMPT` now forbids inventing columns / fabricating a proxy and declines (`CANNOT_ANSWER`) when answering needs information the schema doesn't contain. Prompt-content test added. Verified live: "count of women" → declined ("no column … to determine gender"); "count of employees"/"headcount by department"/"average salary" still answered. |
| BUG-012 | **Inconsistent** decline: the same off-topic/unanswerable prompt (e.g. "what is count of woman") sometimes showed the calm notice and sometimes the technical **"Generated SQL is not a SELECT/CTE. Aborting for safety." + reference id** (model nondeterminism — it declined in prose / a non-SELECT shape without the sentinel, which fell through to the safety error). Found in owner testing under Auto-run. | S3 | Inconsistent, developer-facing error for what should be one calm "can't answer" notice. | **Fixed** ([ADR-025](adr/ADR-025-off-topic-nl-guard.md)) — the generator now resolves **all** non-usable generations (sentinel / prose / non-SELECT / unparseable) to the same `answerable=False` notice, logs the rejected output server-side (`ask_oracle` logger), and **never** raises the technical "not a SELECT" error to the user. SELECT-only `/execute` chokepoint unchanged (the hard boundary). Streamlit shows the notice too. Tests updated (non-SELECT now declines gracefully). Verified live: 6/6 clean declines. |
| BUG-013 | The frontend **typecheck gate** `tsc --noEmit -p tsconfig.json` is a **no-op**: the root `tsconfig.json` has `"files": []` + project `references`, so without `--build` it type-checks **zero** files. Proven by a deliberate `const x: number = "string"` passing it while `tsc --build` caught it. Found in Phase-10 B4 after the no-op gate let a **missing required JSX prop** (`reportRows` on the top-level `<ResultScope>`) reach runtime (the cascade download threw `undefined.length`). | S3 | "tsc clean" was meaningless across Phase 9 — real type errors + missing props went uncaught; surfaced one pre-existing error (`web/src/lib/derive/sql.test.ts:98`, unused `@ts-expect-error`). | **Fixed** (owner-approved) — adopt **`tsc --build`** as the real typecheck gate; fixed the pre-existing `sql.test.ts:98`; added `*.tsbuildinfo` to `.gitignore`; updated the gate command in HANDOFF + the Phase-10 charter; added a component regression test (`ResultsView.cascade.test.tsx`) that fails if the cascade download props are unwired. `tsc --build` now exit 0. |

## Open items (non-defect, tracked)

- ITM-005: Streamlit UI not browser-verified — see [RISK-04](risk-register.md).
- ITM-006: Migrate legacy `connection.json` (plaintext) to encrypted profiles — see [RISK-09](risk-register.md). **(Phase 4 r1, F5 — FIXED 2026-06-10):** the plaintext-password-at-rest is resolved — `save_connection_config` now **strips the password** before writing, so it is never persisted (session-only); profiles remain the encrypted path (`test_storage.py`). The broader migration of the manual single-connection path onto encrypted profiles (removing `connection.json` entirely) remains open under this item. **✅ CLOSED — Round C1 / B2:** the `connection.json` **write** path is removed (`save_connection_config` deleted; the manual "Save" button retired); `storage.migrate_legacy_connection()` imports any existing file once (session-only) and **deletes it** at startup (also removing a pre-F5 plaintext file). Encrypted profiles are the single persistence path. Validated by `tests/test_storage.py`.
- ITM-007: `use_container_width` is deprecated in Streamlit (removal scheduled post-2025-12-31); migrate `st.button`/`st.dataframe`/`st.download_button` calls to `width='stretch'`. Severity S4 (warning only; app functions). **✅ CLOSED — Round C1 / B1:** all 14 call sites in `src/app.py` migrated to `width="stretch"` (verified on `streamlit==1.58.0`); smoke green.
- ITM-008: (deferred from F3) optional NL-question PII scrubbing before external send. Current mitigation: question text is sent by design; tenants set `LLM_POLICY=external_disabled`. Rationale: the question is the user's own intent; scrubbing risks degrading legitimate queries. Revisit with the redaction/policy work. **✅ CLOSED — Round C1 / B3 (charter D-C):** built behind a **default-off `SCRUB_PII`** env flag — when on, the NL question is masked (email/SSN/card/phone → typed placeholders) **on the external path only** (local stays verbatim) via `src/core/llm/pii.py`, complementing the schema-name redaction. Patterns kept conservative precisely because over-masking can degrade queries (hence opt-in). Validated by `tests/test_pii.py`.
- ITM-009: pre-existing CORS `allow_origins=["*"]` + `allow_credentials=True` + `0.0.0.0` bind (`src/api.py`) — harden (specific origins, auth) before any multi-tenant deployment. Flagged by Phase-3 reviewer §5; out of Phase-3 scope. **r2: deferral confirmed acceptable** (pre-existing, inert for single-session posture) — hard precondition for any networked/multi-tenant deployment ([RISK-12](risk-register.md)). **✅ CLOSED — Phase 6.5 / B1 ([ADR-013](adr/ADR-013-network-edge-hardening.md)):** opt-in `X-API-Key` auth (`APP_API_KEY`; `/health` exempt for liveness, `/metrics` gated) + explicit env-driven CORS (`ALLOWED_ORIGINS`, localhost default; a literal `*` forfeits credentials, so the flagged combination is unrepresentable). The `0.0.0.0` bind is a deployment choice — the network-exposure rule lives in [D7 §2](07-deployment-plan.md). Validated by `tests/test_auth.py`.
- ITM-010: (F7, from r2) `validate_base_url` (`src/core/llm/providers.py`) only checks canonical IP literals via `ipaddress.ip_address`, so integer/hex/octal encodings of loopback (`2130706433`, `0x7f000001`, `017700000001` = 127.0.0.1) are treated as hostnames and allowed. Severity **S4** — **not exploitable on the tested stack** (`getaddrinfo` does not resolve those forms → fails closed at the network layer); platform/resolver-dependent. Fix: reject bare-integer/`0x…` hosts or normalize via `getaddrinfo` + re-apply the private/loopback check. Tracked under [RISK-11](risk-register.md) residual. **✅ CLOSED — Phase 6.5 / B2:** `_numeric_host_to_ipv4` decodes `inet_aton`-style numeric hosts (decimal/hex/octal, 1–4 dot-groups; ASCII-strict) **before** the private/loopback checks, independent of platform resolver behaviour; an all-numeric host that is not a valid IPv4 is rejected **fail-closed**. Validated by the encoding matrix in `tests/test_llm_providers.py`. **Phase-6.5 review r1/R1 hardening:** the host is **NFKC-folded** before the checks, so Unicode compatibility digit forms (e.g. fullwidth `１２７.0.0.1`) collapse to ASCII and are caught too (a genuine internationalized hostname still survives as a hostname). DNS-rebinding remains the separately documented RISK-11 residual.
- ITM-011: (Phase 4, charter D-B) **list / multi-value bind parameters deferred.** v1 supports scalar binds only (string/number/date); `IN (:list)` expansion needs a safe design (e.g. generating `:p0,:p1,…` binds, not interpolation). Severity S4 (feature gap). Revisit when a report needs multi-value filters. **✅ CLOSED — 2026-06-12:** `expand_list_binds(sql, binds)` in `src/db.py` rewrites each list-valued bind `:name` → `:name_0, :name_1, …` via regex (no string interpolation; expanded names are bind placeholders, not values). `validate_binds` now accepts non-empty flat lists of scalars and rejects empty lists (Oracle `IN ()` is invalid), nested lists, and non-scalar items. Safety check runs on the **original** SQL before expansion (invariant preserved). `ParamType` in `src/core/reports.py` gains `"list"`; `_coerce_value` parses comma-separated strings into lists. 14 new tests in `tests/test_bind_safety.py` (307 total). The SELECT/CTE-only chokepoint and `assert_no_values` redaction tripwire are unaffected.
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

- ITM-019: (Deployment GA-readiness hardening — S3/ops) **Render free-tier filesystems are
  ephemeral** — any data written to `STORAGE_DIR` (profiles, reports, schemas) is lost on service
  redeploy or restart. **✅ RESOLVED — 2026-06-12:** decision = **Render Disk** (no code change;
  the existing JSON+atomic-write stores are production-quality per ADR-014; SQLite still needs a
  disk; PostgreSQL adds an external DB dependency that conflicts with the product identity).
  `render.yaml` now includes commented `disk:` blocks for both services (uncomment + upgrade plan
  to `starter` to activate); D7 §5 "Render persistent storage" documents the setup steps, disk
  independence between services, and rollback guidance. Free-tier pilots remain ephemeral by
  design — acknowledged, documented, not a defect. **Close criteria met.**

- ITM-020: (Phase 8 / v2, charter D-A/D-B — S4/feature) **Gmail API (OAuth2) + per-user sender
  deferred.** v2 Phase 8 ships email via **SMTP + App Password, single shared mailbox**
  ([ADR-017](adr/ADR-017-email-report-via-gmail-smtp.md)) — the fastest path to a real,
  demoable send with no Google verification gate. The "integrated" Gmail API path (OAuth consent,
  the `gmail.send` sensitive scope, app-verification for external/commercial release) and a
  **per-user sender** (each decision-maker sends as their own Gmail) are deferred to a future
  increment; both pair with the multi-tenant identity layer ([RISK-07](risk-register.md)).
  Non-blocking — the SMTP path is fully functional and tested.

- ITM-021: (Phase 8 / v2 — S4/feature) **AI-drafted email body deferred.** An optional
  LLM-drafted summary/recommendation in the email body was deliberately left **OUT** of Phase 8
  because it would send **row data to the external LLM**, brushing the "schema-names-only"
  redaction line. The MVP body is user-typed only and **no LLM is called on the email path**. If
  added later it must be behind an **explicit opt-in** and either summarize locally or be recorded
  as a sanctioned exception ([ADR-017](adr/ADR-017-email-report-via-gmail-smtp.md)). Non-blocking.

- ITM-022: (v2 Phase-8 UI demo — S4/UX) **Query Builder requires scrolling to run a query.** In
  `draw_query_builder` (NL mode, `src/app.py`), the Generate/Run controls and the results sit far
  apart, forcing the user to scroll to run and again to see output. **✅ CLOSED:** removed the
  `col1`/`col2` split — "Generate SQL" is now a standalone button above the SQL editor; "Run SQL"
  (`type="primary"`) moved to below the SQL text area and explanation, directly above results. No
  logic change; 401 tests pass.

- ITM-023: (v2 Phase-8 UI demo — S4/UX) **Email form not cleared after a successful send.** After
  "Send email" succeeds in `_render_email_action` (`src/app.py`), the To/Cc/Subject/Body values
  persist in `st.session_state`, so the recipient stays filled. **✅ CLOSED:** on `result.ok`,
  `email_to`/`email_cc`/`email_subject`/`email_body` are popped from `st.session_state`; on the
  next render the fields reset to their defaults (blank To/Cc, date-stamped Subject, default Body).
  401 tests pass.

- ITM-024: (v2 UX review 2026-06-14 — S3/UX) **Every screen required vertical page scroll.** All
  seven pages in `src/app.py` stacked controls + content vertically, so any non-trivial interaction
  (e.g. typing a question, generating SQL, viewing results, browsing a template) required scrolling.
  The sidebar also spilled into scroll when the manual-connection form was open.
  **✅ CLOSED:** Full two-panel layout (`st.columns([1, 2])` or `[1, 1]`) applied to every screen:
  controls/inputs in the left panel, content/results in the right panel. Key changes:
  (a) **Query Builder** — NL prompt/EBS-mods/Generate in left; SQL editor + Run SQL (primary) +
  Results/Explanation tabs in right; results at `height=220` (no page push).
  (b) **Connections** — add-profile form left, saved-profiles table + test/delete right.
  (c) **Schema Sources** — Upload/Introspect/Library tabs left, active-schema table browser right.
  (d) **Data Dictionary** — Search/EBS-packs tabs + export buttons left, table detail + FK refs right.
  (e) **Reports** — saved-report selector left, Run/Save-new tabs right.
  (f) **Templates** — module + radio list left, SQL preview + Load/Save right.
  (g) **Settings** — LLM form left, active-config + email/safety status right.
  (h) **Email action** migrated from inline `st.expander` to `@st.dialog` — opens as a modal
  overlay so it never adds page height.
  (i) **Sidebar** — manual-entry form wrapped in `st.expander(expanded=False)`; sidebar never
  scrolls in the default (profile-selected) state.
  `_run_and_display` refactored into `_execute_query` (stores to `session_state`) +
  `_render_results` (renders in calling context); `_render_email_action` removed (superseded by
  `@st.dialog`). 401 tests pass (no logic change).

- ITM-025: (Phase 9 — backend gap) **Email not exposed via the API.** The Phase-8 mailer lived only
  in the Streamlit app (`src/core/mailer/`); the React surface had no way to send. **✅ CLOSED (B2):**
  `POST /reports/email` (root + `/v1`, auth-gated) reuses `send_report_email` unchanged — no LLM,
  no re-query, opt-in 503; SendResult→HTTP mapping; `tests/test_email_api.py`. A pre-build row/column
  cap (100k×1k → 400) was added on review. 414 tests pass.

- ITM-026: (Phase 9 — Ask landing UX, OPEN/enhancement) **Make the example-question chips dynamic.**
  The three chips under the Ask box are currently static placeholders; per owner request (2026-06-14)
  they should reflect the user's **recent / most-run questions** instead. Blocked on query-history
  persistence (not yet built). Deferred to a later increment; wire the chips to history once it exists.

- ITM-027: (Phase 9 — Inc 3 Packet 3a internal review, ✅ **FIXED** 2026-06-14 / robustness, Low) **`/profiles` Zod parse is
  strict on `environment`.** `ProfilePublicSchema.environment` is `z.enum(["DEV","TEST","PROD"])`; any
  unexpected value (or other schema drift) fails the whole list parse and drops the connection picker to
  the E10 zero-state instead of degrading gracefully. Values come from our own `Literal` so drift is
  unlikely. Fix-when-it-fits: wrap the env field (or the list parse) in `.catch()` for graceful
  degradation. Owner-approved deferral (2026-06-14). File: `web/src/lib/api/schemas.ts`.

- ITM-028: (Phase 9 — Inc 3 Packet 3a internal review, ✅ **FIXED** 2026-06-14 / config, Low) **`ADMIN_URL` defaults to a
  hardcoded `http://localhost:8501` in the bundle.** It is env-overridable (`VITE_AOR_ADMIN_URL`) and a
  beta-only affordance for the E10 "add a connection in admin" link, so acceptable now. Fix-when-it-fits:
  source the admin URL from server/runtime config (or hide the link when unconfigured) before GA.
  Owner-approved deferral (2026-06-14). File: `web/src/lib/config.ts`.

- ITM-029: (Phase 9 — Inc 3 Packet 3a internal review, ✅ **FIXED** 2026-06-14 / a11y, Nit) **Connection-picker listbox lacks
  roving arrow-key navigation.** Options are focusable buttons (Tab/Enter/Escape + outside-click all
  work), but there is no ↑/↓ roving-tabindex pattern within the `listbox`. Functional for beta.
  Fix-when-it-fits: add arrow-key navigation (or adopt the shadcn/Radix `Select` if its jsdom friction is
  resolved). Owner-approved deferral (2026-06-14). Files: `web/src/app/ConnectionPicker.tsx`,
  `web/src/features/ask/SchemaPicker.tsx` (same pattern).

- ITM-030: (Phase 9 — Inc 3 Packet 3b internal review, ✅ **FIXED** 2026-06-14 / UX, Low/cosmetic) **Schema picker shows the
  E11 "no schema selected" notice on a transient `/schemas` list-fetch error even when a valid `schemaId`
  is remembered.** The remembered id is still in session and is sent to `nl2sql` (so SQL accuracy is
  unaffected — the id is valid), but the name can't be resolved without the list, so the calm E11 notice
  appears. Error edge only; non-blocking. Fix-when-it-fits: resolve the active name via a `/schemas/{id}`
  fallback, or suppress E11 when `schemaId` is set-but-unresolved. (The same strict-enum parse class as
  ITM-027 also applies to `SchemaSummarySchema.source` — covered by ITM-027's remedy.) Owner-approved
  deferral (2026-06-14). File: `web/src/features/ask/SchemaPicker.tsx`.

- **F3** (Phase 9 — B5b-3 Inc 1 internal review, Low → **RESOLVED in Inc 4 / Packet 4c**, 2026-06-14):
  a **date-dimension cascade level** rendered a non-clickable Recharts trend line and, because the chart
  was non-null, the "Pull live detail" leaf never appeared — so a trailing/standalone date dimension had
  **no path to detail**. **Fixed:** `ResultsView` now renders a compact **Pull-live-detail** affordance
  beside any trend line (pulls the current drill scope via the Decision-3 wrap), and passes the leaf
  context at the top level too (`NoBreakdown` stays drilled-only). 3 RTL tests
  (`web/src/components/exec/ResultsView.f3.test.tsx`); verified live with a crafted date-aliased query.

- ITM-025: **confirmed CLOSED** (B2 — `POST /reports/email`); re-verified at the Phase-9 B5b exit gate.

- ITM-031: (Phase 9 — B5b exit-gate complete product test, OPEN/lint-debt, Low) **Frontend ESLint shows
  21 findings** (`eslint web/src`): 8 `react-refresh/only-export-components` warnings + 2
  `no-empty-object-type` errors are all in **vendored shadcn `components/ui/*`** primitives; the 11
  `no-explicit-any` errors are in pre-existing `lib/api/client.ts` + `components/exec/DriverChart.tsx`
  and in test-mock signatures (`({...}: any)`) that follow the repo's established cascade-test pattern.
  **ESLint is not a configured CI gate** (the gates are pytest/vitest/tsc/vite build — all green), and
  none of the findings are in new production logic. Fix-when-it-fits: type the test mocks + `client.ts`
  helpers, and either relocate shared exports or accept the vendored-primitive warnings (or scope ESLint
  to exclude `components/ui`). Logged at the B5b close (2026-06-14).

- ITM-032: (Phase 9 — B5b exit-gate review r1 / P9B-R1-F2, ✅ **FIXED** 2026-06-14 / robustness, Low) **Pull-detail wrap can be
  ambiguous on a duplicate or unaliased output column.** `buildPullDetailSql` wraps as
  `SELECT * FROM (<approved>) WHERE "COL" = :p`; if the approved `SELECT` has two output columns with the
  same name (or a colliding unaliased expression), the inline view raises **ORA-00918/-00960**. **Not a
  security issue** — stays a bound SELECT, chokepoint-revalidated, surfaces as a sanitized E9 the user can
  edit. Pre-noted in the 4a internal review. Fix-when-it-fits: alias-dedupe the wrapped projection or
  detect collisions client-side. File: `web/src/lib/derive/pullDetail.ts`.

- ITM-034: (Phase 9 — B7 acceptance, **CLOSED 2026-06-15**, S4) **"Introspect" was mild jargon.** The Data
  Dictionary action/dialog said "Introspect schema"; charter bar B-4 suggested plainer wording (e.g.
  "Read from the database"). Logged at the B7 acceptance pass
  ([reviews/phase-9-b7-acceptance.md](reviews/phase-9-b7-acceptance.md)). **Resolution (owner-approved
  wording "Read from database"):** all user-facing strings reworded in `IntrospectDialog.tsx` (trigger
  "Read from database", title "Read a schema from the database", submit "Read & save"/"Reading…",
  placeholder "… (from database)") and `DataDictionaryPage.tsx` (empty-rail / delete-note / empty-state
  + a display-only `sourceLabel()` mapping the `source` badge "introspection"→"From database",
  "upload"→"Uploaded"). The code/API contract is **unchanged** — component name `IntrospectDialog`,
  `introspectSchema`, `POST /schemas/introspect`, and the stored `source` enum all stay (display-only
  mapping). Button-label tests updated. Gates green (pytest 433 / vitest 130 / tsc clean / vite build);
  live-verified vs XE `AOR_DEMO` (no "introspect" text remains user-visible). Owner signed off 2026-06-15.

## Phase 9 (v2) — B5b-3 exit-gate review & remediation (r1)

Source: [reviews/phase-9-b5b-review-r1.md](reviews/phase-9-b5b-review-r1.md) — **independent** reviewer
(reviewer ≠ author, ADR-006; owner chose a spawned reviewer). Verdict **PASS** (no S1/S2 blocking). The
reviewer independently re-ran all four gates (**427 backend / 69 frontend / tsc clean / vite build green**,
all matching) and adversarially verified all 5 invariants HOLD (SELECT-only chokepoint incl. the
pull-detail wrap; AI-proposes/approve + auto-run read-only-safe & default-off; schema-names-only/no rows to
LLM; no client DB secrets; sanitized `error_id`). BUG-008 + the pull wrap confirmed injection-safe; docs
accurate. Six non-blocking findings:

| ID | Sev | Finding | Disposition |
|----|-----|---------|-------------|
| P9B-R1-F1 | S3 | `vitest run` gate brittle on the junction/spaced path (Vite `%20` canonicalization) | **Fixed** — `preserveSymlinks: true` added to `vitest.config.ts` (mirrors `vite.config.ts`) |
| P9B-R1-F2 | S4 | Pull-detail wrap ambiguous on duplicate/unaliased output column (not security) | **Fixed** (ITM-032) — `ResultsView` withholds the live pull when `result.columns` has duplicates (`schemas`/RTL: `ResultsView.f3.test.tsx`) |
| P9B-R1-F3 | S4 | Strict Zod enums fail whole-list parse on drift | **Fixed** (ITM-027) — `Environment`/`SchemaSource` use `.catch(default)` (`schemas.test.ts`) |
| P9B-R1-F4 | S4 | `ADMIN_URL` hardcoded default in bundle | **Fixed** (ITM-028) — default only in `import.meta.env.DEV`, else empty + the affordance renders text not a link |
| P9B-R1-F5 | S4 | Listbox dropdowns lack arrow-key roving nav | **Fixed** (ITM-029) — `useListboxNav` (Arrow/Home/End + focus-on-open) on both pickers (`ConnectionPicker.test.tsx`) |
| P9B-R1-F6 | S4 | Cosmetic `confidence: undefined` vs `null` in AskPage review entries | **Fixed** — `editSql` now uses `null` |

**Post-review remediation (all six findings closed, 2026-06-14):** all findings above are now fixed
(F1/F6 at review close; F2–F5 immediately after, owner-directed). Also fixed **ITM-030** (schema E11
suppressed on a transient `/schemas` error when a `schemaId` is remembered). Gates after remediation:
**427 backend / 74 frontend / tsc clean / vite build green.** Remaining open ITMs: **ITM-026** (dynamic
example chips — needs query history) and **ITM-031** (frontend ESLint debt — not a CI gate).

## Phase 8 (v2) — independent review findings & remediation (r1)

Source: [reviews/phase-8-review-r1.md](reviews/phase-8-review-r1.md) — verdict **PASS-WITH-FIXES** (no S1/S2; all 8 security invariants hold). Package: [reviews/phase-8-review-package.md](reviews/phase-8-review-package.md). Remediated post-review; **371 tests green**.

| ID | Sev | Finding | Disposition |
|----|-----|---------|-------------|
| P8-R1-F1 | S3 | Attachment size cap measured **raw** bytes; default 20 MB → ~26.7 MB base64 > Gmail's 25 MB (user got the generic transport error instead of a clean pre-send rejection) | **Fixed** — `DEFAULT_MAX_ATTACHMENT_MB` 20→**17** (raw, with base64 headroom); `.env.example` / runtime `.env` / `render.yaml` / ADR-017 / design updated |
| P8-R1-F2 | S3 | `validate_address` control-char guard was only `[\r\n\t\x00]`; other C0 / DEL chars passed both guards | **Fixed** — `_CONTROL_RE` widened to `[\x00-\x1f\x7f]`; 5 regression cases (embedded control char rejected). *(Not header injection — CR/LF required — but closes the "illegal char → rejected" contract.)* |
| P8-R1-F3 | S4 | Spec said subjects are "rejected" for control chars; code **collapses** them to spaces (safe, but not the stated behaviour) | **Fixed (doc)** — design §6 now states: addresses are rejected, subject control chars are collapsed (a stray tab shouldn't fail a send) |
| P8-R1-F4 | S4 | Operator-set `EMAIL_FROM` From header was unvalidated (operator-trust boundary; hardening only) | **Fixed** — From is control-stripped in `build_message`; regression test |

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
| 1.14 | 2026-06-12 | Engineering | Deployment GA-readiness hardening: **BUG-006 logged + FIXED** (Dockerfiles untracked since init due to `*.local` gitignore; added negation exceptions, first-committed in `f353ebc`); **ITM-019 added** (Render ephemeral storage / no persistence across redeployments — deployment architecture decision for owner). |
| 1.15 | 2026-06-12 | Engineering | **ITM-019 RESOLVED** — Render Disk selected (no code change); `render.yaml` disk blocks added; D7 §5 runbook written. |
| 1.3 | 2026-06-10 | Engineering | Phase 4: ITM-011 (list/multi-value binds deferred) + ITM-012 (templates not live-EBS validated) logged. |
| 1.16 | 2026-06-15 | Engineering | Phase 9 **B6 complete** (Connections/Dictionary/Reports/Settings screens): **BUG-009** logged + FIXED (error-readability, ADR-024); report parameter value-pickers shipped (ADR-023). ITM-026 + ITM-031 remain open. |
| 1.21 | 2026-06-15 | Engineering | Phase 9 **B7 + post-B7 fixes** (BUG-010/011/012, ADR-025) FIXED; **owner CXO sign-off** + **independent exit-gate r1 = PASS-WITH-FIXES** (reviewer ≠ author; gates 433/130; all 5 invariants hold). 5 S4 findings (F-1 stale counts, F-2 multi-bind IN, F-3 stale comment, F-4 latent effect, F-5 model-compliance) remediated/accepted. **PHASE 9 CLOSED.** Open: ITM-026/031/034. |
| 1.22 | 2026-06-15 | Engineering | **ITM-034 CLOSED** — "Introspect" reworded to owner-approved "Read from database" across the Data dictionary (display-only; code/API/`source` enum unchanged); button-label tests updated; gates green (433/130/tsc/vite); live-verified vs XE. Open backlog now: ITM-026, ITM-031. |
| 1.23 | 2026-06-15 | Engineering | **BUG-013 FIXED** — the frontend typecheck gate `tsc --noEmit -p tsconfig.json` was a **no-op** (root `tsconfig.json` `files:[]` + references → checks 0 files); adopted **`tsc --build`** as the real gate (owner-approved), fixed the pre-existing `sql.test.ts:98`, git-ignored `*.tsbuildinfo`, updated HANDOFF + Phase-10 charter; `tsc --build` exit 0. Surfaced during Phase-10 B4. |
