# Delivery Roadmap

> **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-10
> Authoritative phase definitions live in `ask-oracle-implementation-plan.md` (origin); this is the governed status view.

Each feature phase runs through the lifecycle micro-cycle (Discovery → Design → Development → Testing → Deployment → Iteration) and closes at a gate. **Every phase exit now requires an independent adversarial code review + QA** that iterates until it returns PASS — see the [External Review & QA Gate](process/external-review-gate.md) and [Adversarial Review & QA Prompt](process/adversarial-reviewer-prompt.md).

| Phase | Theme | Status | Gate / notes |
|-------|-------|--------|--------------|
| 1 | Productization & documentation | ✅ Done | Initial product + docs. |
| 2 | **Hardened Connectivity & Safety** | ✅ Dev+Test done | Safety layer, profiles, chokepoint, per-user LLM, 48 tests. |
| **P2.5** | **Governance baseline & Phase-2 closure** | 🔄 In progress | git + `/docs` + ADRs + CI + UI smoke + **key rotation** + sign-off. **Gate to Phase 3.** |
| 3 | NL→SQL 2.0 & LLM abstraction | 📋 Next | `LLMProvider` interface (seeded by `LLMConfig`), explanation + confidence, redaction. |
| 4 | Reports, templates & UX rework | 📋 Planned | Saved reports w/ params, EBS templates, left-nav UX. |
| 5 | Data dictionary browser & schema tools | 📋 Planned | Table/column/relationship browser. |
| 6 | Observability & error handling | 📋 Planned | Metrics, structured logs, error reference IDs. |
| 7 | Optional: Oracle 23ai & EBS enhancements | 📋 Optional | Vector search / in-DB ML; EBS metadata packs. |

## Current focus
Close **P2.5** before opening Phase 3 Discovery. Critical path: key rotation (T-07) → UI smoke (T-13) → closure sign-off (T-17). See [task-tracker](task-tracker.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Governed roadmap view; P2.5 inserted before Phase 3. |
