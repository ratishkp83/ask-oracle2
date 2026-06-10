# D11 — Task Tracker

> **Document:** Task Tracker · **Version:** 1.0 · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-10

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

## Phase 6 — Observability & Error Handling (🔄 Discovery — charter awaiting owner decisions)

Charter: [phase-6-charter.md](charters/phase-6-charter.md). **Discovery opened 2026-06-10**;
objectives/scope/deliverables/risks/success criteria + open decisions **D-A…D-G** drafted.
**Build is gated on owner approval + decision resolution (P6-D).** Theme: structured JSON
logging, request/error-reference IDs, uniform DB-error sanitization (**closes ITM-015**), and
lightweight in-process metrics.

| ID | Task | Status | Notes |
|----|------|--------|-------|
| P6-0 | Open Phase 6 Discovery charter | ✅ Completed | objectives/scope/risks/success criteria + open decisions D-A…D-G; pending owner approval before any code |
| P6-D | Owner approval + decision resolution (D-A…D-G) | ✅ Completed | resolved 2026-06-10: all seven as recommended — in-process metrics+`/metrics` (D-A); JSON-to-stdout + `LOG_LEVEL`/`LOG_FORMAT` (D-B); additive `error_id` keep `detail` (D-C); sanitize raw driver errors only (D-D); UUID + honour/echo `X-Request-ID` (D-E); in-memory metrics (D-F); CI 3.11+3.13 matrix (D-G) |
| P6-DES | Design + build sequence (owner-approved) | ✅ Completed | `docs/observability-error-handling-design.md` (`0b61061`); owner approved as-is 2026-06-10 → build |
| P6-1 | Central logging config (`src/core/logging_config.py`) — JSON/text, env-driven, idempotent | ✅ Completed | **B1**; `logging_config.py` + `JsonFormatter`/`TextFormatter` + `request_id` ContextVar; audit emits valid JSON; wired at API + UI startup; 7 tests (167 total); ADR-012; D3 updated |
| P6-2 | Request-correlation middleware + central exception handler + uniform error envelope | ✅ Completed | **B2**; `request_id_middleware` (honour/echo `X-Request-ID`); handlers for HTTPException/validation/catch-all inject `error_id`; additive to `detail` |
| P6-3 | Shared DB-error sanitizer across all DB-touching endpoints — **resolves ITM-015** | ✅ Completed | **B2**; `core/errors.py` (`log_error`/`sanitize_db_error_for_ui`) + `_db_error`; 4 arms refactored; **ITM-015 CLOSED**; 9 tests (176 total); D5/ADR-012 updated |
| P6-4 | In-process metrics (`src/core/metrics.py`) + read-only `/metrics` endpoint | 📋 Planned | counts (executed/rejected/errored) + latency; shape per D-A |
| P6-5 | UI surfaces generic message + `error_id` | 📋 Planned | `src/app.py` error displays |
| P6-6 | Tests (sanitization/no-leak, error-id + header, log JSON shape, metrics, regression) | 📋 Planned | no chokepoint/safety regression |
| P6-7 | Governed-doc updates (D3/D5/D6/D7, ADR-012, CHANGELOG, traceability, registers) + **close ITM-015** | 📋 Planned | code + docs in lockstep |
| P6-G | (Optional, D-G) CI Python matrix 3.11 + 3.13 — **closes ITM-016** | 📋 Planned | gated on D-G |
| R6.1–.7 | Phase-6 independent adversarial review + QA gate | 📋 Planned | owner-supplied reviewer; iterate to PASS |

## Standing per-phase review gate (applies to EVERY phase)

Instantiated as `R<phase>.1…7` at each phase exit (see [external-review-gate](process/external-review-gate.md)):
`.1` prepare package · `.2` independent adversarial code review · `.3` adversarial QA · `.4` triage → issue log · `.5` remediate blocking + re-validate · `.6` re-review until PASS · `.7` record verdict + sign-off.

| ID | Task | Status | Notes |
|----|------|--------|-------|
| R2.x | Phase-2 independent adversarial review + QA | ⏭️ Waived | Gate effective Phase 3+ ([ADR-006](adr/ADR-006-external-review-gate.md)); Phase-2 author-only review accepted ([RISK-10](risk-register.md)) |
| R3.x | Phase-3 independent adversarial review + QA | ✅ Completed | r1 FAIL → remediate → **r2 PASS-WITH-FIXES** (no open blocking); gate closed 2026-06-10 |

## Backlog (next phases)

| ID | Task | Phase | Status |
|----|------|-------|--------|
| T-12 | LLM provider abstraction (`LLMProvider`) + explanation/confidence | Phase 3 | 📋 Planned (seeded by T-05) |
| T-18 | API `/v1` versioning prefix | Phase 3/4 | 📋 Planned |
| T-19 | Migrate legacy `connection.json` → encrypted profiles | Phase 2 follow-up | 📋 Planned (RISK-09) |
| T-20 | Saved reports: profile binding + parameters | Phase 4 | 📋 Planned |

## Dependencies & critical path

- **Phase-2 closure gate: PASSED (2026-06-10).** Phase 3 Discovery may open.
- **Phase-3 closure gate: PASSED (2026-06-10)** — r2 PASS-WITH-FIXES, no open blocking. Phase 4 may open.
- **Phase 4: CLOSED (2026-06-10)** — exit gate PASSED (r1 PASS-WITH-FIXES, no open blocking; 130 tests).
- **Phase 5: CLOSED (2026-06-10)** — exit gate PASSED (r1 FAIL → r2 PASS-WITH-FIXES, no open blocking; 160 tests). Phase 6 may open next.
- **Phase 6: Discovery OPEN (2026-06-10)** — charter drafted; **build gated on owner approval + decisions D-A…D-G (P6-D)**. Folds in ITM-015 (and optionally ITM-016 per D-G).
- Pre-GA (not gating Phase 3): manual UI/live-DB pass (RISK-04), `/v1` API prefix (T-18), legacy `connection.json` migration (T-19).
- **Hard precondition for any networked/multi-tenant deployment (Phase 7):** CORS/auth hardening (ITM-009/RISK-12) + `base_url` host-normalization (F7/ITM-010).

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
