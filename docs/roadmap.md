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
| 5 | **Data dictionary browser & schema tools** | ✅ Done | Searchable dictionary (where-used + export), SELECT-only introspection ([ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md)), schema persistence + `/schemas` ([ADR-011](adr/ADR-011-schema-persistence-store.md)). Closed via gate (r1 FAIL → r2 PASS-WITH-FIXES) 2026-06-10; 160 tests. |
| 6 | **Observability & Error Handling** | ✅ Done | Structured JSON logs, request/error-reference IDs, uniform DB-error sanitization (**ITM-015 closed**), in-process metrics + `/metrics`. Closed via gate (r1 PASS-WITH-FIXES → r2 PASS) 2026-06-10; 185 tests; ADR-012. r1 F-1/F-2 re-pinned the validated set to a clean-install-proven 3.13-capable config. Residual: ITM-016 (CI demo pending push). |
| 7 | Optional: Oracle 23ai & EBS enhancements | 📋 Optional | Vector search / in-DB ML; EBS metadata packs. Carries Phase-7 preconditions (CORS/auth ITM-009, base_url ITM-010, file-store ITM-013/14, non-DB error surfaces ITM-017). |

## Current focus
**Phase 6 CLOSED** (exit gate passed 2026-06-10; r1 PASS-WITH-FIXES → r2 PASS; 185 tests).
ITM-015 closed; the validated dependency set was re-pinned to a clean-install-proven
3.13-capable configuration (review F-1/F-2). **Sole open follow-up:** the owner pushes so CI
demonstrates green on both interpreter legs (ITM-016). Next feature work: **Phase 7
(optional)** — but its hard preconditions (CORS/auth ITM-009, base_url ITM-010, file-store
durability ITM-013/14, non-DB error sanitization ITM-017) gate any networked/multi-tenant
deployment. See [task-tracker](task-tracker.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Governed roadmap view; P2.5 inserted before Phase 3. |
| 1.1 | 2026-06-10 | Delivery | Phase 3 marked Done; Phase 4 progressed Discovery → Dev+Test done (exit gate pending). |
| 1.2 | 2026-06-10 | Delivery | Phase 4 CLOSED (gate passed, 130 tests); Phase 5 is next. |
| 1.3 | 2026-06-10 | Delivery | Phase 5 Discovery opened (charter awaiting owner decisions D-A…D-E). |
| 1.4 | 2026-06-10 | Delivery | Phase 5 Dev+Test done (155 tests); exit gate (R5.x) pending. |
| 1.5 | 2026-06-10 | Delivery | Phase 5 CLOSED (gate passed r1 FAIL → r2 PASS-WITH-FIXES, 160 tests); Phase 6 is next. |
| 1.6 | 2026-06-10 | Delivery | Phase 6 Discovery opened (charter awaiting owner decisions D-A…D-G). |
| 1.7 | 2026-06-10 | Delivery | Phase 6 CLOSED (gate passed r1 PASS-WITH-FIXES → r2 PASS, 185 tests); ITM-015 closed; validated set re-pinned 3.13-capable (F-1/F-2); residual ITM-016 (CI demo pending push). |
