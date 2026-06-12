# Phase 7 — Design + Build Sequence (EBS Intelligence & 23ai)

> **Document:** Design · **Version:** 1.0 · **Status:** 🔄 Pending owner approval (no code until approved) · **Owner:** Engineering · **Last updated:** 2026-06-12
> Charter: [charters/phase-7-charter.md](charters/phase-7-charter.md) (D-A defer 23ai · D-B all 5 modules, core tables · D-C read-only curated · D-D fold in `/v1`).

## 1. Purpose & scope recap
Make NL→SQL EBS-aware via **curated metadata packs + glossary** (the testable, no-new-infra
track), add a read-only `/packs` API and UI surface, fold in the `/v1` API prefix (T-18), and
**formally defer** the 23ai vector track with a recorded direction. All additive; the SELECT-only
chokepoint and the external-prompt redaction guarantee are untouched (packs are curated
**metadata** — table/column descriptions, join hints, business-term mappings — never row data).

## 2. Current-state seams (verified in code)
- **`Schema`** (`src/schema.py`) carries structure only — **no description/glossary fields**. Packs
  must overlay, not mutate the Schema persistence contract (Phase-5 metadata-only enforcement).
- **Templates** (`src/core/templates.py`): curated pydantic models in an in-repo list, exposed
  read-only (`list_templates()` → `/templates`). **Packs mirror this exactly.** `Module =
  Literal["GL","AP","AR","PO","OM"]` is defined there — reuse it.
- **External prompt context** (`src/core/llm/redaction.py`): `build_external_context(schema)` =
  `schema.to_compact_markdown()` (names only); `assert_no_values(context)` is the tripwire. Pack
  metadata appends here and is covered by the same tripwire.
- **API** (`src/api.py`): routes are `@app.<verb>` decorators directly on `app`; app-level
  `dependencies=[Depends(require_api_key)]` + exception handlers + middleware live on `app`.

## 3. Component designs

### 3.1 `src/core/ebs_packs.py` (new) — B1
Pydantic models + curated data + accessors:
```
Module (reuse from templates)
GlossaryTerm(term, table, column?, note?)
TableNote(table, description, key_columns=[], joins=[])     # joins: "A.col -> B.col" hints
EbsPack(module, name, tables=[TableNote], glossary=[GlossaryTerm])
_PACKS: list[EbsPack]   # GL/AP/AR/PO/OM, core tables (aligned with the template catalog)
list_packs() -> [EbsPack];  get_pack(module) -> EbsPack | None;  all_glossary() -> [GlossaryTerm]
build_ebs_context(modules: list[Module]) -> str   # curated markdown: glossary + table notes
```
**Invariants (tested):** every glossary `table` exists in its module's `TableNote` set; `joins`
are well-formed `A.col -> B.col`; `build_ebs_context(...)` output contains **none** of the
`_FORBIDDEN_MARKERS` (so it always passes `assert_no_values`); packs are static (no I/O).

### 3.2 NL→SQL context enrichment — B2
- `generate_sql_from_nl(...)` gains an optional `ebs_modules: list[Module] | None`. When provided
  **and** the provider is external, the prompt context becomes
  `build_external_context(schema) + "\n\n" + build_ebs_context(ebs_modules)`, then
  `assert_no_values(combined)` runs over the **whole** thing (unchanged guarantee).
- **Opt-in:** no `ebs_modules` → behaviour identical to today (non-EBS users unaffected). Local
  provider path unchanged. AI still **proposes** SQL; nothing auto-runs.
- Tests: combined context passes the tripwire; an EBS question with packs on yields SQL
  referencing the mapped tables (mocked LLM asserting the prompt carried the glossary); packs-off
  is byte-identical to current context.

### 3.3 UI — B3
- **Data Dictionary:** a read-only **"EBS Packs"** expander — pick a module, browse table notes +
  searchable glossary (term → table/column/note).
- **Query Builder (NL mode):** a multiselect "Include EBS module context (GL/AP/…)" that feeds
  `ebs_modules` into the `/nl2sql` call. Default none.
- Covered by the headless `AppTest` smoke (sections render).

### 3.4 `/packs` API — B4
- `GET /packs` → `list[EbsPack]`; `GET /packs/{module}` → `EbsPack` (404 unknown). Read-only,
  mirrors `/templates`. Auth applies (app-level dependency).

### 3.5 `/v1` API prefix (T-18) — B5
- Move the route **decorators** from `@app.<verb>` onto an `APIRouter` (`router = APIRouter()`),
  then `app.include_router(router)` **and** `app.include_router(router, prefix="/v1")`. Every
  endpoint is reachable at both its current path (back-compat) **and** `/v1/...`.
- **Unchanged:** exception handlers, middleware, and the app-level auth dependency stay on `app`
  and apply to both mounts. The `/execute` chokepoint logic is in `sql_safety.py`/`db.py` — only
  the decorator host changes; the full endpoint suite + new `/v1` assertions prove no regression.
- Closes **T-18**; documented in D5. (`/health` exemption: keep `/health` exempt; `/v1/health`
  optional — decide at build, default keep only `/health` for probes.)

### 3.6 23ai deferral — B6
- **ADR-016 (or a design note)** records: 23ai vector track **deferred**; intended direction =
  AI Vector Search over glossary/schema embeddings for semantic term→object matching, gated
  behind a flag and a 23ai instance; revisit on a 23ai instance or customer demand. New backlog
  **ITM-018** ("23ai vector track — deferred, design recorded"). No code.

### 3.7 Governed-doc sweep — B7
ADR-015 (EBS metadata packs), D3 (module table: `core/ebs_packs`), D5 (`/packs`, `/v1`), D6
(tests), D7 (no new env), product-vision/BRD (EBS positioning: packs are review-before-run
metadata), CHANGELOG, traceability (new FR for EBS packs), registers (close T-18; ITM-018; ITM-012
note that packs still need live-EBS validation), tracker. Then R7.1 review package.

## 4. Build sequence (each step = one commit; code + tests + docs)
| Step | Content | Closes |
|------|---------|--------|
| **B1** | `core/ebs_packs.py` + 5 curated packs + accessors + `build_ebs_context`; pack-integrity & no-leak tests; ADR-015 | — |
| **B2** | NL→SQL EBS context enrichment (opt-in, external-only, tripwire over combined); redaction tests | — |
| **B3** | UI: Data Dictionary EBS-packs browser + Query Builder module multiselect | — |
| **B4** | `/packs` + `/packs/{module}` read-only API | — |
| **B5** | `/v1` prefix via `APIRouter` included twice (back-compat); `/v1` endpoint tests | **T-18** |
| **B6** | 23ai deferral ADR/note + **ITM-018** | D-A |
| **B7** | Governed-doc sweep + traceability + registers; R7.1 review package | — |
| **R7.x** | Independent exit-gate review (reviewer ≠ author) → PASS → close | — |

## 5. Test plan (offline; mocked LLM; no live DB needed)
- Pack integrity (glossary↔table consistency, join format), `build_ebs_context` no-forbidden-markers.
- `assert_no_values` over schema+EBS combined context; packs-off context unchanged.
- `/packs` list/detail/404; auth on/off matrix already covers the new routes.
- `/v1`: a sampled endpoint matrix answers identically at `/x` and `/v1/x`; auth still enforced.
- Full suite green on 3.11 + 3.13; the live-Oracle smoke is **not** re-required (no execution-path change).

## 6. Risks → mitigation (from charter)
P7-R1 pack accuracy → review-before-run + ITM-012 live-EBS validation; P7-R2 23ai untestable →
deferred (B6); P7-R3 glossary leak/bloat → curated text + `assert_no_values` + `max_chars` cap in
the context builder; P7-R4 scope creep → flat term→object glossary, 5 modules core tables, no
inference engine. **No change to the chokepoint or the Phase-6.5 security posture.**

## 7. Out of scope (recorded)
23ai vector code (deferred, B6); OCI GenAI SDK; user-editable glossary (D-C later increment);
ITM-011 multi-value binds (not folded in); live-EBS validation of pack contents (ITM-012).

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-12 | Engineering | Initial design + build sequence (B1…B7) per resolved decisions D-A…D-D; pending owner approval before any code. |
