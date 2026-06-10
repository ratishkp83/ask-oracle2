# ADR-006 — Independent adversarial review & QA gate (effective Phase 3)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product owner, Delivery

## Context
A mandatory independent adversarial code review + QA was added as a phase-exit
gate (see [external-review-gate](../process/external-review-gate.md)) *after*
Phase 2 had already closed under author-only review. We had to decide whether to
retro-apply it to Phase 2 or start it at Phase 3, and who performs the review
(the assistant authored the Phase 2/3 code, so it cannot be the independent
reviewer).

## Decision
The gate is **effective from Phase 3 onward**. **Phase 2 remains closed** under
author-only review (grandfathered). The **independent reviewer is supplied
externally by the product owner** (a fresh reviewer agent), satisfying the
reviewer-≠-author rule for all gated phases.

## Consequences
- Phase 2 carries an accepted gap: no independent review ([RISK-10](../risk-register.md)). Mitigated by strong automated coverage (51 tests across safety, secrets, profiles, endpoints, and UI smoke).
- Every phase from 3 onward must pass an independent adversarial review/QA (iterate-until-PASS) before closing.
- Clean separation of duties: the assistant builds; the owner's reviewer agent reviews.

## Alternatives considered
- **Retro-review Phase 2 now:** more rigor, but delays Phase 3 for an already-closed, well-tested phase.
- **Assistant self-review:** rejected — not independent; defeats the gate's purpose.
