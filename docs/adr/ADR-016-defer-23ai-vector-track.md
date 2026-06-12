# ADR-016 — Defer the Oracle 23ai vector track (record direction; revisit on an instance)

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Product/Engineering (Phase 7 charter D-A, owner-approved)
- **Phase:** 7 (EBS Intelligence & 23ai)

## Context
The original plan's Phase 7 named two tracks: **EBS metadata packs** (delivered this phase,
ADR-015) and **Oracle 23ai** native AI — AI Vector Search / in-DB ML to improve NL→SQL and
surface insights. The 23ai track requires **Oracle Database 23ai**: the `VECTOR` type and
`VECTOR_DISTANCE`/AI Vector Search do not exist on the dev instance (**Oracle XE 21c**). A free
23ai instance is obtainable (23ai Free container/installer) but is new infrastructure the owner
must stand up. Shipping vector features we cannot run or test against a real 23ai would violate
the discipline that just closed RISK-04 ("no code paths unvalidated against a real DB").

## Decision
**Defer the 23ai vector track** — do not build it this phase. **Record the intended direction**
so it can be picked up cleanly, and track it as a backlog item (**ITM-018**), **not** dropped:

- **Intended capability:** semantic matching of business questions / glossary terms to schema
  objects using **AI Vector Search** over embeddings of the EBS glossary + schema metadata, to
  augment (not replace) the curated packs (ADR-015) — e.g. resolve a paraphrased term to the
  right table when no exact glossary entry exists.
- **Shape when built:** behind an explicit feature flag and a configured 23ai connection; the
  embedding/index build is an offline step; query-time vector lookups stay **SELECT-only** (read
  embeddings; never write through the reporting path). The existing redaction guarantee
  (metadata only to external models) is preserved.
- **Preconditions to revisit:** (1) an Oracle 23ai instance available for live validation, **or**
  (2) explicit customer demand. Re-open as its own chartered effort with a design + exit-gate
  review like any feature.

## Consequences
- Phase 7 ships the **testable** EBS value now (packs + glossary + `/packs` + `/v1`), with no
  untestable vector code in the tree.
- The 23ai idea is preserved and owned (ITM-018), not lost.
- No new dependency, no 23ai client/SDK, no flagged-but-dead code paths.

## Alternatives considered
- **Build it now** (charter D-A option b): rejected — requires standing up 23ai purely to test;
  the curated packs deliver most of the value testably today.
- **Drop entirely** (option c): rejected — it is a real differentiator for 23ai customers; defer
  with a recorded direction instead.

## Notes
- Tracked as **ITM-018** (issue log). EBS-template validation against real EBS remains the
  separate ITM-012.
