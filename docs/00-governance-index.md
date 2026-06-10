# Ask Oracle Reports — Documentation Governance Index

> **Document:** Governance Index · **Version:** 1.0 · **Status:** Baseline · **Owner:** Delivery Lead · **Last updated:** 2026-06-10

This `/docs` tree is the **single source of truth** for the product. Every change
to behaviour, contracts, or scope must be reflected here in the same change set
as the code, before the work is considered complete.

## Document set

| ID | Document | Path | Status |
|----|----------|------|--------|
| D1 | Product Vision | [01-product-vision.md](01-product-vision.md) | Baseline |
| D2 | Requirements (BRD/PRD) | [02-brd-prd.md](02-brd-prd.md) | Baseline |
| D3 | Architecture | [03-architecture.md](03-architecture.md) | Baseline |
| D4 | Data Models | [04-data-models.md](04-data-models.md) | Baseline |
| D5 | API Contracts | [05-api-contracts.md](05-api-contracts.md) | Baseline |
| D6 | Test Strategy | [06-test-strategy.md](06-test-strategy.md) | Baseline |
| D7 | Deployment Plan | [07-deployment-plan.md](07-deployment-plan.md) | Baseline |
| D8 | Change Log | [CHANGELOG.md](CHANGELOG.md) | Living |
| D9 | Decision Log (ADRs) | [adr/](adr/) | Living |
| D10 | Risk Register | [risk-register.md](risk-register.md) | Living |
| D11 | Task Tracker | [task-tracker.md](task-tracker.md) | Living |
| D12 | Issue / Bug Log | [issue-log.md](issue-log.md) | Living |
| D13 | Traceability Matrix | [traceability-matrix.md](traceability-matrix.md) | Living |
| — | Delivery Roadmap (7 phases) | [roadmap.md](roadmap.md) | Living |
| — | Phase-2 Review & QA | [ask-oracle-review-phase-2.md](ask-oracle-review-phase-2.md) | Closed |

## Process & gates

| Doc | Purpose | Path |
|-----|---------|------|
| External Review & QA Gate | Mandatory independent review + QA at every phase exit; iterate-until-PASS loop | [process/external-review-gate.md](process/external-review-gate.md) |
| Adversarial Review & QA Prompt | Reusable red-team prompt handed to the independent reviewer each phase | [process/adversarial-reviewer-prompt.md](process/adversarial-reviewer-prompt.md) |
| Review outputs | One file per review iteration: `docs/reviews/phase-<N>-review-r<n>.md` | `reviews/` (created at first review) |

> **Phase exit gate:** a phase is not "closed" until it passes an **independent adversarial code review + QA** (reviewer ≠ author). See the gate doc for the full Definition of Done.

## Document control conventions

- **Every doc** carries a control header (version, status, owner, last updated) and a **Revision history** table at the bottom.
- **Status legend:** `Draft` → `Baseline` (approved, current) → `Superseded`. *Living* docs (CHANGELOG, ADRs, registers, trackers) are appended continuously.
- **Versioning:** semantic-ish — minor bump for additive edits, major bump for breaking/scope changes. The git commit is the authoritative version record.
- **Change discipline:** code + docs change together in one commit; the CHANGELOG entry references the commit/phase.

## Status legend (trackers)

`Planned` · `In Progress` · `Blocked` · `Completed` · `Accepted` (risks/issues knowingly not actioned).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial governance baseline (P2.5). |
