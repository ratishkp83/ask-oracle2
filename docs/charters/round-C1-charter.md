# Round C1 Charter — Pre-GA Consolidation & Testing

> **Document:** Round Charter · **Version:** 1.0 · **Status:** 🔄 Discovery — OPEN (scope + decisions pending owner approval; **no code until approved**) · **Owner:** Product/Engineering · **Last updated:** 2026-06-11

## Lifecycle stage
**Discovery OPENED 2026-06-11.** With Phases 1–6 and the Phase-6.5 hardening mini-phase all
closed, every **code** precondition for a networked/multi-tenant deployment is cleared. What
remains before GA is **verification against reality** and a handful of pre-GA cleanups that
need no new feature work. Round C1 bundles those into one consolidation/testing round so the
product can be declared GA-ready (or have a precise, owned list of what's left).

> **Interpretation note:** this round is my read of the owner's "next round (C1) — testing"
> direction. Scope below is **proposed**; trim/extend at approval.

## Objectives
1. **Demonstrate "green == shipped" on the pushed commit** — confirm the CI 3.11+3.13 matrix is
   green on `9209e3a` (the Phase-6.5 push), the way ITM-016 was demonstrated for Phase 6.
2. **Validate against a real Oracle instance (RISK-04)** — the introspection, templates, reports,
   and the SELECT-only path have never run against a live DB; do the manual UI + live-Oracle pass.
3. **Clear the pre-GA cleanups** that are pure hygiene, not features — ITM-006, ITM-007, ITM-008.
4. Produce a crisp **GA-readiness verdict**: either "ready" or an owned, prioritized residual list.

## Scope — in (subject to Decisions D-A…D-C)
- **C1-1 — CI confirmation.** Read the Actions run for `9209e3a`; record the run number + both
  legs green in the issue log (closes the ITM-016-style demonstration for Phase 6.5). *(Owner or
  a `gh`-equipped environment needed — see Risks.)*
- **C1-2 — RISK-04 live-Oracle + manual UI pass.** Against an owner-provided read-only account
  (ADR-009): connect → introspect a real schema → run a template + a saved report → export;
  walk the manual UI checklist (D6 §7) incl. the observability check (JSON logs, error_id,
  `/metrics`). Capture results; file any defects. **Owner provides the instance/credentials.**
- **C1-3 — ITM-006.** Migrate the legacy manual `connection.json` path onto encrypted profiles
  (password already not persisted since Phase-4 F5); retire the plaintext single-connection path
  or document its removal. (RISK-09.)
- **C1-4 — ITM-007.** Replace deprecated Streamlit `use_container_width=…` with `width='stretch'`
  across `st.button`/`st.dataframe`/`st.download_button` (removal scheduled post-2025-12-31).
- **C1-5 — ITM-008 (per D-C).** Optional NL-question PII scrubbing before external LLM send —
  design + gate behind a flag, or formally defer with rationale.
- **Tests + governed-doc updates in lockstep**, and an exit-gate review only for the items that
  touch code (C1-3/4/5); C1-1/C1-2 are verification, recorded not reviewed.

## Scope — out
- **No new features** — Round C1 is consolidation/testing only; Phase 7 (optional 23ai/EBS)
  remains a separate, later phase.
- **No change to the SELECT-only chokepoint or the Phase-6.5 security posture.**
- **No multi-worker/SQLite store migration** (the documented D7 single-worker constraint stands).

## Deliverables
- CI-run record for `9209e3a` (issue log) — both legs green, or a fix if not.
- A **live-Oracle test report** (`docs/reviews/` or `docs/` — location at design) covering the
  connect→introspect→template→report→export path + the manual UI/observability checklist, with
  any defects filed.
- ITM-006/007 code changes + tests; ITM-008 design (built behind a flag or formally deferred).
- Governed-doc updates (D3/D6/D7 as touched, issue log, risk register incl. **RISK-04**,
  CHANGELOG, tracker); a **GA-readiness verdict** note.

## Risks
| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| C1-R1 | No `gh` CLI / private repo → CI status can't be auto-read from the dev box | Low | Owner confirms the run in the Actions tab, or installs `gh` / provides the run URL; record the number |
| C1-R2 | No Oracle instance available → RISK-04 can't be closed this round | **Medium** | Owner provisions a read-only sandbox account (ADR-009); until then C1-2 stays open and GA-readiness is "pending live pass" |
| C1-R3 | Live pass surfaces template/SQL mismatches vs the real EBS schema (ITM-012) | Medium | Templates are review-before-run starting points; file per-template defects, fix or document |
| C1-R4 | ITM-006 migration touches the credential path | Medium | Password already session-only; changes go through the encrypted ProfileStore + tests; reviewer re-checks no plaintext at rest |

## Success criteria (round exit)
1. CI 3.11+3.13 green on `9209e3a` recorded (or remediated to green).
2. Live-Oracle + manual UI pass executed against a real instance; results recorded; defects filed
   (or RISK-04 explicitly carried with the owner's acknowledgement if no instance is available).
3. ITM-006/007 closed (code + tests); ITM-008 built-behind-flag or formally deferred.
4. Governed docs current; **RISK-04 dispositioned**; a GA-readiness verdict recorded.
5. Code-touching items pass an independent exit-gate review (reviewer ≠ author) where applicable.

## Open decisions (PENDING — owner to resolve; recommendations given)
- **D-A — RISK-04 instance.** (a) **Owner provisions a read-only Oracle sandbox now** so C1-2 runs
  this round — **[Recommended]**; (b) defer the live pass — C1 does CI + ITM-006/007/008 only and
  RISK-04 stays open into a later round. *Rec: (a) if an instance is reachable; else (b) and be
  explicit that GA is "pending live pass."*
- **D-B — Round C1 scope.** (a) **All of C1-1…C1-5** (full pre-GA consolidation) —
  **[Recommended]**; (b) testing/verification only (C1-1/C1-2), defer the ITM cleanups; (c)
  cleanups only (C1-3/4/5), defer the live pass.
- **D-C — ITM-008 (NL PII scrubbing).** (a) **Design + build behind a default-off flag** (opt-in
  redaction of the NL question before external send) — **[Recommended]**; (b) formally defer with
  the existing rationale (the question is the user's own intent; `LLM_POLICY=external_disabled`
  is the current mitigation).

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-11 | Product/Eng | Discovery charter opened after Phase 6.5 closure; bundles CI confirmation, RISK-04 live pass, and ITM-006/007/008; objectives/scope/risks/success criteria + open decisions D-A…D-C; **pending owner approval before any code.** |
