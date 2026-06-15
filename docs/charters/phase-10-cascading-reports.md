# Phase 10 Charter — Cascading Report Deliverables + Local Insight Narration (v2)

> **Document:** Phase Charter · **Version:** 1.1 · **Status:** 🟢 **Approved by owner (2026-06-15)** — D-A…D-H all resolved; **Design (B2) next** · **Owner:** Product/Engineering · **Last updated:** 2026-06-15

> **End goal this phase advances:** *"fully intelligent + cascading reporting."* The product today is excellent at **single-shot answer + interactive drill-down**. Phase 10 delivers the **cascading** half as a real, sendable **deliverable**, plus a low-risk slice of **intelligence** — **local, deterministic insight narration** — so those deliverables *read* like a CXO report. Conversational Ask, a semantic/metrics layer, scheduling, and LLM-phrased insight are deliberately deferred to later phases.

## Lifecycle stage
**Discovery OPENED 2026-06-15** on the **v2 branch** (`D:\Ratish\Personal\Project\ask-oracle-reports-main v2`, junction `…\aor-v2`, branch `v2`; **local commits only, no push** until the July limit reset). Phase 9 (React CXO UI) is CLOSED; ITM-034 closed. This is the next v2 feature. **No code until this charter is signed off** (review-gate at every checkpoint; independent adversarial exit-gate at close, reviewer ≠ author per ADR-006).

## Context — grounding facts (verified in the code, 2026-06-15)
- **What exists:** the React CXO surface (`web/`) does NL→SQL → editable review → run → executive results (`ResultsView`), with a **multi-level interactive drill-down** that is **client-side and ephemeral**: `web/src/lib/derive/cascade.ts` (`dimensionOrder` from GROUP BY; `filterRows` ANDs the drill stack), `pickChart`/`chartForDim` re-scope per level, and `ResultsView` holds a `DrillLevel[]` stack with a breadcrumb and a **pull-detail leaf** (`web/src/lib/derive/pullDetail.ts` wraps the approved SQL as `SELECT * FROM (<approved>) WHERE "DIM" = :v`, re-approved, run via the chokepoint).
- **All derivation is TypeScript + local/deterministic** (`web/src/lib/derive/*` — columns/kpis/chart/sql-aware/cascade/pullDetail). **No row data ever goes to any LLM** (invariant 3).
- **Delivery pattern already in place:** the client assembles a result and the server just packages/sends it — `POST /reports/export` (server-side CSV/xlsx via openpyxl) and `POST /reports/email` (the Phase-8 mailer over HTTP; client posts the exact `columns`+`rows` shown; **no LLM, no re-query**; allow-list + header-injection guard + size cap + audit). Client-side CSV export is a pure Blob download.
- **The SQL chokepoint** is `src/db.py` `run_select` ← `assert_safe_select` (`core/sql_safety.py`), reached only via `POST /execute` and `POST /reports/{id}/run`; `SafetyLimits` caps rows/time/size.
- **Saved reports** (`src/core/reports.py`, `Report` v2 model) carry `sql` + typed bind `parameters[]`; runs go through the chokepoint.
- **Greenfield (confirmed absent anywhere):** query history, insight/narrative/anomaly logic, scheduling/cron, a semantic/metrics layer. So both end-goal words map to genuinely un-built capability; Phase 10 takes the **cascading-deliverable** gap + the **local-insight** slice.
- **The gap, precisely:** the interactive drill-down is an on-screen *interaction*; a **cascading report** is a *deliverable* — a parent summary that fans out into per-value child sections, narrated, that you can **download or email**. That artifact does not exist today.

## Non-negotiables (the five invariants — must not regress)
1. **SELECT/CTE-only chokepoint** — unchanged. Every cascade child query is a normal `POST /execute` (a re-validated SELECT). No new SQL-execution path is introduced.
2. **AI proposes / user approves** — preserved. The user approves the **parent** SQL (in the Ask review, or it is the saved report's already-approved `sql`). Cascade **children are deterministic, value-bound derivations of that approved parent** (`SELECT * FROM (<approved>) WHERE "DIM" = :v …`) — the exact transformation today's drill-down / pull-detail already performs (ADR-021/022 precedent). **No new AI proposal is generated for children.**
3. **Schema-names-only to the LLM** — preserved. Insight narration is computed **100% locally from the already-fetched result** (no rows, no aggregates, to any model). No LLM call is added on any Phase-10 path.
4. **No client-side DB secrets** — preserved. Connections by `profile_id`; the bundle carries result data the user already saw, never credentials.
5. **Sanitized errors with `error_id`** — preserved; all new surfaces route through the existing `friendlyError`/`errorMessage` + `_db_error` policy (ADR-024).

## Objectives
1. From a run result (or a saved report), generate a **cascading report**: a styled **HTML bundle** — parent summary + narrated KPIs + **nested per-value child sections** drilling the dimensions — matching the React executive design (premium look, tabular numerals).
2. Make it a **deliverable**: **download** the bundle (client-side) and **email** it (reusing the Phase-8 mailer + its allow-list / audit / size cap).
3. Add **local insight narration** — a conservative, deterministic "what's notable here" band — to both normal results and the bundle, with **no LLM and no row egress**.
4. Let a user **"Save as cascading report"** — persist the cascade spec (dimension order, depth, caps) on the Report model (additive) so it re-runs to a fresh bundle.
5. Keep it governed: charter → owner decisions → design (ADR-026/027) → build B1…Bn (each review-gated + HOLD-for-sign-off) → independent exit-gate review (reviewer ≠ author).

## Resolved decisions (owner, 2026-06-15)
| # | Decision | Choice |
|---|----------|--------|
| D-A | Phase lead | **Cascading deliverable (Direction C) + the local slice of insight narration (Direction B-local).** Conversational/self-healing Ask (A) and the semantic/metrics layer (D) are deferred to later phases. |
| D-B | Deliverable format | **Styled HTML bundle** — a self-contained, premium HTML document matching the React executive tokens; emailable inline AND downloadable; user can print-to-PDF from the browser. **No new heavy dependency.** (Excel / native PDF deferred.) |

## Decisions D-C…D-H — **RESOLVED: approved as recommended (owner, 2026-06-15)**
| # | Decision | Options | Resolved (= recommendation) |
|---|----------|---------|----------------|
| D-C | **Cascade spec source** | (a) auto-derive dimension order from GROUP BY (zero config); (b) explicit, user-chosen order; (c) **auto-derive default + optional override** | **(c)** — consistent with the existing deterministic derivation; zero-effort default, full control when wanted. |
| D-D | **Execution model** | (a) **client-orchestrated fan-out reusing `derive/*`** — client runs parent + children via `/execute`, assembles the bundle; download is pure client-side; **email extends the existing mailer endpoint** to accept the prebuilt HTML; (b) server-side fan-out (Python re-implements derivation) | **(a)** — reuses the rich TS derive layer (no Python port), keeps the chokepoint the only SQL path, matches the existing "client assembles, server packages/sends" pattern. **Server-side fan-out is the fast-follow when scheduling is chartered** (a scheduler needs unattended server execution). |
| D-E | **Fan-out bounds** | depth / children-per-level / rows-per-child | **Default depth 2** (configurable), **top-8 children per level by the lead measure + an "Others" rollup**, **per-child row cap = `SafetyLimits` default**, and a **hard cap on total queries** with a visible progress + the option to widen. Bounds cost, file size, and email limits. |
| D-F | **Insight narration scope** | (a) **100% local/deterministic templates (no LLM)**; (b) allow LLM to *phrase* locally-computed aggregates | **(a)** — preserves invariant 3 with zero ambiguity; conservative, explainable facts only. LLM-phrasing is a deliberate later increment behind an explicit opt-in. |
| D-G | **Delivery channels** | download / email / both | **Both** — client-side Blob **download**; **email** via the extended mailer (allow-list + audit + size cap apply, same data-egress boundary as today's export/email). |
| D-H | **Insight band placement** | bundle only / also on the live results view | **Both** — show the local insight band on the normal `ResultsView` too, so the "intelligent" value lands immediately on every result, not just in a bundle. |

## Scope — proposed IN (subject to D-C…D-H)
- **Insight engine** `web/src/lib/derive/insight.ts` — pure/local/deterministic: ranks notable facts from a result (lead-measure totals, **top mover / concentration / share**, **trend** when a date dimension is present, simple **outliers**, null/coverage notes), emitting a short ranked set of plain-language lines. Conservative (no causal claims); hidden when low-confidence. Unit-tested against fixtures. Rendered as an **Insight band** in `ResultsView` (D-H) and embedded in the bundle.
- **Cascade bundle assembler** `web/src/lib/cascade/bundle.ts` + a styled HTML template — given the approved parent SQL + the parent result + a cascade spec, **orchestrate the fan-out** (children = `pullDetail`-style value-bound derivations via `/execute`, bounded by D-E), and assemble a **self-contained styled HTML document**: parent summary → narrated KPIs → driver chart (static/SVG) → **nested child sections** (each its own mini summary + narration + table), with a contents/breadcrumb. Inline CSS from the design tokens; no external assets. Verified single-file (opens offline).
- **Download** — assemble client-side, Blob download (no server round-trip), mirroring the existing client CSV export.
- **Email** — extend `POST /reports/email` (and `/v1`) to accept a **prebuilt HTML bundle** as the email body/attachment, reusing `send_report_email` (allow-list, header-injection guard, size cap, audit, `SendResult`→HTTP). **No LLM, no re-query** on this path.
- **"Save as cascading report"** — additive `cascade` field on the `Report` model (`{ dimension_order[], depth, children_per_level, … }`), persisted via the existing `ReportStore`; a saved cascading report re-runs (parent through the chokepoint, then the bounded fan-out) to a fresh bundle. Back-compatible (absent `cascade` = a normal report; on-disk shape additive).
- **Tests + governed docs in lockstep** — vitest for the insight engine, the fan-out orchestrator (mocked `/execute`), the bundle assembler (single-file/escaping/caps), and the email-bundle path; backend tests for the extended email endpoint; **ADR-026** (cascading report deliverable + client-orchestrated fan-out) and **ADR-027** (local insight narration); CHANGELOG/HANDOFF/issue-log/risk-register/roadmap updated; **complete product test** + independent exit-gate review at close.

## Scope — explicit OUT (deferred, each a clean later phase)
- **No conversational / multi-turn Ask and no SQL self-repair** (Direction A — a later "intelligent depth" phase; would pair with query-history persistence).
- **No semantic/metrics layer** (Direction D).
- **No scheduling / unattended / recurring delivery** — collides with RISK-16 (single-worker) + ITM-019 (ephemeral storage); needs durable state + the server-side fan-out path (D-D fast-follow). On-demand only this phase.
- **No LLM-phrased insight and no AI-drafted narrative** (would brush invariant 3; D-F defers it behind an explicit opt-in).
- **No native PDF or Excel bundle** this phase (HTML + browser print-to-PDF covers the CXO read; Excel/PDF are additive later).
- **No query-history persistence and no dynamic Ask chips (ITM-026)** — not required by this scope.
- **No change to the SELECT-only chokepoint or the security posture.**

## Architecture sketch
```
Ask review / saved report
  └─ approved parent SQL  ──run──▶  /execute (chokepoint)  ──▶  parent result (columns+rows)
        │
        ▼  client orchestrator (web/src/lib/cascade/bundle.ts), bounded by the cascade spec
   for each top-N child value in dim[0]:  SELECT * FROM (<approved>) WHERE "dim0"=:v   ──▶ /execute
        for each child value in dim[1]:   … AND "dim1"=:v2                              ──▶ /execute   (depth ≤ D-E)
        │
        ▼  derive/* (KPIs, chart, insight.ts) per section — all LOCAL, no LLM
   assemble styled single-file HTML bundle
        ├─ download  → client Blob (no server)
        └─ email     → POST /reports/email (HTML body, reuse mailer: allow-list + audit + size cap)
```
Every SQL hop is the existing chokepoint; every child is a deterministic derivation of the approved parent; no LLM call anywhere in the phase.

## Build plan (each packet: build → gates → internal review → present → **HOLD for owner sign-off**)
- **B1 — Charter** (this doc) → owner sign-off. *(Gate to B2.)*
- **B2 — Design + ADRs** (`docs/cascading-reports-design.md`, ADR-026/027; RISK entries) → owner approval **before** code.
- **B3 — Insight engine** `insight.ts` + the **Insight band** in `ResultsView` (D-H) — immediate, standalone intelligence value; fully unit-tested; live-verified vs XE.
- **B4 — Cascade fan-out + HTML bundle assembler** (`bundle.ts` + template) with the D-E bounds + **download**; verified single-file, premium look, live vs XE.
- **B5 — Delivery + persistence** — extend the mailer endpoint for the HTML bundle (email); **"Save as cascading report"** (additive `cascade` field) + run-a-saved-cascading-report; live send verified (recipient-confirmed).
- **B6 — Docs sweep + complete product test + independent exit-gate review** (reviewer ≠ author) → remediate → **Phase 10 CLOSED.**

## Risks (initial — promoted to the register at design)
| ID | Risk | Sev | Mitigation |
|----|------|-----|------------|
| P10-R1 | **Query fan-out cost/latency** — a wide/deep cascade fires many child queries | Med | D-E bounds (depth + top-N + "Others" + per-child row cap + total-query hard cap); visible progress; each child still chokepoint-capped by `SafetyLimits`. |
| P10-R2 | **Data egress via emailed bundle** — user emails sensitive output externally | Med-High | **Same boundary as today's export/email**; reuse `EMAIL_ALLOWED_DOMAINS` allow-list + audit log + size cap; user-initiated + reviewed; opt-in mailer. |
| P10-R3 | **Invariant-2 perception** — "the app is running SQL the user didn't type" | Low | Children are **deterministic, value-bound derivations of the *approved* parent** via the existing chokepoint (pull-detail precedent); documented in ADR-026; no new AI proposal. |
| P10-R4 | **Insight credibility** — a wrong/:overclaimed narrative erodes trust | Med | Conservative deterministic templates; facts only, **no causation**; show the basis; hide when low-confidence; fully unit-tested on fixtures. |
| P10-R5 | **Bundle size / email limits** — large cascade → big HTML / Gmail reject | Low-Med | Per-child row caps + a bundle size cap with a clear warning; reuse the mailer's byte cap + clean reject surfacing. |
| P10-R6 | **HTML injection in the bundle** — result values rendered into HTML | Med | Strict HTML-escaping of all data/identifiers in the template; inline CSS only; no external/script content; tested with adversarial cell values. |
| P10-R7 | **Scope creep** into scheduling / LLM-phrasing / PDF / semantic layer | Low | All explicitly OUT; each a separately chartered later phase. |

## Success criteria (phase exit — finalized at design)
1. From a run result **or** a saved report, the user generates a **cascading report** — parent summary + narrated KPIs + **nested per-value child sections** — as a **styled, single-file HTML bundle** matching the executive design; **downloadable** and **emailable**.
2. Cascade dimension order **auto-derived (GROUP BY) with optional override**; **bounded** (depth + top-N children + "Others" + per-child row caps + total-query cap); **every child query runs through the SELECT-only chokepoint** as a deterministic derivation of the **approved** parent (no new AI proposal).
3. **Local insight narration** appears on the live results view (D-H) and in the bundle, computed **100% locally** (no rows/aggregates to any LLM); conservative + explainable.
4. **"Save as cascading report"** persists the cascade spec on the Report model (**additive, back-compatible**); a saved cascading report re-runs to a fresh bundle.
5. **All five invariants hold**; gates green (**pytest · vitest · tsc · vite build**); ADR-026/027 + governed docs current; **independent exit-gate review = PASS** (reviewer ≠ author).
6. Verified **live vs XE `AOR_DEMO`** end-to-end (generate → download → email a real bundle, recipient-confirmed); **no scheduling, no LLM-phrased insight, no PDF/Excel, no semantic layer** (all OUT/deferred).

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-15 | Product/Eng | Discovery charter drafted (v2 / Phase 10) — cascading report deliverables + local insight narration. **D-A** (lead = cascading deliverable + local insight) and **D-B** (styled HTML bundle) resolved by owner. D-C…D-H recommended, pending sign-off. Conversational Ask, semantic layer, scheduling, LLM-phrased insight, PDF/Excel all explicitly OUT. **No code until this charter is approved.** |
| 1.1 | 2026-06-15 | Product/Eng | **Charter APPROVED by owner** — D-C…D-H accepted as recommended (auto-derive+override; client-orchestrated fan-out reusing `derive/*`; depth-2/top-8/"Others"/row-caps; 100%-local insight; download+email; insight band on live results + bundle). Status 🟢; **B2 (design + ADR-026/027) next** for a second sign-off before feature code. |
