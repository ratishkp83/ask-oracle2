# Phase 5 Charter — Data Dictionary Browser & Schema Tools

> **Document:** Phase Charter · **Version:** 1.2 · **Status:** Development complete → exit-gate review · **Owner:** Product/Engineering · **Last updated:** 2026-06-10

## Lifecycle stage
**In exit gate** (2026-06-10). Built across `4d08844 → 865719a`; design approved.
Independent review **r1 = FAIL** (1 blocking — F-1 S2, metadata-only persistence not
enforced; [phase-5-review-r1.md](../reviews/phase-5-review-r1.md)). **Remediated**: F-1
fixed (not waived) + F-2…F-5; **159 tests green** (`ee14e70`). **Next: r2 re-review** on
the fixes + regression (owner-supplied reviewer) → on PASS, close Phase 5.

## Context — where we are today (grounding facts)
- **A schema model already exists** (`src/schema.py`): `Schema` → `TableDefinition` →
  `ColumnDefinition` (with `data_type`, `is_primary_key`, `is_foreign_key`,
  `references_table/column`) + `RelationshipDefinition`. Parsed from uploaded CSV/Excel
  (`parse_schema_dataframe` / `parse_relationships_dataframe`); BR-4 = no DBA metadata
  privileges required.
- **The current "Explore Schema" UI is thin.** `draw_schema_explorer` shows a table
  picker → **column names only** (`list_columns`) + a relationships table. It does **not**
  surface the per-column detail the model already holds (data type, PK/FK flags, FK
  target), has **no search/filter**, and **no relationship navigation / where-used**.
- **Schema is session-only.** It lives in `st.session_state.schema` and must be
  **re-uploaded every session**; it is never persisted server-side. NL→SQL receives it
  inline (`schema_csv` in the `/nl2sql` body); there is no schema store or `/schema` API.
- **Read-only DB account precondition (ADR-009)** is now in force — so SELECT-only
  introspection of Oracle's data-dictionary views (`ALL_TAB_COLUMNS`, `ALL_CONS_COLUMNS`,
  `ALL_CONSTRAINTS`, …) is architecturally compatible: it would run through the existing
  `/execute` SELECT/CTE chokepoint under the read-only account.

## Objectives
1. Turn schema exploration into a proper **data-dictionary browser**: searchable,
   filterable tables/columns with full detail (type, PK/FK, FK target) and **relationship
   navigation** (FK in/out, "where used").
2. Add **schema tools** that reduce the manual-upload burden and make the dictionary
   reusable (per the Decisions: optional **live SELECT-only introspection** and/or
   **schema persistence**).
3. Export the dictionary; keep everything read-only and governed.

## Scope — in (subject to Decisions)
- **Data-dictionary browser** (enhanced/renamed "Explore Schema" or a new **Data
  Dictionary** left-nav section): table list + global **search/filter** (by table/column
  name, data type, PK/FK); per-table **column detail grid**; **relationship navigation**
  (this table's FKs out, tables whose FKs point in / "where used"); dictionary **export**
  (CSV/Excel/Markdown).
- **Schema query/search helpers** in the core (e.g. `find_columns`, `references_to`,
  `referenced_by`) with tests — reused by UI (and API if D-B says so).
- **(If D-A)** Live **SELECT-only introspection**: build a `Schema` from
  `ALL_TAB_COLUMNS` + constraint views via `run_select` (the chokepoint), **scoped**
  (owner/schema + name filter) and **capped** (`SafetyLimits`), with graceful degradation
  when the account can't see a view.
- **(If D-B)** **Schema persistence** (a `SchemaStore`, mirroring profiles/reports) so the
  dictionary survives sessions, **+ a read `/schema` (or `/dictionary`) API** for parity.
- Tests + governed-doc updates in the same change set (D2 FR, D3, D4, D5, D6, ADR(s),
  CHANGELOG, traceability, registers, tracker).

## Scope — out (explicit non-goals for Phase 5)
- **No data profiling / row-count / value sampling** — dictionary = *metadata* only (no
  reading table *data* for stats in this phase).
- **No write-back to the database** of any kind (read-only product guarantee).
- **No visual ER-diagram rendering** unless D-C opts in (Phase 4 kept "no charts"); default
  is tabular/text relationship navigation.
- **No business glossary / editable annotations** unless D-D opts in.
- **No DBA_*-view introspection** — `ALL_*` (objects visible to the read-only account) only.
- **No automatic full-catalog crawl** of large EBS instances — introspection is scoped and
  on-demand.

## Deliverables
- Data-dictionary browser UI (search/filter, column-detail grid, relationship navigation,
  export).
- Core schema-tool helpers (search/where-used) — `src/schema.py` or `src/core/dictionary.py`.
- **(If D-A)** `src/core/introspection.py` — dictionary-view SELECTs + row→`Schema` mapping
  (through the chokepoint).
- **(If D-B)** `src/core/schema_store.py` (+ `/schema` API).
- Tests: schema-helper unit tests; introspection mapping against synthetic dictionary
  fixtures (mocked DB — no live Oracle); UI smoke for the new section; (if D-B) store +
  API tests.
- Governed docs: this charter (resolved), D2 (new FRs), D3, D4, D5, D6, ADR(s), CHANGELOG,
  traceability, registers, tracker.

## Risks
| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R5-1 | Live introspection on a huge EBS catalog (tens of thousands of objects) overwhelms UI / times out | High | **Scope** by owner/schema + name filter; **cap** via `SafetyLimits`; on-demand (per-table), never a full crawl |
| R5-2 | Introspection bypasses the safety chokepoint | **High** | Reuse `OracleClient.run_select` — dictionary queries are SELECT-only and go through `assert_safe_select` + the read-only account; no new execution path |
| R5-3 | Dictionary-view privileges/availability vary by account | Medium | Use `ALL_*` views (visible to the connected user); graceful degradation + clear messaging when a view isn't accessible |
| R5-4 | Introspection mapping correctness (PK/FK across owners) | Medium | Synthetic dictionary fixtures + unit tests; document known limitations; user reviews before relying |
| R5-5 | Persisted schema metadata sensitivity (table/column names, no data) | Low | Local JSON under `STORAGE_DIR` (git-ignored), like reports; metadata only, no values/secrets |
| R5-6 | Scope creep (browser + introspection + persistence + API + glossary) overloads the phase | Medium | Decisions fix the envelope up front; defer glossary; scope introspection; persistence optional |

## Success criteria (phase exit)
1. A data-dictionary browser presents searchable/filterable tables and **full column
   detail** (type, PK/FK, FK target) plus **relationship navigation** (FK in/out, where-used)
   over uploaded metadata.
2. Dictionary **export** (CSV/Excel/Markdown) works.
3. **(If D-A)** Live introspection builds a `Schema` via **SELECT-only** queries through
   the chokepoint under a read-only account, scoped + capped, degrading gracefully.
4. **(If D-B)** The schema persists across sessions via a store (+ read API), no re-upload.
5. Tests green in CI; governed docs current.
6. **Independent adversarial review + QA returns PASS** ([gate](../process/external-review-gate.md)); **reviewer agent supplied by the owner**.

## Decisions (resolved 2026-06-10)
Owner resolved all five at charter approval — the four pivotal scope decisions confirmed
**as recommended**; the D-E default accepted.

- **D-A — Live introspection:** ✅ **Add scoped SELECT-only introspection** (auto-load from
  `ALL_*` views through the chokepoint, scoped by owner/schema + name filter, capped by
  `SafetyLimits`, graceful on missing views) **alongside** CSV/Excel upload.
- **D-B — Schema persistence + API:** ✅ **Persist the schema in a `SchemaStore`** (mirrors
  profiles/reports; local JSON under `STORAGE_DIR`, metadata only) **+ a read `/schema`
  API** for parity.
- **D-C — Browser depth:** ✅ **Full browser** — search/filter + column-detail grid + FK
  navigation + **where-used** (reverse FK) + export (CSV/Excel/Markdown). No ER-graph viz.
- **D-D — Business glossary:** ✅ **Read-only browser only**; editable glossary deferred.
- **D-E — UI placement:** ✅ **Rename/expand "Explore Schema" → "Data Dictionary"** in the
  left-nav (single section, shared session state).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Discovery charter opened; decisions pending owner approval. |
| 1.1 | 2026-06-10 | Product/Eng | Owner approved; decisions D-A…D-E resolved (4 pivotal as recommended; D-E default accepted). Discovery complete → Design. |
| 1.2 | 2026-06-10 | Product/Eng | Design approved + built (helpers, schema store, introspection, /schemas, Data Dictionary UI); 155 tests; docs updated. Dev+Test complete → exit-gate review (R5.x). |
