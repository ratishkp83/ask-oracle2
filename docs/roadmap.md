# Delivery Roadmap

> **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-10
> Authoritative phase definitions live in `ask-oracle-implementation-plan.md` (origin); this is the governed status view.

Each feature phase runs through the lifecycle micro-cycle (Discovery → Design → Development → Testing → Deployment → Iteration) and closes at a gate. **Every phase exit now requires an independent adversarial code review + QA** that iterates until it returns PASS — see the [External Review & QA Gate](process/external-review-gate.md) and [Adversarial Review & QA Prompt](process/adversarial-reviewer-prompt.md).

| Phase | Theme | Status | Gate / notes |
|-------|-------|--------|--------------|
| 1 | Productization & documentation | ✅ Done | Initial product + docs. |
| 2 | **Hardened Connectivity & Safety** | ✅ Dev+Test done | Safety layer, profiles, chokepoint, per-user LLM, 48 tests. |
| **P2.5** | **Governance baseline & Phase-2 closure** | 🔄 In progress | git + `/docs` + ADRs + CI + UI smoke + **key rotation** + sign-off. **Gate to Phase 3.** |
| 3 | NL→SQL 2.0 & LLM abstraction | ✅ Done | `LLMProvider` interface, explanation + confidence, strict redaction. Closed via gate (r2 PASS-WITH-FIXES) 2026-06-10. |
| 4 | **Reports, Templates & UX** | ✅ Done | Saved reports w/ bind params + profile binding, 13 EBS templates (GL/AP/AR/PO/OM), left-nav UX. Closed via gate (r1 PASS-WITH-FIXES) 2026-06-10; 130 tests. F1→read-only-account precondition ([ADR-009](adr/ADR-009-readonly-db-account-precondition.md)). |
| 5 | **Data dictionary browser & schema tools** | 🔄 Discovery | Charter [open](charters/phase-5-charter.md) 2026-06-10 — **decisions pending owner approval**. Searchable table/column/relationship browser; optional SELECT-only introspection + schema persistence. |
| 6 | Observability & error handling | 📋 Planned | Metrics, structured logs, error reference IDs. |
| 7 | Optional: Oracle 23ai & EBS enhancements | 📋 Optional | Vector search / in-DB ML; EBS metadata packs. |

## Current focus
**Phase 5 Discovery** — charter [open](charters/phase-5-charter.md) and awaiting owner
approval + decisions (D-A…D-E) before any code. See [task-tracker](task-tracker.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Governed roadmap view; P2.5 inserted before Phase 3. |
| 1.1 | 2026-06-10 | Delivery | Phase 3 marked Done; Phase 4 progressed Discovery → Dev+Test done (exit gate pending). |
| 1.2 | 2026-06-10 | Delivery | Phase 4 CLOSED (gate passed, 130 tests); Phase 5 is next. |
| 1.3 | 2026-06-10 | Delivery | Phase 5 Discovery opened (charter awaiting owner decisions D-A…D-E). |
