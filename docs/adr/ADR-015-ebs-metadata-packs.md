# ADR-015 — EBS metadata packs as curated, redaction-safe NL→SQL overlays

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Product/Engineering (Phase 7 charter D-B/D-C, owner-approved)
- **Phase:** 7 (EBS Intelligence & 23ai)

## Context
NL→SQL on E-Business Suite is hampered by opaque table names (`RA_CUSTOMER_TRX_ALL`,
`AP_INVOICES_ALL`). The model sees schema **names** only (strict redaction — external prompts
carry no row data). To generate good EBS SQL it needs *business meaning*: which table is "the
invoice", how tables join, what a "ledger" is. The `Schema` model
(`src/schema.py`) carries structure only — **no description or glossary fields** — and is under a
metadata-only persistence contract (Phase-5 F-1). We need EBS knowledge **without** mutating that
contract or weakening the redaction guarantee.

## Decision
Ship **curated EBS metadata packs** as a separate, additive overlay
(`src/core/ebs_packs.py`) — the same pattern as the Phase-4 template catalog (curated pydantic
models in an in-repo list, read-only). Per module family (GL/AP/AR/PO/OM):
- `TableNote` — table description, key columns, canonical join hints (`A.col -> B.col`).
- `GlossaryTerm` — business term → table(+column) mapping ("invoice" → `AP_INVOICES_ALL`).
- `EbsPack` groups these per `Module` (the `Literal` reused from `templates.py`).

`build_ebs_context(modules)` renders the selected packs as **curated markdown — names and
descriptions only, never row data** — which is appended to the external prompt context (opt-in;
see ADR-012/redaction). The combined context still runs through `assert_no_values`, so the
data-leak tripwire covers pack text too. Packs **describe exactly the tables the template catalog
already references** (a test enforces this).

## Consequences
- NL→SQL becomes EBS-aware via metadata only — no `Schema` model change, no new persistence, no
  weakening of redaction (packs are author-curated names/descriptions; a test asserts the
  generated context contains none of the `_FORBIDDEN_MARKERS`).
- Packs are **read-only and static this phase** (charter D-C); a user-editable glossary is a
  clean later increment.
- Pack **contents** still need validation against a real EBS instance (names vary by version /
  customization) — that stays **ITM-012**; packs are review-before-run, like templates.
- Glossary may reference a table owned by another module's pack (e.g. PO → `AP_SUPPLIERS`);
  consistency is checked against the **global** pack table set.

## Alternatives considered
- **Add `description`/glossary to the `Schema` dataclass:** rejected — touches the metadata-only
  serialization/whitelist and the persistence contract for marginal benefit; an overlay is
  cleaner and isolated.
- **Embed EBS hints in the LLM system prompt:** rejected — not inspectable, not testable, not
  per-module selectable, and harder to keep redaction-safe.
- **23ai vector / semantic glossary search:** deferred (charter D-A, ITM-018) — requires an
  Oracle 23ai instance to test; the curated packs deliver the value now, testably.

## Notes
- Surfaced read-only via `/packs` (mirrors `/templates`) and in the Data Dictionary UI.
- Opt-in: with no module selected, `build_ebs_context` returns `""` and behaviour is unchanged.
- Tests: `tests/test_ebs_packs.py` (integrity, template-table coverage, tripwire-safety).
