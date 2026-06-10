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
- Pre-GA (not gating Phase 3): manual UI/live-DB pass (RISK-04), `/v1` API prefix (T-18), legacy `connection.json` migration (T-19).
- **Hard precondition for any networked/multi-tenant deployment (Phase 7):** CORS/auth hardening (ITM-009/RISK-12) + `base_url` host-normalization (F7/ITM-010).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial tracker; Phase-2 delivered, P2.5 in progress. |
| 1.1 | 2026-06-10 | Delivery | Phase-3 exit gate PASSED (r2 PASS-WITH-FIXES); R3.3/P3-7 closed; Phase 4 may open. |
