# ADR-011 — Schema persistence store (metadata only)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product/Engineering
- **Phase:** 5 (Data Dictionary Browser & Schema Tools)

## Context
Through Phase 4, an uploaded schema lived only in Streamlit `st.session_state` and had
to be **re-uploaded every session**; NL→SQL received it inline. Phase 5 adds live
introspection and a data-dictionary browser, which makes a reusable, persisted dictionary
worthwhile (charter D-B).

## Decision
Persist schemas in a **`SchemaStore`** that mirrors `core/profiles.py` and
`core/reports.py`: an ABC with `JsonFileSchemaStore` (default, `storage/schemas.json`) and
`InMemorySchemaStore` (tests). A **`SchemaRecord`** carries `id, name, source
(upload|introspection), profile_id?, table_count, timestamps, definition` — where
`definition` is the serialized schema dict from `schema_to_dict` (the field is named
`definition`, not `schema`, to avoid shadowing a Pydantic attribute).

- **Metadata only.** A record holds table/column/relationship structure — **no data values
  and no credentials**. The file is git-ignored like the other stores.
- `list()` returns lightweight `SchemaSummary` objects (no `definition` blob); `get()`
  returns the full record.
- Exposed read + manage via the API (`/schemas`), consistent with the core+API pattern
  ([ADR-008](ADR-008-reports-core-module-api-parity.md)).

## Consequences
- A dictionary survives sessions; no re-upload/re-introspection each time.
- One source of truth for saved schemas (UI + API share the store).
- A SQLite/Postgres backend can replace the JSON file without touching the API.

## Alternatives considered
- **Keep schema session-only:** rejected (D-B) — re-upload friction, no API parity.
- **Store inside the reports/profiles files:** rejected — schemas are a distinct concern;
  a dedicated store keeps each file cohesive.
