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
| T-10 | `git init` + baseline commit (`.env` ignored) | 🔄 In Progress | local identity set; **user pushes to GitHub** |
| T-09 | Promote governed `/docs` set into repo | ✅ Completed | this batch |
| T-14 | Record ADR-001…005 | 🔄 In Progress | see `docs/adr/` |
| T-15 | Seed CHANGELOG + registers + trackers | ✅ Completed | this batch |
| T-16 | Add CI workflow (pytest) | 🔄 In Progress | `.github/workflows/ci.yml` |
| T-13 | Phase-2 manual UI smoke test | 📋 Planned | checklist in test-strategy |
| T-07 | **Rotate leaked Groq/OpenAI keys** | ⛔ Blocked (user) | external; RISK-01 |
| T-17 | Phase-2 closure sign-off record | 📋 Planned | gate to start Phase 3 |

## Backlog (next phases)

| ID | Task | Phase | Status |
|----|------|-------|--------|
| T-12 | LLM provider abstraction (`LLMProvider`) + explanation/confidence | Phase 3 | 📋 Planned (seeded by T-05) |
| T-18 | API `/v1` versioning prefix | Phase 3/4 | 📋 Planned |
| T-19 | Migrate legacy `connection.json` → encrypted profiles | Phase 2 follow-up | 📋 Planned (RISK-09) |
| T-20 | Saved reports: profile binding + parameters | Phase 4 | 📋 Planned |

## Dependencies & critical path

- **T-07 (key rotation)** gates any external deployment.
- **T-13 + T-17** gate the Phase-2 → Phase-3 transition.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial tracker; Phase-2 delivered, P2.5 in progress. |
