# D1 — Product Vision

> **Document:** Product Vision · **Version:** 1.0 · **Status:** Baseline · **Owner:** Product · **Last updated:** 2026-06-10
> **Source:** decomposed from `ask-oracle-techspec.md` §1–§2, §6 (which remains the origin spec).

## 1. Vision

Ask Oracle Reports is a **modern, AI-assisted, governed reporting layer for Oracle
Database and Oracle E-Business Suite (EBS)**. It lets business users and analysts
connect securely, ask in plain English or write SQL, and get reviewable,
exportable reports — without standing up a heavy BI platform and without leaving
IT guardrails.

**Mental model:** Connect → Ask → Review SQL → Run → Export.

## 2. Target users

- Oracle DB / EBS customers (on-prem or cloud).
- Finance, operations, HR, and supply-chain analysts underserved by BI Publisher complexity.
- Tech leads who want a lightweight, **governed "Ask" layer**, not a full BI stack.

## 3. Problem & market gap

Existing options (BI Publisher; Jasper/Crystal/Bold/Telerik; generic GPT connectors)
are either heavy to set up, not NL→SQL-focused, or not tuned to EBS schemas and the
safety constraints of production Oracle databases.

## 4. Product principles (non-negotiables)

1. **Minimal, obvious UX** — task-based menus, not BI jargon.
2. **Explainable, safe intelligence** — AI *proposes* SQL; users review/edit before running. **SELECT/CTE only; DML/DDL/PL-SQL rejected** by a single central safety layer, **backed by a required least-privilege read-only database account** (defense in depth — see [ADR-009](adr/ADR-009-readonly-db-account-precondition.md)).
3. **Oracle-centric** — tuned to Oracle SQL/PLSQL idioms and EBS schema patterns.
4. **Local/hosted LLM first, external optional** — provider abstraction; redaction for external LLMs.
5. **Secrets are secrets** — no credentials in source/logs; encrypted at rest.

## 5. Differentiators

- True NL→SQL for Oracle (not drag-and-drop designers).
- Zero schema changes; uses uploaded metadata + safe read-only connections.
- Lightweight UI for everyday questions.
- Optional Oracle 23ai (vector search / in-DB ML) integration path.

## 6. Out of scope (current)

- Write-back / data modification of any kind (permanent product guarantee, delivered by the SELECT/CTE-only safety layer **and** a required least-privilege read-only DB account — [ADR-009](adr/ADR-009-readonly-db-account-precondition.md)).
- Full pixel-perfect/embedded report design.
- Multi-tenant user accounts / RBAC (future; see [ADR-004](adr/ADR-004-per-user-llm-config.md)).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product | Baseline from techspec decomposition. |
| 1.1 | 2026-06-10 | Product | Phase 4 r1/F1: no-modification guarantee framed as defense in depth (safety layer + required read-only DB account, ADR-009). |
