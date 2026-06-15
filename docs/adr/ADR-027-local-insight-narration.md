# ADR-027 — Local, deterministic insight narration (no LLM, no row egress)

- **Status:** Accepted (owner sign-off 2026-06-15)
- **Date:** 2026-06-15
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 10 (B3)

## Context
The end goal's "**fully intelligent**" axis asks the product to do more than render a result — to say **what's notable** about it ("Engineering leads salary at $375.0K — 47% of the total"). The hard constraint is **invariant 3**: never send row or cell data (or aggregates derived from them) to any model. We also must not erode trust with a wrong or over-claimed "insight."

## Decision
Compute insight narration **100% locally and deterministically** from the already-fetched result — **no LLM, no network**, consistent with the existing local derive layer ([ADR-021](ADR-021-sql-aware-derivation-and-cascade.md)).

- **`web/src/lib/derive/insight.ts`** — `deriveInsights(cols, rows, sqlMeta, opts)` returns a ranked, capped set of `Insight { kind, text, measure?, basis, confidence }`. Fact templates, each emitted **only when a threshold is met**: **total** (lead-measure fold using the measure's exact aggregation — AVG framed honestly as "average across N groups"), **top** value, **concentration** (top-1/top-3 share), **trend** (only with an ordered date/time dimension; first→last % change; never causal), **spread** (min/max group), **coverage** (null/"—" share). Conservative thresholds suppress noise; low-confidence items are dropped; the function **never throws** (degrades to `[]`).
- **Surfacing (D-H):** an **Insight band** above the KPI cards in `ResultsView`, and the same engine embedded per section in the cascade bundle (ADR-026).
- **LLM phrasing is explicitly deferred** (charter D-F): even *phrasing* locally-computed aggregates via an LLM would put result-derived numbers on the wire; that is a separate, opt-in future increment.

## Consequences
- Immediate "intelligent" value on **every** result (not just bundles), shipped in the first packet (B3), with **zero** invariant-3 exposure.
- Insights are explainable (each carries a factual `basis`) and reproducible (deterministic) — auditable, unlike free-form LLM prose.
- The trade-off is breadth: templates cover common executive facts (lead, concentration, trend, spread, coverage), not open-ended analysis. That is the intended conservative scope for a trust-sensitive CXO product.

## Security / invariants
- **Invariant 3:** reads only local column/SQL metadata + the rows already in the browser; **sends nothing to any model or network**. No aggregate, label, or value leaves the client.
- **Trust (P10-R4):** facts only, no causal claims; thresholds + confidence gating prevent flimsy or misleading statements; fully unit-tested on fixtures (emit-vs-suppress at each threshold).

## Alternatives considered
- **LLM-generated narrative from the result:** rejected — violates invariant 3 (row/aggregate egress), adds latency/cost/nondeterminism, and is unauditable. Deferred behind an explicit opt-in if ever pursued (charter D-F).
- **No narration (KPIs only):** rejected — leaves the "intelligent" half of the end goal unaddressed; the deterministic band is a low-risk, high-signal middle path.
