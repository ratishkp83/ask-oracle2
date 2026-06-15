# ADR-026 — Cascading report deliverable via client-orchestrated fan-out (HTML bundle)

- **Status:** Accepted (owner sign-off 2026-06-15)
- **Date:** 2026-06-15
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 10 (B4/B5)

## Context
The product has an excellent **interactive** multi-level drill-down ([ADR-021](ADR-021-sql-aware-derivation-and-cascade.md)), but it is on-screen only and ephemeral. The end goal "**cascading reporting**" needs a **deliverable**: a parent summary that fans out into per-value child sections, narrated, that a CXO can **download or email**. Two hard constraints carry over: the **SELECT-only chokepoint** (invariant 1) and **AI-proposes / user-approves** (invariant 2), and a third — all derivation today lives in **client-side TypeScript** (`web/src/lib/derive/*`), with the established delivery pattern being "client assembles, server packages/sends" (`POST /reports/export`, `POST /reports/email`).

## Decision
Build the cascading report as a **client-orchestrated fan-out** that **reuses the TypeScript derive layer**, rendered to a **self-contained styled HTML bundle**.

- **Fan-out (`web/src/lib/cascade/bundle.ts`):** starting from the **approved** parent SQL + its result, descend the cascade's dimension order (auto-derived via `cascade.dimensionOrder`, overridable). For each **top-N** child value (ranked by the lead measure), build the child SQL with the existing `buildPullDetailSql(approvedSql, filters)` — `SELECT * FROM (<approved>) WHERE "DIM" = :v [AND …]` — and run it through the existing `/execute` chokepoint; recurse to a bounded **depth**. Residual values become a **local "Others" rollup** (no query). Every section's KPIs/chart/insights are derived **locally**.
- **Bounds (D-E):** depth (default 2), children-per-level (default top-8 + "Others"), per-child row cap (server `SafetyLimits`), and a **total-query hard cap** with visible progress; over-cap → `truncated`. A failed child is isolated with a sanitized error, never aborting the bundle.
- **Render (`renderHtml.ts`):** a single-file `<!doctype html>` with inlined token-styled CSS, inline-SVG charts, **no scripts, no external assets**, all data/identifiers HTML-escaped.
- **Deliver:** **download** = pure client Blob (no server); **email** = a **new** additive `POST /reports/email-bundle` (+`/v1`, auth-gated) reusing `send_report_email` in an HTML-document mode (all existing guards apply). The Phase-9 `EmailReportRequest` contract is left untouched.
- **Persist:** an additive `cascade: Optional[CascadeSpec]` on the `Report` model (metadata only; back-compatible) so a saved report re-runs to a fresh bundle.

## Consequences
- A genuine, sendable cascading **deliverable** that reuses the entire derive layer — no Python re-implementation, minimal new server surface (one additive endpoint + one additive model field).
- Multiple queries per bundle (bounded); each is chokepoint-validated and `SafetyLimits`-capped. The total-query cap bounds cost and bundle size.
- The bundle is a static, offline-openable file — safe to email/archive; no JS, no external calls.
- **Deferred:** **server-side fan-out** (needed for *unattended/scheduled* generation) and **native PDF/Excel** are explicit fast-follows; this ADR is the on-demand, client-orchestrated path.

## Security / invariants
- **Invariant 1:** every parent/child query is a plain `SELECT` through `/execute` or `/reports/{id}/run`; no new execution path; binds carry values (never interpolated); the NULL bucket is `IS NULL` (via `buildPullDetailSql`).
- **Invariant 2:** the user approves the **parent**; children are **deterministic, value-bound derivations** of that approved SQL (the pull-detail transformation ADR-021/022 already sanctioned) — **no new AI proposal**.
- **Invariant 3:** no LLM call is added; only SQL text + already-fetched rows are read; the bundle/insights are assembled locally; nothing is sent to a model.
- **Email egress** is the **same boundary as today's export/email** (RISK-20): user-initiated, reviewed, allow-list + audit + size cap via the unchanged mailer chokepoint. HTML-escaping defends bundle injection (P10-R6).

## Alternatives considered
- **Server-side fan-out (Python re-derives KPIs/insights/cascade):** rejected for Phase 10 — duplicates the mature TS derive layer in a second language, adds a server orchestration path, for no on-demand benefit. **Adopted as the deferred path** once scheduling (unattended generation) is chartered.
- **Extend `EmailReportRequest` instead of a new endpoint:** rejected — would mutate a Phase-9 contract + its validators (regression risk); a separate additive endpoint is cleaner to auth/test.
- **Native PDF/Excel bundle:** deferred — HTML + browser print-to-PDF meets the CXO read with no new heavy dependency (charter D-B).
- **Render charts with a JS lib in the bundle:** rejected — a deliverable must be a static, script-free file; inline SVG is deterministic and offline-safe.
