# D2 — Requirements (BRD / PRD)

> **Document:** Requirements · **Version:** 1.0 · **Status:** Baseline · **Owner:** Product/Engineering · **Last updated:** 2026-06-10

## 1. Business requirements (BRD)

| ID | Business requirement | Rationale |
|----|----------------------|-----------|
| BR-1 | Enable non-DBA analysts to self-serve Oracle/EBS reports safely | Reduce BI/IT backlog; avoid BI Publisher overhead |
| BR-2 | Guarantee read-only access to production databases | Protect production integrity; enterprise trust |
| BR-3 | Keep credentials and API keys confidential at all times | Security/compliance; commercial viability |
| BR-4 | Operate without requiring DBA metadata privileges | Faster adoption via uploaded metadata |
| BR-5 | Support both local/hosted and external LLMs under policy | Handle PHI/PII-sensitive customers |

## 2. Personas

- **Analyst (primary):** asks questions, reviews/edits SQL, exports results.
- **Tech lead / admin:** manages connections, sets policy, reviews safety.
- **Reviewer/QA (internal):** validates safety and contracts each phase.

## 3. Scope

**In scope (through Phase 6):** connectivity & profiles, SELECT-only execution, NL→SQL (provider-agnostic), reports/templates, data-dictionary browser, observability.
**Out of scope:** write-back, RBAC/multi-tenant accounts, pixel-perfect report design (see Vision §6).

## 4. Functional requirements & user stories (with acceptance criteria)

| ID | User story | Acceptance criteria | Status |
|----|-----------|---------------------|--------|
| FR-1 | As an analyst, I save named Oracle connection profiles. | Create/list/delete via UI+API; password encrypted at rest; never returned. | ✅ Phase 2 |
| FR-2 | As an analyst, I test a connection before using it. | `SELECT 1 FROM DUAL` round-trip; clear success/failure message; no creds leaked. | ✅ Phase 2 |
| FR-3 | As an analyst, I run only safe read queries. | Any non-SELECT (DML/DDL/PL-SQL/stacked/FOR UPDATE) rejected with a clear reason; never hits DB. | ✅ Phase 2 |
| FR-4 | As an analyst, results are bounded for responsiveness. | `MAX_ROWS`/`MAX_EXECUTION_SECONDS`/`MAX_RESULT_BYTES` enforced; `truncated` flag surfaced. | ✅ Phase 2 |
| FR-5 | As an analyst, I ask in English and get proposed SQL. | NL→SQL returns SQL + (future: explanation); never auto-executes. | ✅ (explanation: Phase 3) |
| FR-6 | As a user, I configure my own LLM provider/model/key. | Per-session override in Settings; env fallback; key never persisted/logged. | ✅ Phase 2 |
| FR-7 | As an analyst, I export results to CSV/Excel. | Download buttons produce valid CSV/XLSX of current result. | ✅ (existing) |
| FR-8 | As an analyst, I save and re-run reports. | Save SQL by name; list; re-open. | ✅ (existing, basic) |
| FR-9 | As a user, every executed query is audited without leaking data. | Audit record = source, profile, user, SQL **hash**, rows, time; no raw SQL/creds. | ✅ Phase 2 |

## 5. Non-functional requirements

| ID | NFR | Target |
|----|-----|--------|
| NFR-1 | Safety | SELECT/CTE only; fail-closed; single chokepoint. |
| NFR-2 | Security | No secrets in source/logs; profile passwords encrypted (Fernet). |
| NFR-3 | Performance | Interactive ad-hoc < 10s typical; bounded by safety limits. |
| NFR-4 | Portability | python-oracledb **thin mode** (no Oracle client install). |
| NFR-5 | Deployability | Docker Compose + Render; env-based config. |
| NFR-6 | Testability | Automated tests for safety, profiles, API; CI on every change. |

## 6. Constraints & assumptions

- Local working copy is git-initialized; GitHub remote: `ratishkp83/ask-oracle2`.
- No authentication/identity layer yet → "per-user" = per-session (see [ADR-004](adr/ADR-004-per-user-llm-config.md)).
- Schema knowledge comes from uploaded CSV/Excel metadata.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Baseline; FR/NFR captured, Phase-2 marked delivered. |
| 1.1 | 2026-06-10 | Eng | GitHub remote reference updated to `ratishkp83/ask-oracle2`. |
