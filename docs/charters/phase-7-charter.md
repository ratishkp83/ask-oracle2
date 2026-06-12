# Phase 7 Charter — EBS Intelligence & Oracle 23ai Enhancements (optional)

> **Document:** Phase Charter · **Version:** 1.2 · **Status:** 🔄 Review (build B1…B7 complete 2026-06-12, 285 tests; exit-gate review pending) · **Owner:** Product/Engineering · **Last updated:** 2026-06-12

## Lifecycle stage
**Discovery OPENED 2026-06-12.** Phases 1–6, 6.5 and Round C1 are all closed; the product is
GA-ready per [round-C1-ga-readiness.md](../round-C1-ga-readiness.md). Phase 7 is the **optional
feature phase** from the original implementation plan ("Oracle 23ai & EBS Enhancements"), whose
scope the plan explicitly left open: *"to be defined once you decide how deep to go into
EBS/23ai integration."* This charter defines that scope and puts the decisions to the owner.

## Context — grounding facts
- **The origin plan (§Phase 7)** names two tracks: (1) **OCI/23ai integration** — use Oracle AI
  Vector Search / in-DB ML for better NL→SQL and insights; (2) **EBS-aware features** —
  pre-built metadata packs for EBS modules and an **EBS glossary** (business terms →
  table/column mappings).
- **Instance constraint:** the dev box runs **Oracle XE 21c**. AI Vector Search and the `VECTOR`
  type require **Oracle Database 23ai** — they cannot run or be tested on 21c. A free 23ai
  instance is obtainable (23ai Free container image, or the 23ai Free installer), but that is
  new infrastructure the owner would have to stand up; without it, any vector feature ships
  **untested against a live DB**, which contradicts the discipline that closed RISK-04.
- **EBS track needs no new infrastructure.** Metadata packs are curated, static metadata
  (table/column descriptions, join paths, business-term glossary) feeding the existing
  `Schema` model and NL→SQL prompt context — exactly how the Phase-4 template catalog ships.
  Live-EBS validation of pack contents stays [ITM-012](../issue-log.md) regardless.
- **Why packs matter (product view):** today NL→SQL sees only schema *names* (strict
  redaction). On EBS, table names (`RA_CUSTOMER_TRX_ALL`) are opaque — a glossary mapping
  "invoice", "customer", "supplier" → real tables/joins is the single highest-leverage
  improvement for the EBS target market, and it composes with the existing redaction
  (curated **metadata**, never row data).
- **Deferred items tagged "Phase 7" elsewhere** (candidates to fold in or re-home):
  `/v1` API prefix (T-18, "before external GA"); list/multi-value binds (ITM-011); Prometheus
  exposition (ADR-012 alternative); multi-user identity (ADR-004/RISK-07); SQLite store
  (RISK-16 revisit). None are required for this phase's feature goals.
- **Non-negotiables remain in force:** SELECT/CTE-only chokepoint untouched; AI proposes,
  never runs; external prompts carry **schema names + curated metadata only** (no row data);
  secrets via env; metadata-only persistence.

## Objectives (proposed)
1. **Make NL→SQL genuinely EBS-aware:** ship curated **EBS metadata packs** (per module:
   table/column descriptions + canonical join paths) and an **EBS glossary** (business term →
   table/column mapping), loadable into the dictionary + prompt context alongside an
   introspected or uploaded schema.
2. **Decide the 23ai track deliberately:** either build a tested 23ai vector capability behind
   a feature flag (requires a 23ai instance), or formally defer it with a recorded rationale —
   no half-built untestable code.
3. Optionally retire small carried items that fit naturally (per D-D).
4. Keep everything governed: charter → owner decisions → design → build → independent
   exit-gate review.

## Scope — proposed IN (subject to D-A…D-D)
- **EBS metadata packs** (per D-B): curated JSON packs for the 5 module families already in the
  template catalog (GL/AP/AR/PO/OM) — table+column descriptions, key join paths, and glossary
  terms; shipped in-repo like templates; loaded via Schema Sources; merged into the dictionary
  browser and the NL→SQL context under the existing redaction rules.
- **Glossary surface** (per D-C): browse/search in the Data Dictionary; terms included in the
  external prompt context (metadata only).
- **23ai vector track** (per D-A): either (a) a tested, flag-gated capability (e.g. semantic
  schema/glossary search using in-DB vector similarity) against a 23ai instance, or (b) a
  **formal deferral** with a design note for later.
- **Fold-ins** (per D-D): `/v1` API prefix and/or ITM-011 multi-value binds if chosen.
- Tests + governed docs in lockstep; independent exit-gate review at close.

## Scope — explicit OUT
- **No live-data features:** packs/glossary are metadata; no row data ever enters prompts.
- **No OCI cloud-service dependency** (OCI GenAI etc.) — provider abstraction already covers
  external LLMs; cloud-specific SDK integration is a separate, later decision.
- **No multi-user identity / RBAC** (stays RISK-07/ADR-004 future).
- **No live-EBS validation** of pack contents (stays ITM-012 — needs a customer/test EBS).
- **No change to the SELECT-only chokepoint or the Phase-6.5 security posture.**

## Risks (initial)
| ID | Risk | Sev | Mitigation |
|----|------|-----|------------|
| P7-R1 | EBS pack contents wrong for a customer's EBS version/customizations | Med | Packs are curated *starting points*, review-before-run like templates; versioned per EBS 12.2 baseline; ITM-012 validation before marketing claims |
| P7-R2 | 23ai features built without a live 23ai → untestable code rots | Med | D-A forces the choice: tested-with-instance or formally deferred — nothing in between |
| P7-R3 | Glossary terms bloat the external prompt / leak something sensitive | Med | Same tripwire as schema redaction (`assert_no_values`); packs are static curated text we author; size caps in context builder |
| P7-R4 | Scope creep (packs → full semantic layer) | Med | Charter fixes the envelope: 5 module families, glossary as flat term→mapping, no inference engine |

## Success criteria (phase exit, to finalize at design)
1. EBS packs load + merge into dictionary and NL→SQL context; measurably better SQL on
   EBS-style questions (worked examples in tests, mocked LLM).
2. Glossary browsable in the UI; external context passes the redaction tripwire with packs on.
3. 23ai track either demo-tested against a real 23ai (flag-gated) or formally deferred.
4. Suite green on 3.11+3.13; docs/ADRs current; independent review PASS.

## Open decisions (PENDING — owner to resolve; recommendations given)
- **D-A — 23ai vector track.**
  (a) **Defer formally this phase** — record the design direction, revisit when a 23ai
  instance (or customer demand) exists — **[Recommended]**;
  (b) Build flag-gated vector features now — **requires the owner to stand up Oracle 23ai
  Free** (container or installer) for live testing;
  (c) Drop from the roadmap entirely.
  *Recommendation: (a)* — the EBS track is the higher-value, testable work; 23ai stays a
  deliberate fast-follow.

- **D-B — EBS pack breadth.**
  (a) **All 5 template module families (GL/AP/AR/PO/OM), core tables only** (~10–20 tables
  each, descriptions + key joins + terms) — **[Recommended]**;
  (b) Start with 2 modules (GL/AP) deeper;
  (c) One pilot module.
  *Recommendation: (a)* — matches the template catalog surface users already see.

- **D-C — Glossary mutability.**
  (a) **Read-only curated packs this phase** (users can already upload their own schema CSVs)
  — **[Recommended]**;
  (b) User-editable glossary with persistence (new store + CRUD + UI — bigger).
  *Recommendation: (a)* — ship value first; editability is a clean later increment.

- **D-D — Fold-ins.**
  (a) **Add the `/v1` API prefix (T-18) this phase** (cheap, additive with back-compat
  mounting, was flagged "before external GA") — **[Recommended]**;
  (b) Also ITM-011 multi-value binds;
  (c) No fold-ins — packs/glossary only.
  *Recommendation: (a)* — T-18 closes the last "before GA" note; ITM-011 only if a pack
  report actually needs list binds.

## Decisions (resolved 2026-06-12)
Owner resolved all four as recommended:
- **D-A — 23ai vector track:** ✅ **Defer formally** — record the design direction; revisit when a
  23ai instance or customer demand exists. (Phase 7 ships the EBS track; 23ai becomes a tracked
  fast-follow item, **not** dropped.)
- **D-B — EBS pack breadth:** ✅ **All 5 module families (GL/AP/AR/PO/OM), core tables only** —
  matches the template catalog surface.
- **D-C — Glossary mutability:** ✅ **Read-only curated packs this phase** (users can still upload
  their own schema CSVs); editable glossary is a later increment.
- **D-D — Fold-ins:** ✅ **Add the `/v1` API prefix (T-18)** this phase (additive, back-compat
  mount). ITM-011 multi-value binds **not** folded in (only if a pack report needs it).

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-12 | Product/Eng | Discovery charter opened — scope proposal for the optional Phase 7 (EBS metadata packs + glossary as primary track; 23ai vector as a decide-deliberately track; optional fold-ins); decisions D-A…D-D; **pending owner approval before any code.** |
| 1.1 | 2026-06-12 | Product/Eng | Owner resolved D-A (defer 23ai, tracked fast-follow), D-B (all 5 modules, core tables), D-C (read-only curated), D-D (fold in `/v1` T-18; not ITM-011). Discovery → Design. |
| 1.2 | 2026-06-12 | Product/Eng | Design approved → build **B1…B7 complete** (285 tests; ADR-015/016; **T-18 CLOSED**; ITM-018 logged). Next: R7.2 independent exit-gate review (reviewer ≠ author, owner-supplied). |
