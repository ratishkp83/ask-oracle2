# D11 — Task Tracker

> **Document:** Task Tracker · **Version:** 1.49 · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-13

Status: Planned · In Progress · Blocked · Completed.

## Delivered (Phase 2)

| ID | Task | Status |
|----|------|--------|
| T-01 | Central layered SQL safety engine | ✅ Completed |
| T-02 | Connection profiles + Fernet encryption | ✅ Completed |
| T-03 | `/execute` + `/profiles` API (chokepoint) | ✅ Completed |
| T-04 | Streamlit Connections + Settings UI | ✅ Completed (⚠️ not browser-verified — T-13) |
| T-05 | Per-user LLM config (`LLMConfig`) | ✅ Completed |
| T-06 | Secret removal from files | ✅ Completed |
| T-08 | Techspec 5 edits | ✅ Completed |

## P2.5 — Governance Baseline & Phase-2 Closure (current)

| ID | Task | Status | Depends / Notes |
|----|------|--------|-----------------|
| T-10 | `git init` + baseline commit (`.env` ignored) | ✅ Completed | commit `5c21f13`; local identity placeholder; **user pushes to GitHub** |
| T-09 | Promote governed `/docs` set into repo | ✅ Completed | 22 docs tracked |
| T-14 | Record ADR-001…005 | ✅ Completed | `docs/adr/` |
| T-15 | Seed CHANGELOG + registers + trackers | ✅ Completed | — |
| T-16 | Add CI workflow (pytest) | ✅ Completed | `.github/workflows/ci.yml`; first run executes on push |
| T-13 | Phase-2 UI smoke test | ✅ Completed | automated via `test_app_smoke.py` (3 tests); **found + fixed BUG-005** |
| T-07 | Rotate leaked Groq/OpenAI keys | ✅ Completed | user-confirmed 2026-06-10 (RISK-01 Closed) |
| T-17 | Phase-2 closure sign-off | ✅ Completed | **gate PASSED 2026-06-10**: secrets rotated, 51 tests green, docs current, ADRs ratified, tree clean |

## Phase 3 — NL→SQL 2.0 & LLM Abstraction (✅ CLOSED — exit gate passed 2026-06-10)

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P3-1 | LLM provider abstraction (`src/core/llm/`) | ✅ Completed | External (Groq/OpenAI) + Local stub |
| P3-2 | Strict redaction + tripwire | ✅ Completed | external prompts = schema names only |
| P3-3 | `LLM_POLICY` toggle | ✅ Completed | local_only / local_external / external_disabled |
| P3-4 | Heuristic confidence | ✅ Completed | High/Med/Low + reasons |
| P3-5 | `/nl2sql` → SQL+explanation+confidence; UI display | ✅ Completed | D5/D4/D3 updated |
| P3-6 | Tests (20 new; **65 total** green) | ✅ Completed | mocked provider, no network |
| R3.1 | Independent adversarial review + QA (r1) | ✅ Done | verdict **FAIL** — 2 blocking (F1,F2) + 4 non-blocking; [phase-3-review-r1.md](reviews/phase-3-review-r1.md) |
| R3.2 | Remediate findings F1–F6 + regression tests | ✅ Done | F1/F2/F4/F5/F6 fixed; F3 wording fixed, scrubbing deferred (ITM-008); **75 tests green** |
| R3.3 | Re-review (r2) on the fixes + regression | ✅ Done | verdict **PASS-WITH-FIXES — no open blocking** ([phase-3-review-r2.md](reviews/phase-3-review-r2.md)); range `b77b571..HEAD` (`29d956b`); all r1 probes independently re-run; new S4 F7→ITM-010; deferrals ITM-008/009 confirmed acceptable |
| P3-7 | Phase-3 closure sign-off | ✅ Completed | **gate PASSED 2026-06-10**: r2 = PASS-WITH-FIXES (no open blocking), 75 tests green, governed docs current, F1–F6 remediated + re-validated, S3/S4 fixed-or-deferred |

## Phase 4 — Reports, Templates & UX (✅ CLOSED — exit gate passed 2026-06-10)

Charter: [phase-4-charter.md](charters/phase-4-charter.md). **Gate PASSED**: independent
review **r1 = PASS-WITH-FIXES** (no S1/S2); S3 F2/F3/F4/F5 fixed, F1 remediated (read-only
account precondition documented — [ADR-009](adr/ADR-009-readonly-db-account-precondition.md)),
F6 + R1/R2 deferred/backlogged with rationale; **130 tests green**.

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P4-0 | Open Phase 4 Discovery charter | ✅ Completed | objectives/scope/risks/success criteria + open decisions D-A…D-I |
| P4-D | Owner approval + decision resolution (D-A…D-I) | ✅ Completed | resolved 2026-06-10: keep JSON store; scalar binds; curated EBS SQL; ~10–15 templates across 5 modules; sidebar nav; **core + /reports API**; bind-through-execute; nullable profile binding |
| P4-DES | Design + build sequence (approved) | ✅ Completed | `docs/reports-templates-ux-design.md` (`78f1ad3`); owner approved → build |
| P4-1 | `src/core/reports.py` — Report v2 model + store + legacy migration | ✅ Completed | `43e603d`; 13 tests |
| P4-2 | Bind-parameter plumbing through `run_select`/`/execute` (ADR-007) | ✅ Completed | `e53fc51`; **chokepoint** `validate_binds` + 11 bind-safety tests |
| P4-3 | EBS template catalog (GL/AP/AR/PO/OM, 13 templates) | ✅ Completed | `50eea97`; every template proven a safe SELECT |
| P4-4 | Left-nav UX rework + Reports/Templates sections | ✅ Completed | `dc2daed`; 7-section smoke green |
| P4-5 | `/reports` CRUD + `/reports/{id}/run` API (ADR-008) | ✅ Completed | `50eea97`; shares `_run_sql` chokepoint |
| P4-6 | Tests (CRUD, **bind-safety**, migration, template shape, execute-with-binds, UI smoke) | ✅ Completed | +43 → **118 green** |
| P4-7 | Governed-doc updates (D3/D4/D5/D6, BRD, ADR-007/008, CHANGELOG, traceability, registers) | ✅ Completed | code + docs in lockstep |
| R4.1–.7 | Phase-4 independent adversarial review + QA gate | ✅ Completed | r1 = **PASS-WITH-FIXES** ([phase-4-review-r1.md](reviews/phase-4-review-r1.md)); no S1/S2; F2/F3/F4/F5 fixed + F1 documented (ADR-009); F6/R1/R2 deferred-or-backlogged; owner closed F1 (account is the control) + F5 (don't persist password) 2026-06-10 |
| P4-CLOSE | Phase-4 closure sign-off | ✅ Completed | **gate PASSED 2026-06-10**: r1 PASS-WITH-FIXES (no open blocking), 130 tests green, governed docs current, all findings fixed-or-formally-disposed |

## Phase 5 — Data Dictionary Browser & Schema Tools (✅ CLOSED — exit gate passed 2026-06-10)

Charter: [phase-5-charter.md](charters/phase-5-charter.md). **Gate PASSED**: independent
review **r1 = FAIL** (F-1 S2) → remediated → **r2 = PASS-WITH-FIXES** (no open blocking).
F-1 fixed + re-verified; F-2 200-path fixed / 400-path deferred (ITM-015); F-3/F-4/F-5/N-1
fixed; **160 tests green**.

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P5-0 | Open Phase 5 Discovery charter | ✅ Completed | objectives/scope/risks/success criteria + open decisions D-A…D-E |
| P5-D | Owner approval + decision resolution (D-A…D-E) | ✅ Completed | resolved 2026-06-10: scoped introspection + upload; persist schema + /schema API; full browser (incl. where-used) + export; read-only (defer glossary); rename → Data Dictionary |
| P5-DES | Design + build sequence (approved) | ✅ Completed | `docs/data-dictionary-design.md` (`4d08844`); owner approved → build |
| P5-2 | Core schema-tool helpers (find/where-used) + serialization | ✅ Completed | `41ba9f2`; 6 tests |
| P5-4 | Schema persistence (`SchemaStore`) + ADR-011 | ✅ Completed | `8a00489`; 4 tests |
| P5-3 | Live SELECT-only introspection (`core/introspection.py`) + ADR-010 | ✅ Completed | `7598cc3`; **through the chokepoint**; 7 tests |
| P5-API | `/schemas` CRUD + `/schemas/introspect` API | ✅ Completed | `733ca59`; 7 tests |
| P5-1 | Data-dictionary browser UI + Schema Sources (introspect/save/load) | ✅ Completed | `2067ec7`; renamed nav; +1 smoke |
| P5-6 | Governed-doc updates (D2/D3/D4/D5/D6, ADR-010/011, CHANGELOG, traceability, registers) | ✅ Completed | code + docs in lockstep |
| R5.1 | Prepare review package | ✅ Completed | self-contained brief w/ filled Context + Phase-5 invariants: [reviews/phase-5-review-package.md](reviews/phase-5-review-package.md) |
| R5.2 | Independent adversarial review + QA (r1) | ✅ Done | verdict **FAIL** — 1 blocking (F-1 S2: metadata-only persistence not enforced) + F-2…F-5; [phase-5-review-r1.md](reviews/phase-5-review-r1.md) |
| R5.3 | Remediate r1 findings + regression tests | ✅ Done | F-1 fixed (not waived), F-2 200-path fixed / 400 → ITM-015, F-3/F-4/F-5 fixed; **159 tests**; commit `ee14e70` |
| R5.4 | Re-review (r2) on fixes + regression | ✅ Done | verdict **PASS-WITH-FIXES — gate cleared** ([phase-5-review-r2.md](reviews/phase-5-review-r2.md)); F-1 re-verified closed; F-2(400)/ITM-015 + N-1 carried; N-1 fixed at closure (160 tests) |
| P5-CLOSE | Phase-5 closure sign-off | ✅ Completed | **gate PASSED 2026-06-10**: r2 = PASS-WITH-FIXES (no open blocking), 160 tests green, governed docs current, all findings fixed-or-formally-deferred |

## Phase 6 — Observability & Error Handling (✅ CLOSED — exit gate passed 2026-06-10)

Charter: [phase-6-charter.md](charters/phase-6-charter.md) · Design:
[observability-error-handling-design.md](observability-error-handling-design.md). Decisions
**D-A…D-G** resolved (all as recommended); design approved; build **B1…B6** delivered
structured JSON logging, request/error-reference IDs, uniform DB-error sanitization
(**ITM-015 CLOSED**), in-process metrics, and a CI 3.11+3.13 matrix. **Exit gate PASSED:**
**r1 = PASS-WITH-FIXES** (2 blocking S2 — F-1/F-2 dependency/CI hygiene; pins not
3.13-installable + httpx floor broke LLM + CI never ran) → remediated (re-pinned to a
**clean-install-proven 3.13-capable** set; F-3/F-4/F-5 fixed) → **r2 = PASS**. **185 tests
green**; chokepoint unchanged. **Pushed (`d059295..2a88a04`); CI run #7 green on both
3.11 + 3.13 → ITM-016 CLOSED.** No open residual.

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P6-0 | Open Phase 6 Discovery charter | ✅ Completed | objectives/scope/risks/success criteria + open decisions D-A…D-G; pending owner approval before any code |
| P6-D | Owner approval + decision resolution (D-A…D-G) | ✅ Completed | resolved 2026-06-10: all seven as recommended — in-process metrics+`/metrics` (D-A); JSON-to-stdout + `LOG_LEVEL`/`LOG_FORMAT` (D-B); additive `error_id` keep `detail` (D-C); sanitize raw driver errors only (D-D); UUID + honour/echo `X-Request-ID` (D-E); in-memory metrics (D-F); CI 3.11+3.13 matrix (D-G) |
| P6-DES | Design + build sequence (owner-approved) | ✅ Completed | `docs/observability-error-handling-design.md` (`0b61061`); owner approved as-is 2026-06-10 → build |
| P6-1 | Central logging config (`src/core/logging_config.py`) — JSON/text, env-driven, idempotent | ✅ Completed | **B1**; `logging_config.py` + `JsonFormatter`/`TextFormatter` + `request_id` ContextVar; audit emits valid JSON; wired at API + UI startup; 7 tests (167 total); ADR-012; D3 updated |
| P6-2 | Request-correlation middleware + central exception handler + uniform error envelope | ✅ Completed | **B2**; `request_id_middleware` (honour/echo `X-Request-ID`); handlers for HTTPException/validation/catch-all inject `error_id`; additive to `detail` |
| P6-3 | Shared DB-error sanitizer across all DB-touching endpoints — **resolves ITM-015** | ✅ Completed | **B2**; `core/errors.py` (`log_error`/`sanitize_db_error_for_ui`) + `_db_error`; 4 arms refactored; **ITM-015 CLOSED**; 9 tests (176 total); D5/ADR-012 updated |
| P6-4 | In-process metrics (`src/core/metrics.py`) + read-only `/metrics` endpoint | ✅ Completed | **B3**; thread-safe counters + latency; wired into `_run_sql`; `GET /metrics`; 5 tests (181 total); D3/D5 updated |
| P6-5 | UI surfaces generic message + `error_id` | ✅ Completed | **B4**; 3 UI driver-error surfaces (`_try_connect`, introspection, `_run_and_display`) use shared `sanitize_db_error_for_ui` → generic msg + ref; `SqlSafetyError`/`ValueError` stay verbatim; +1 test (182 total) |
| P6-6 | Tests (sanitization/no-leak, error-id + header, log JSON shape, metrics, regression) | ✅ Completed | delivered across B1–B4: `test_logging_config.py` (7), `test_error_handling.py` (10), `test_metrics.py` (5) = **+22 → 182**; no chokepoint/safety regression |
| P6-7 | Governed-doc updates (D3/D5/D6/D7, ADR-012, CHANGELOG, traceability, registers) + **close ITM-015** | ✅ Completed | **B6**; D3/D5/D6/D7 + ADR-012 + CHANGELOG + traceability (NFR-7) + risk-register (RISK-19 Closed) + issue-log (ITM-015/016 Closed) + governance index, in lockstep |
| P6-G | (D-G) CI Python matrix 3.11 + 3.13 — **closes ITM-016** | ✅ Completed | **B5**; `ci.yml` `strategy.matrix.python-version: ["3.11","3.13"]` (`fail-fast: false`); **ITM-016 CLOSED** |
| R6.1 | Prepare exit-gate review package | ✅ Completed | [reviews/phase-6-review-package.md](reviews/phase-6-review-package.md); range `d059295..fc55a46`, 9 Phase-6 invariants to attack, leak-proof pointer |
| R6.2 | Independent adversarial review + QA (r1) | ✅ Done | verdict **PASS-WITH-FIXES** ([phase-6-review-r1.md](reviews/phase-6-review-r1.md)); all 9 invariants + suite verified green; 2 blocking **S2 (F-1/F-2)** = dependency/CI hygiene (pins not 3.13-installable + httpx floor breaks LLM + CI never ran) external to the Phase-6 code; F-3/F-4/F-5/F-7 minor |
| R6.3 | Remediate r1 findings + regression | ✅ Done | re-pinned to a clean-install-proven 3.13-capable set (F-1/F-2; 185 green on a fresh 3.13 venv); F-3 ingress id-sanitization, F-4 single id source, F-5 introspect+header leak tests; F-6 package note; F-7→ITM-017 |
| R6.4 | Re-review (r2) on the fixes | ✅ Done | verdict **PASS** ([phase-6-review-r2.md](reviews/phase-6-review-r2.md)); F-1/F-2 clean-install re-verified, F-3/F-4/F-5 confirmed; ITM-016 Mitigating (CI demo pending push) |
| R6.5 | Phase-6 closure sign-off | ✅ Completed | **gate PASSED**: r1 PASS-WITH-FIXES → r2 PASS; 185 tests; governed docs current. **Pushed `d059295..2a88a04`; CI run #7 green on both 3.11 + 3.13 → ITM-016 CLOSED.** Phase 6 fully closed; no open residual. |

## Phase 6.5 — Pre-Deployment Hardening (✅ CLOSED — exit gate passed 2026-06-11)

Charter: [phase-6.5-charter.md](charters/phase-6.5-charter.md). Bundles the carried code
preconditions gating any networked/multi-tenant deployment — ITM-009 (CORS/auth, RISK-12),
ITM-010 (base_url IP encodings), ITM-013/014 (file-store durability, RISK-16), ITM-017
(non-DB `str(exc)` surfaces) — into one charter → design → build → exit-gate cycle.
**Build gated on owner decisions D-A…D-F (P6.5-D); no code until approved.** RISK-04
(live-Oracle pass) stays out of scope (owner-scheduled).

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P6.5-0 | Open Phase 6.5 Discovery charter | ✅ Completed | objectives/scope/risks/success criteria + open decisions D-A…D-F; grounding facts verified against HEAD `2ba0a56` |
| P6.5-D | Owner approval + decision resolution (D-A…D-F) | ✅ Completed | resolved 2026-06-11, all as recommended: opt-in static API key via `X-API-Key`/`APP_API_KEY` (D-A); `/health` open + minimal, `/metrics` gated (D-B); `ALLOWED_ORIGINS` env, localhost default (D-C); atomic-write helper, keep JSON (D-D); corrupt records skip+log (D-E); intentional messages verbatim + `error_id`, rest generic (D-F) |
| P6.5-DES | Design + build sequence (owner-approved) | ✅ Completed | `docs/pre-deployment-hardening-design.md`; owner approved as-is 2026-06-11 → build |
| P6.5-1 | Network edge: opt-in API-key auth + env-driven CORS (ITM-009/RISK-12) | ✅ Completed | **B1**; `core/auth.py` (`X-API-Key` vs `APP_API_KEY`, `/health` exempt, `/metrics` gated) + `ALLOWED_ORIGINS` CORS with no-`*`-with-credentials invariant; 16 tests (**201 total**); D5/D7 + ADR-013; formal ITM-009 closure at B6 |
| P6.5-2 | `validate_base_url` numeric-encoding hardening (ITM-010) | ✅ Completed | **B2**; pure-Python `inet_aton`-style decode (`_numeric_host_to_ipv4`, ASCII-strict) before the IP checks; all-numeric-but-invalid hosts rejected fail-closed; 17 tests (**218 total**); formal ITM-010 closure at B6 |
| P6.5-3 | Shared atomic-write helper across the 4 JSON stores (ITM-013/RISK-16) | ✅ Completed | **B3**; `core/fileio.py::atomic_write_json` (same-dir temp + fsync + `os.replace`) adopted by `storage`/`profiles`/`reports`/`schema_store`, shape unchanged; 7 tests (**225 total**); ADR-014 + D3 updated; formal ITM-013 closure at B6 |
| P6.5-4 | Corrupt-record robustness in the report store (ITM-014) | ✅ Completed | **B4**; quarantine (skip-and-log w/ `error_id`, **preserve-on-save**) in `_deserialize`; profiles + schema stores had the same uncaught-raise → same treatment; 6 tests (**231 total**); formal ITM-014 closure at B6 |
| P6.5-5 | Non-DB error-surface sanitization (ITM-017) | ✅ Completed | **B5**; nl2sql catch-all split (ValueError/LLMError verbatim per ADR-012 rule, rest generic + `error_id`); profiles `SecretConfigError` 500 verbatim + server-side breadcrumb; 4 UI `SecretConfigError` arms show `(ref: …)` via `log_error_for_ui`; 5 tests (**236 total**); formal ITM-017 closure at B6 |
| P6.5-6 | Tests + governed-doc updates (D3/D5/D7, ADRs, CHANGELOG, registers) + close ITM-009/010/013/014/017 | ✅ Completed | **B6**; **ITM-009/010/013/014/017 CLOSED** (issue log v1.8); RISK-12 Closed, RISK-16 → Mitigating (concurrency residual = D7 constraint), RISK-11 residual narrowed; D3/D5/D6/D7, ADR-013/014 + index, traceability NFR-8, CHANGELOG — all in lockstep; **236 tests** |
| R6.5.1 | Prepare exit-gate review package | ✅ Completed | [reviews/phase-6.5-review-package.md](reviews/phase-6.5-review-package.md); range `2ba0a56..d34658c`, 9 phase invariants to attack |
| R6.5.2 | Independent adversarial exit-gate review + QA (r1) | ✅ Done | verdict **PASS-WITH-FIXES** ([phase-6.5-review-r1.md](reviews/phase-6.5-review-r1.md)); **no S1/S2** — all 9 invariants + suite verified green; 2 S3 (R1 Unicode SSRF first-line bypass, R2 fd-leak) + 2 S4 (R3 blank-CORS, R4 doc) |
| R6.5.3 | Remediate r1 findings + regression | ✅ Done | R1 NFKC host-fold (Unicode fullwidth-digit IP encodings rejected at the guard; genuine IDN preserved); R2 `os.close(fd)` on error path; R3 blank `ALLOWED_ORIGINS` → localhost fallback; R4 documented (D7); **+6 → 242 tests** |
| R6.5.4 | Phase-6.5 closure sign-off | ✅ Completed | **gate PASSED 2026-06-11**: r1 = PASS-WITH-FIXES (no blocking), R1–R4 all remediated, 242 tests, governed docs current. Closed on r1 by owner direction (no r2). Pushed `2ba0a56..9209e3a`. CI-matrix green confirmation deferred to **Round C1**. |

## Round C1 — Pre-GA Consolidation & Testing (✅ CLOSED 2026-06-12)

Charter: [round-C1-charter.md](charters/round-C1-charter.md). Verification + pre-GA cleanups, no
new features. **Scope + decisions D-A…D-C pending owner; no code until approved.**

| ID | Task | Status | Notes |
|----|------|--------|-------|
| C1-0 | Open Round C1 Discovery charter | ✅ Completed | objectives/scope/risks + decisions D-A…D-C |
| C1-D | Owner approval + decisions (D-A instance / D-B scope / D-C ITM-008) | ✅ Completed | resolved 2026-06-11: **Oracle XE available** → live pass runs this round (EBS templates still ITM-012); **full scope**; **build ITM-008** behind default-off flag |
| C1-DES | Design + build sequence + XE live-pass runbook | ✅ Completed | `docs/round-C1-design.md` (B1…B6 + read-only-account/sample-schema SQL) |
| C1-1 | Confirm CI 3.11+3.13 green on the pushed C1 code | ✅ Completed | **B4**; owner confirmed in the Actions tab — **CI run #12 green** on `f374380` (B1–B3 head), plus #10 (`9209e3a`) + #11 (`a395003`) green; a green run = both 3.11 + 3.13 legs passed. (B5 `5c1444d` is docs/script only, unpushed — no product/test change.) |
| C1-2 | RISK-04 live-Oracle + manual UI/observability pass | ✅ Completed | **B5** + owner UI walk; live engine pass against **XE 21c** (`XEPDB1`, read-only `aor_readonly`) via `scripts/c1_live_smoke.py` — connect/introspect/bound-report/export/safety **ALL PASS** ([evidence](reviews/round-C1-live-pass.md)); **owner browser-tested the Streamlit UI against XE satisfactorily 2026-06-11**. **RISK-04 Closed.** EBS-template live validation remains ITM-012 (needs real EBS). |
| C1-3 | ITM-006 — legacy `connection.json` → encrypted profiles | ✅ Completed | **B2**; write path removed (`save_connection_config` deleted; Save button retired); `migrate_legacy_connection()` imports-once + deletes (also any pre-F5 plaintext file); 245 tests; ITM-006 CLOSED, RISK-09 Closed |
| C1-4 | ITM-007 — `use_container_width` → `width='stretch'` | ✅ Completed | **B1**; 14 sites in `app.py` migrated (verified `streamlit==1.58.0`); smoke green; ITM-007 CLOSED |
| C1-5 | ITM-008 — NL PII scrubbing (per D-C) | ✅ Completed | **B3**; `core/llm/pii.py` behind default-off `SCRUB_PII`; external path only, local verbatim; email/SSN/card/phone masked; 15 tests (260 total); ITM-008 CLOSED |
| C1-6 | Governed-doc updates + GA-readiness verdict | ✅ Completed | **B6**; [round-C1-ga-readiness.md](round-C1-ga-readiness.md) — **GA-ready (core product) subject to deployment preconditions; EBS pack beta pending ITM-012**; registers/CHANGELOG/traceability current. **Round C1 CLOSED.** |
| RC1.1 | Prepare exit-gate review package (B1–B3 code) | ✅ Completed | [reviews/round-C1-review-package.md](reviews/round-C1-review-package.md); range `a395003..f374380` |
| RC1.2 | Independent adversarial exit-gate review (r1) | ✅ Done | verdict **PASS-WITH-FIXES** ([round-C1-review-r1.md](reviews/round-C1-review-r1.md)); no S1/S2; chokepoint diff empty; all B1–B3 invariants verified clean; C1-R1-F1 (S3) + C1-R1-F2 (S4) |
| RC1.3 | Remediate r1 findings + regression | ✅ Done | C1-R1-F1 storage delete-failure → logged warning (no secret); C1-R1-F2 load TOCTOU → try/except; **+2 → 262 tests** |

## Phase 7 — EBS Intelligence & Oracle 23ai Enhancements (✅ CLOSED — exit gate passed 2026-06-12)

Charter: [phase-7-charter.md](charters/phase-7-charter.md). Optional feature phase; primary
track = EBS metadata packs + glossary (no new infrastructure); 23ai vector = decide-deliberately
(XE 21c can't run it). **Decisions D-A…D-D pending owner; no code until approved.**

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P7-0 | Open Phase 7 Discovery charter | ✅ Completed | scope proposal + decisions D-A…D-D |
| P7-D | Owner approval + decisions (D-A 23ai / D-B pack breadth / D-C glossary mutability / D-D fold-ins) | ✅ Completed | resolved 2026-06-12: defer 23ai (tracked); all 5 modules core tables; read-only curated; fold in `/v1` (T-18), not ITM-011 |
| P7-DES | Design + build sequence (owner-approved) | ✅ Completed | `docs/ebs-intelligence-design.md`; owner approved 2026-06-12 → build |
| P7-1 | **B1** EBS packs core (`core/ebs_packs.py`, 5 modules, ADR-015) | ✅ Completed | curated packs + glossary for GL/AP/AR/PO/OM (tables aligned to the template catalog); `build_ebs_context()` metadata-only, tripwire-safe; 9 tests (**271 total**); ADR-015 |
| P7-2 | **B2** NL→SQL EBS context enrichment (opt-in, external-only, tripwire) | ✅ Completed | `generate_sql_from_nl(ebs_modules=…)` + `/nl2sql` `ebs_modules[]`; combined context through `assert_no_values`; local path unchanged; 3 tests (**274 total**); D5 v1.8 |
| P7-3 | **B3** UI: Data Dictionary packs browser + Query Builder module multiselect | ✅ Completed | Data Dictionary "EBS Packs" expander (tables + glossary); Query Builder NL-mode module multiselect → `ebs_modules`; headless smoke green (279) |
| P7-4 | **B4** `/packs` read-only API | ✅ Completed | `GET /packs` + `GET /packs/{module}` (404 uniform envelope); 5 tests (**279 total**); D5 v1.9 |
| P7-5 | **B5** `/v1` API prefix via router (back-compat) | ✅ Completed | every route on an `APIRouter` mounted at `""` + `/v1`; handlers/middleware/auth on app; `/v1/health` exempt; 6 tests (**285 total**); D5 v1.10; **T-18 CLOSED** |
| P7-6 | **B6** 23ai deferral ADR/note + ITM-018 | ✅ Completed | [ADR-016](adr/ADR-016-defer-23ai-vector-track.md) records the direction; **ITM-018** logged (deferred, not dropped) |
| P7-7 | **B7** Governed-doc sweep + traceability + registers | ✅ Completed | D3/D5/D6/traceability (FR-14) + ADR index + CHANGELOG + issue-log in lockstep; review package prepared |
| P7-V | EBS pack validation method (ITM-012) — self-audit + live validator | ✅ Completed | `reviews/ebs-pack-self-audit.md` (confidence-flagged; all tables High) + `scripts/ebs_pack_validate.py` (introspects a real EBS via the chokepoint, diffs every pack table/column; offline-tested, 4 tests → 289); ITM-012 close criteria defined; **live run gated on EBS access** |
| R7.1 | Prepare exit-gate review package | ✅ Completed | [reviews/phase-7-review-package.md](reviews/phase-7-review-package.md); range `baf4224..HEAD` |
| R7.2 | Independent adversarial exit-gate review (r1) | ✅ Done | verdict **PASS** ([phase-7-review-r1.md](reviews/phase-7-review-r1.md)); no blocking; all 7 invariants verified; 2 S4 (P7-R1-F1/F2) |
| R7.3 | Remediate r1 findings + regression | ✅ Done | F1 `ebs_modules` unknown→422 (+case-normalize); F2 `/v1` POST auth tests; **+4 → 293** |
| P7-CLOSE | Phase-7 closure sign-off | ✅ Completed | **gate PASSED 2026-06-12**: r1 = PASS (no blocking), F1/F2 remediated, 293 tests, governed docs current. **Phase 7 CLOSED.** EBS packs need real-EBS validation (ITM-012, method defined); 23ai deferred (ITM-018). |

## Phase 8 — Follow-up Actions: Email a Report (🟢 v2; build B1–B5 complete, B6 review pending)

Charter: [phase-8-charter.md](charters/phase-8-charter.md) · Design:
[email-followup-action-design.md](email-followup-action-design.md). **First v2 feature** (v2 branch;
local commits only, no push until the July limit reset). SELECT-only chokepoint + schema redaction
untouched; **no LLM on the email path**. Owner directive: a real, demoable send.

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P8-0 | Open Phase 8 Discovery charter | ✅ Completed | objectives/scope/risks + decisions D-A…D-F; grounding verified against the v2 tree |
| P8-D | Owner approval + decisions (D-A…D-F) | ✅ Completed | SMTP+App Password; single shared mailbox; CSV/Excel user-pick; free-form + smart quick-pick; UI+service, no HTTP endpoint; optional `EMAIL_ALLOWED_DOMAINS` |
| P8-DES | Design + build sequence (approved) | ✅ Completed | `docs/email-followup-action-design.md`; `core/mailer/` package (stdlib SMTP, **no new dependency**) |
| P8-1 | **B1** mailer core (config/message/recipients) + tests | ✅ Completed | `0abbaca`; opt-in `email_enabled`; validation + CRLF/header-injection guard + allow-list + size cap + `EmailMessage` (reuses CSV/Excel helpers); smart quick-pick; 50 tests (**357 total**) |
| P8-2 | **B2** SMTP transport (`sender.py`) + errors/metrics + tests | ✅ Completed | `6e72fe8`; `send_report_email` → `SendResult` (ok/rejected/error); audit-log metadata-only; `emails_sent/failed/rejected`; sanitized transport errors (`GENERIC_EMAIL_DETAIL`+`error_id`); 8 mocked-SMTP tests (**365 total**) |
| P8-3 | **B3** "Send as email" UI in query/report views | ✅ Completed | `320da37`; opt-in expander rendered from `last_results` (survives reruns); quick-pick chips, free-form To/Cc, CSV/Excel toggle; app.py compiles |
| P8-4 | **B4** live-demo enablement (smoke + config/deploy) | ✅ Completed | `53a4264`; `scripts/p8_email_smoke.py`; `.env.example` + `render.yaml` (UI service, secrets sync:false); **live send verified end-to-end against Gmail** (success criterion 6) |
| P8-5 | **B5** governed-doc sweep (ADR-017, RISK-20/21, ITM-020/021, CHANGELOG, registers, HANDOFF) | ✅ Completed | this entry; docs in lockstep |
| P8-6 | **B6** independent adversarial exit-gate review (reviewer ≠ author) | 🔜 Pending | owner-supplied reviewer; v2 range `640bd92..HEAD`; review package next |
| P8-DEMO | Owner live demo to an intended recipient | 🔜 Pending | send to an owner-chosen recipient via the UI or smoke script (criterion 6 — path already proven) |

## Standing per-phase review gate (applies to EVERY phase)

Instantiated as `R<phase>.1…7` at each phase exit (see [external-review-gate](process/external-review-gate.md)):
`.1` prepare package · `.2` independent adversarial code review · `.3` adversarial QA · `.4` triage → issue log · `.5` remediate blocking + re-validate · `.6` re-review until PASS · `.7` record verdict + sign-off.

| ID | Task | Status | Notes |
|----|------|--------|-------|
| R2.x | Phase-2 independent adversarial review + QA | ⏭️ Waived | Gate effective Phase 3+ ([ADR-006](adr/ADR-006-external-review-gate.md)); Phase-2 author-only review accepted ([RISK-10](risk-register.md)) |
| R3.x | Phase-3 independent adversarial review + QA | ✅ Completed | r1 FAIL → remediate → **r2 PASS-WITH-FIXES** (no open blocking); gate closed 2026-06-10 |

## Deployment GA-Readiness Hardening (✅ COMPLETE — 2026-06-12)

Unplanned post-Phase-7 improvement: audit and fix the deployment artifacts against
the five GA-readiness preconditions recorded in [round-C1-ga-readiness.md](round-C1-ga-readiness.md).
No app-code or chokepoint changes; 293 tests remain green. Committed `f353ebc` (pushed).

| ID | Task | Status | Notes |
|----|------|--------|-------|
| DH-1 | `render.yaml`: add `APP_SECRET_KEY`/`APP_API_KEY`/`ALLOWED_ORIGINS` (sync:false) + `LOG_LEVEL`/`LOG_FORMAT`/`STORAGE_DIR`; bump `PYTHON_VERSION` 3.11→3.13 | ✅ Completed | B1; missing vars would cause profile-encryption failure + open API on naïve deploy |
| DH-2 | `Dockerfile.api.local` + `Dockerfile.local`: pin base image `python:3.12-slim` → `python:3.13-slim` | ✅ Completed | B2; aligns containers with CI-validated 3.11/3.13 matrix |
| DH-3 | `docker-compose.yml`: Compose profiles `api`/`ui`/`frontend`; named `storage` volume; add missing `ui` (Streamlit) service | ✅ Completed | B3; enforces single-worker-per-store constraint (RISK-16); Streamlit was completely absent |
| DH-4 | `.gitignore`: add `!Dockerfile.local` + `!Dockerfile.*.local` negations | ✅ Completed | B4 / **BUG-006 FIXED**; Vite `*.local` glob had excluded both Dockerfiles from git since repo init |
| DH-5 | `.env.example`: add `APP_API_KEY`, `ALLOWED_ORIGINS`, `LLM_POLICY`, `SCRUB_PII`, `LOG_LEVEL`, `LOG_FORMAT` | ✅ Completed | B5; 6 vars from Phases 3/6/6.5/C1 were absent |
| DH-6 | `docs/07-deployment-plan.md` v1.6: Docker profile commands, single-worker note, `LLM_POLICY` env table, release checklist gates | ✅ Completed | B6; docs in lockstep |

## Backlog / Carried items

| ID | Task | Phase | Status |
|----|------|-------|--------|
| T-12 | LLM provider abstraction (`LLMProvider`) + explanation/confidence | Phase 3 | ✅ Completed (Phase 3 / P3-1) |
| T-18 | API `/v1` versioning prefix | Phase 3/4 | ✅ Completed (Phase 7 / B5) |
| T-19 | Migrate legacy `connection.json` → encrypted profiles | Phase 2 follow-up | ✅ Completed (Round C1 / B2; RISK-09 Closed) |
| T-20 | Saved reports: profile binding + parameters | Phase 4 | ✅ Completed (Phase 4 / P4-1/P4-5) |
| ITM-011 | List/multi-value bind parameters | Feature | ✅ Closed (2026-06-12; `expand_list_binds` in `src/db.py`; `"list"` ParamType in `reports.py`; 14 new tests → 307 total) |
| ITM-012 | EBS pack + template validation vs real EBS 12.2 | External | 📋 Open (tooling ready; gated on EBS instance access) |
| ITM-018 | Oracle 23ai vector track | Feature | 📋 Deferred (ADR-016; needs a 23ai instance) |
| ITM-019 | Render persistent storage → Render Disk | Ops | ✅ Resolved (Render Disk; render.yaml disk blocks + D7 §5 runbook; no code change) |
| ITM-020 | Gmail API (OAuth2) + per-user sender | Feature (v2) | 📋 Deferred (ADR-017; SMTP+App Password ships now; OAuth pairs with multi-tenant identity) |
| ITM-021 | AI-drafted email body | Feature (v2) | 📋 Deferred (ADR-017; would send row data to the LLM — needs an explicit opt-in / local summary) |

## Dependencies & critical path

- **Phase-2 closure gate: PASSED (2026-06-10).** Phase 3 Discovery may open.
- **Phase-3 closure gate: PASSED (2026-06-10)** — r2 PASS-WITH-FIXES, no open blocking. Phase 4 may open.
- **Phase 4: CLOSED (2026-06-10)** — exit gate PASSED (r1 PASS-WITH-FIXES, no open blocking; 130 tests).
- **Phase 5: CLOSED (2026-06-10)** — exit gate PASSED (r1 FAIL → r2 PASS-WITH-FIXES, no open blocking; 160 tests). Phase 6 may open next.
- **Phase 6: CLOSED (2026-06-10)** — exit gate PASSED (r1 PASS-WITH-FIXES → r2 PASS; 185 tests). ITM-015 + ITM-016 closed (pushed; CI run #7 green on both 3.11 + 3.13). Phase 7 (optional) may open next.
- **Phase 6.5: CLOSED (2026-06-11)** — exit gate PASSED (r1 PASS-WITH-FIXES → R1–R4 remediated → closed on r1, no r2; 242 tests; pushed). ITM-009/010/013/014/017 closed; RISK-12 Closed, RISK-16 Mitigating. **Phase 7 (optional) now gated only on RISK-04 (pre-GA live-Oracle pass).** Next: **Round C1** (pre-GA consolidation & testing) — carries CI-matrix green confirmation, RISK-04, and ITM-006/007/008.
- Pre-GA (not gating Phase 3): manual UI/live-DB pass (RISK-04), `/v1` API prefix (T-18), legacy `connection.json` migration (T-19).
- **Hard preconditions for any networked/multi-tenant deployment (Phase 7): CLEARED** — CORS/auth (ITM-009/RISK-12), `base_url` host-normalization (ITM-010), file-store durability (ITM-013/014/RISK-16) and non-DB error surfaces (ITM-017) all closed under Phase 6.5. Remaining pre-GA gate = RISK-04 (live-Oracle pass), carried into Round C1.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial tracker; Phase-2 delivered, P2.5 in progress. |
| 1.1 | 2026-06-10 | Delivery | Phase-3 exit gate PASSED (r2 PASS-WITH-FIXES); R3.3/P3-7 closed; Phase 4 may open. |
| 1.2 | 2026-06-10 | Delivery | Phase 4 Discovery opened (P4-0); P4-1…P4-7 + R4.x seeded as Planned; build gated on owner decisions (P4-D). |
| 1.3 | 2026-06-10 | Delivery | Phase 4 decisions resolved + built: P4-DES…P4-7 Completed (118 tests); R4.x exit-gate review is the next action (owner-supplied reviewer). |
| 1.4 | 2026-06-10 | Delivery | Phase 4 exit gate PASSED (r1 PASS-WITH-FIXES); F2/F3/F4/F5 fixed, F1 documented (ADR-009), F6/R1/R2 deferred; 130 tests; Phase 4 CLOSED. |
| 1.5 | 2026-06-10 | Delivery | Phase 5 Discovery opened (P5-0); P5-1…P5-6 + R5.x seeded as Planned; build gated on owner decisions (P5-D). |
| 1.6 | 2026-06-10 | Delivery | Phase 5 decisions resolved + built: P5-DES…P5-6 Completed (155 tests); R5.x exit-gate review is the next action (owner-supplied reviewer). |
| 1.7 | 2026-06-10 | Delivery | Phase 5 r1 = FAIL (F-1 S2) → remediated (159 tests; F-1 fixed, F-2…F-5); r2 re-review pending. |
| 1.8 | 2026-06-10 | Delivery | Phase 5 r2 = PASS-WITH-FIXES; N-1 fixed at closure (160 tests); gate PASSED; Phase 5 CLOSED. |
| 1.9 | 2026-06-10 | Delivery | Phase 6 Discovery opened (P6-0); P6-D…P6-7 + P6-G + R6.x seeded as Planned; build gated on owner decisions (P6-D). |
| 1.10 | 2026-06-10 | Delivery | Phase 6 decisions D-A…D-G resolved (all as recommended); P6-D Completed; P6-DES (design) In Progress — design doc pending owner approval before code. |
| 1.11 | 2026-06-10 | Delivery | Phase 6 design approved (P6-DES Completed); Build started — B1 (logging core) done: P6-1 Completed, 167 tests, ADR-012, D3 updated. |
| 1.12 | 2026-06-10 | Delivery | Phase 6 B2 done: P6-2/P6-3 Completed; request-id middleware + exception handlers + `core/errors` sanitizer; **ITM-015 CLOSED**; 176 tests; D5 updated. |
| 1.13 | 2026-06-10 | Delivery | Phase 6 B3 done: P6-4 Completed; `core/metrics` + `GET /metrics`, counters wired into chokepoint; 181 tests; D3/D5 updated. |
| 1.14 | 2026-06-10 | Delivery | Phase 6 B4 done: P6-5 Completed; UI driver-error surfaces sanitized (shared helper) + ref id; safety/validation messages verbatim; 182 tests. |
| 1.15 | 2026-06-10 | Delivery | Phase 6 B5 done: P6-G Completed; CI 3.11+3.13 matrix; **ITM-016 CLOSED**. |
| 1.16 | 2026-06-10 | Delivery | Phase 6 B6 done: P6-6/P6-7 Completed; governed docs (D3/D5/D6/D7, ADR-012, CHANGELOG, traceability, registers, index) in lockstep; build B1…B6 complete (182 tests); R6.1 review-package prep is next. |
| 1.17 | 2026-06-10 | Delivery | Phase 6 R6.1 Completed — review package prepared (`d059295..HEAD`). Next: owner runs the independent adversarial exit-gate reviewer (R6.2). |
| 1.18 | 2026-06-10 | Delivery | Phase 6 exit gate: r1 = PASS-WITH-FIXES (F-1/F-2 S2 = dependency/CI hygiene) → remediated (3.13-capable repin, clean-install-proven, 185 green; F-3/F-4/F-5 fixed) → r2 = PASS. **Phase 6 CLOSED.** Residual ITM-016 (CI demo pending push). |
| 1.19 | 2026-06-10 | Delivery | Pushed `d059295..2a88a04`; **CI run #7 green on both 3.11 + 3.13 → ITM-016 CLOSED.** Phase 6 fully closed, no open residual. |
| 1.20 | 2026-06-11 | Delivery | Phase 6.5 Discovery opened (P6.5-0); bundles ITM-009/010/013/014/017 as a pre-deployment hardening mini-phase; P6.5-1…P6.5-6 + R6.5.x seeded as Planned; build gated on owner decisions D-A…D-F (P6.5-D). |
| 1.21 | 2026-06-11 | Delivery | Phase 6.5 decisions D-A…D-F resolved (all as recommended); P6.5-D Completed; P6.5-DES (design) In Progress — design doc pending owner approval before code. |
| 1.22 | 2026-06-11 | Delivery | P6.5 design + build sequence drafted (`pre-deployment-hardening-design.md`, B1…B6); awaiting owner approval (P6.5-DES) before any code. |
| 1.23 | 2026-06-11 | Delivery | P6.5 design approved (P6.5-DES Completed); Build started — B1 (network edge) done: P6.5-1 Completed, 201 tests, ADR-013, D5/D7 updated, ADR index backfilled (ADR-012/013). |
| 1.24 | 2026-06-11 | Delivery | P6.5 B2 done: P6.5-2 Completed — `validate_base_url` rejects integer/hex/octal/dotted IP encodings (fail-closed on all-numeric invalid hosts); 218 tests. |
| 1.25 | 2026-06-11 | Delivery | P6.5 B3 done: P6.5-3 Completed — atomic JSON writes via `core/fileio.py` across the 4 stores (ADR-014, D3); 225 tests. |
| 1.26 | 2026-06-11 | Delivery | P6.5 B4 done: P6.5-4 Completed — corrupt-record quarantine (skip-and-log + preserve-on-save) in report/profile/schema stores; 231 tests. |
| 1.27 | 2026-06-11 | Delivery | P6.5 B5 done: P6.5-5 Completed — ITM-017 surfaces routed (nl2sql generic-on-unexpected; SecretConfigError verbatim + breadcrumb/refs); 236 tests; design v1.2 refinement recorded. |
| 1.28 | 2026-06-11 | Delivery | P6.5 B6 done: P6.5-6 Completed — governed-doc sweep; ITM-009/010/013/014/017 formally CLOSED; RISK-12 Closed / RISK-16 Mitigating; NFR-8 traced. Build B1…B6 complete (236 tests); R6.5.1 review-package prep is next. |
| 1.29 | 2026-06-11 | Delivery | R6.5.1 Completed — review package prepared (`2ba0a56..d34658c`). Next: owner runs the independent adversarial exit-gate reviewer (R6.5.2). |
| 1.30 | 2026-06-11 | Delivery | R6.5.2 exit-gate review r1 = PASS-WITH-FIXES (no S1/S2); R6.5.3 remediated all four findings (R1 Unicode SSRF NFKC fold, R2 fd-close, R3 blank-CORS fallback, R4 doc) → 242 tests. Gate cleared; closure (R6.5.4) pending optional r2 spot-check + push. |
| 1.31 | 2026-06-11 | Delivery | **Phase 6.5 CLOSED** (R6.5.4) — gate passed on r1 by owner direction (no r2); pushed `2ba0a56..9209e3a`. Next = **Round C1** (pre-GA consolidation & testing; charter opened); CI-matrix green confirmation + RISK-04 + ITM-006/007/008 carried there. |
| 1.32 | 2026-06-11 | Delivery | Round C1 decisions resolved (XE available / full scope / build ITM-008); design + XE runbook done (`round-C1-design.md`); **B1 done — ITM-007 CLOSED** (242 tests). Next: B2 ITM-006, B3 ITM-008; B5 live pass awaits owner XE setup. |
| 1.33 | 2026-06-11 | Delivery | **B2 done — ITM-006 CLOSED, RISK-09 Closed**: `connection.json` write path retired, read-and-delete migration; D3 v1.5; 245 tests. Next: B3 ITM-008. |
| 1.34 | 2026-06-11 | Delivery | **B3 done — ITM-008 CLOSED**: `core/llm/pii.py` opt-in PII scrubbing (`SCRUB_PII`, external path only); D3/D7 updated; 260 tests. All C1 code items (B1–B3) done. Next: B4 CI confirm, B5 live pass (owner XE setup), RC1 review, B6 verdict. |
| 1.35 | 2026-06-11 | Delivery | **B5 done — RISK-04 live-Oracle pass against XE 21c: ALL PASS** (connect/introspect/bound-report/export/safety via `scripts/c1_live_smoke.py`; [evidence](reviews/round-C1-live-pass.md)); risk-register v1.8 (RISK-04 Med→Low). Remaining: B4 CI confirm, RC1 review, B6 verdict (+ optional UI browser-visual; EBS templates = ITM-012). |
| 1.36 | 2026-06-12 | Delivery | **B4 done** — owner confirmed CI green (run #12 on `f374380`, +#10/#11); **owner browser-tested the UI against XE satisfactorily → RISK-04 Closed**. RC1.1 review package prepared (`a395003..f374380`). Remaining: RC1.2 independent review (owner-supplied), B6 GA-readiness verdict. |
| 1.37 | 2026-06-12 | Delivery | RC1.2 exit-gate review r1 = PASS-WITH-FIXES (no S1/S2); RC1.3 remediated C1-R1-F1 (storage delete-failure warning) + C1-R1-F2 (load TOCTOU) → 262 tests. Gate cleared; B6 GA-readiness verdict next to close C1. |
| 1.38 | 2026-06-12 | Delivery | **Round C1 CLOSED** (C1-6/B6) — GA-readiness verdict recorded (`round-C1-ga-readiness.md`): **GA-ready core product** subject to deployment preconditions; EBS pack beta pending ITM-012. Phase 7 (optional) is the only remaining roadmap item. |
| 1.39 | 2026-06-12 | Delivery | Phase 7 Discovery opened (P7-0) — EBS metadata packs + glossary primary track; 23ai vector decide-deliberately (XE 21c constraint); P7-1…P7-5 + R7.x seeded; build gated on owner decisions D-A…D-D (P7-D). |
| 1.40 | 2026-06-12 | Delivery | Phase 7 decisions D-A…D-D resolved (defer 23ai / 5 modules core / read-only / fold in `/v1`); P7-D Completed; design + build sequence B1…B7 drafted (`ebs-intelligence-design.md`); P7-DES In Progress — pending owner approval before code. |
| 1.41 | 2026-06-12 | Delivery | Phase 7 design approved (P7-DES Completed); Build started — **B1 done**: `core/ebs_packs.py` (5-module curated packs + glossary, ADR-015), `build_ebs_context()` tripwire-safe; 271 tests. Next: B2 NL→SQL enrichment. |
| 1.42 | 2026-06-12 | Delivery | Phase 7 **B2 done** (P7-2): opt-in `ebs_modules` in `generate_sql_from_nl` + `/nl2sql` (external-only, combined context through `assert_no_values`); D5 v1.8; 274 tests. Next: B3 UI. |
| 1.43 | 2026-06-12 | Delivery | Phase 7 **B4 + B3 done** (P7-4/P7-3): read-only `/packs` API (D5 v1.9; +5 → 279) + UI (Data Dictionary EBS-packs browser, Query Builder module multiselect; smoke green). Next: B5 `/v1` prefix, B6 defer, B7 sweep. |
| 1.44 | 2026-06-12 | Delivery | Phase 7 **B5 done** (P7-5): `/v1` prefix via APIRouter mounted twice (back-compat); auth + safety gate enforced on `/v1`; `/v1/health` exempt; **T-18 CLOSED**; D5 v1.10; 285 tests. Next: B6 defer, B7 sweep. |
| 1.45 | 2026-06-12 | Delivery | Phase 7 **B6 + B7 done**: ADR-016 (23ai deferral) + ITM-018; governed-doc sweep (traceability FR-14, D6, registers); **build B1…B7 complete (285 tests)**; R7.1 review package prepared. Next: R7.2 independent exit-gate review (owner-supplied). |
| 1.46 | 2026-06-12 | Delivery | ITM-012 validation method (P7-V): EBS pack self-audit (`reviews/ebs-pack-self-audit.md`) + automated live validator (`scripts/ebs_pack_validate.py`, offline-tested); 289 tests. Live EBS run gated on instance access. |
| 1.47 | 2026-06-12 | Delivery | **Phase 7 CLOSED** — exit-gate review r1 = PASS (no blocking); P7-R1-F1/F2 (S4) remediated → 293 tests. **All phases (1–6 + 6.5 + C1 + 7) closed.** Open carries: ITM-012 (EBS live validation, method defined), ITM-018 (23ai deferred). |
| 1.48 | 2026-06-12 | Delivery | **Deployment GA-readiness hardening COMPLETE** — DH-1…DH-6 + BUG-006 fixed; backlog T-12/T-18/T-19/T-20 marked completed; ITM-011/012/018/019 carried as the only open items. Pushed `f353ebc`. |
| 1.49 | 2026-06-13 | Delivery | **v2 Phase 8 — Email a Report follow-up action: build B1–B5 complete** (`0abbaca..53a4264` on branch `v2`; local commits only, no push). `core/mailer/` stdlib-SMTP package + UI + smoke; 58 new tests (**365 total**); ADR-017; RISK-20/21; ITM-020/021 deferred. **Live send verified end-to-end against Gmail.** Remaining: P8-6 independent exit-gate review (owner-supplied) + P8-DEMO owner live demo to an intended recipient. |
