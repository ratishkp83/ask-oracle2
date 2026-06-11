# Delivery Roadmap

> **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-11
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
| 6 | **Observability & Error Handling** | ✅ Done | Structured JSON logs, request/error-reference IDs, uniform DB-error sanitization (**ITM-015 closed**), in-process metrics + `/metrics`. Closed via gate (r1 PASS-WITH-FIXES → r2 PASS) 2026-06-10; 185 tests; ADR-012. r1 F-1/F-2 re-pinned the validated set to a clean-install-proven 3.13-capable config; pushed, CI green on 3.11 + 3.13 (ITM-016 closed). |
| **P6.5** | **Pre-deployment hardening (carried preconditions)** | 🔄 Dev+Test done | Opt-in API-key auth + env-driven CORS (ADR-013), base_url encoding fix, atomic store writes + corrupt-record quarantine (ADR-014), non-DB error surfaces routed. **ITM-009/010/013/014/017 CLOSED; RISK-12 Closed/RISK-16 Mitigating; 236 tests.** Exit gate (R6.5.x) pending — **gate to Phase 7 / any networked deploy.** |
| 7 | Optional: Oracle 23ai & EBS enhancements | 📋 Optional | Vector search / in-DB ML; EBS metadata packs. Gated on **P6.5 closure** (its former preconditions) + RISK-04 (pre-GA live-Oracle pass). |

## Current focus
**Phase 6.5 — Pre-Deployment Hardening: build B1…B6 COMPLETE 2026-06-11 (236 tests).** All five
carried preconditions closed in code + registers (ITM-009/010/013/014/017; RISK-12 Closed,
RISK-16 Mitigating). **Next: the R6.5.x independent exit-gate review** (reviewer ≠ author,
owner-supplied) → PASS → close P6.5. Phase 7 (optional: 23ai/EBS) opens only after P6.5 closes;
RISK-04 (live-Oracle pass) stays a separate owner-scheduled pre-GA activity. See
[task-tracker](task-tracker.md).

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
| 1.8 | 2026-06-11 | Delivery | Phase 6.5 (pre-deployment hardening) Discovery opened — bundles ITM-009/010/013/014/017; row inserted; Phase-7 gate re-expressed as "P6.5 closure + RISK-04". |
| 1.9 | 2026-06-11 | Delivery | Phase 6.5 Dev+Test done (236 tests; all five ITMs closed; ADR-013/014); exit gate (R6.5.x) pending. |
