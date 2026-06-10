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

## Phase 5 — Data Dictionary Browser & Schema Tools (🔄 Discovery — decisions pending)

Charter: [phase-5-charter.md](charters/phase-5-charter.md). Opened 2026-06-10. **No code
until the owner approves the charter and resolves decisions D-A…D-E** (live introspection,
schema persistence + API, browser depth, business glossary, UI placement).

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
| **R5.2–.7** | **Phase-5 independent adversarial review + QA gate** | ⏳ **Next — awaiting owner** | reviewer ≠ author; **owner supplies a fresh reviewer agent** ([prompt](process/adversarial-reviewer-prompt.md) + [package](reviews/phase-5-review-package.md)) over range `5335876..HEAD`; iterate to PASS |

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
- **Phase 5: DEV+TEST COMPLETE (2026-06-10)** — P5-1…P5-6 done, 155 tests green, docs in lockstep. **Exit gate (R5.x) pending: owner supplies the independent adversarial reviewer** over `6a299f8..HEAD`; remediate to PASS, then close Phase 5.
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
