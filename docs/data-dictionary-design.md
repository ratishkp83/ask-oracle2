# Data Dictionary Browser & Schema Tools — Design (Phase 5)

> **Document:** Design · **Version:** 1.0 · **Status:** Baseline (built; Phase 5 closed — exit gate passed) · **Owner:** Product/Engineering · **Last updated:** 2026-06-10
> Implements [phase-5-charter.md](charters/phase-5-charter.md) (decisions D-A…D-E resolved 2026-06-10).

## 1. Overview
Phase 5 turns thin schema exploration into a **data-dictionary browser** (searchable
tables/columns with full detail + relationship navigation + export) and adds two **schema
tools**: **live SELECT-only introspection** of Oracle's data-dictionary views, and
**schema persistence** (a store + read API). All DB access remains read-only, through the
single `/execute`-equivalent chokepoint, under the required least-privilege account
([ADR-009](adr/ADR-009-readonly-db-account-precondition.md)).

## 2. Schema-tool helpers (`src/schema.py`)
Pure functions over the existing `Schema` (no DB), with unit tests:

| Helper | Returns |
|--------|---------|
| `find_columns(schema, query="", *, data_type=None, pk=None, fk=None)` | `[ColumnDefinition]` matching a name substring (table or column) + filters |
| `table_detail(schema, table)` | the table's `[ColumnDefinition]` (full detail) |
| `references_out(schema, table)` | `[(from_column, to_table, to_column)]` — FKs this table declares |
| `referenced_by(schema, table)` | `[(from_table, from_column, to_column)]` — **where-used**: other tables' FKs / relationships pointing **at** this table |

`referenced_by` unions per-column FK metadata and `schema.relationships` (deduped).

## 3. Serialization (`src/schema.py`)
`schema_to_dict(schema) -> dict` and `schema_from_dict(d) -> Schema` (round-trippable;
metadata only — table/column/relationship structure, **no data values**). Used by the
store and the API.

## 4. Schema persistence (`src/core/schema_store.py`) — D-B / ADR-011
Mirrors `profiles`/`reports`:

| Model | Fields |
|-------|--------|
| `SchemaRecord` | `id, name, source∈{upload,introspection}, profile_id?, table_count, created_at, updated_at, schema(dict)` |

`SchemaStore` ABC + `JsonFileSchemaStore` (`storage/schemas.json`) + `InMemorySchemaStore`;
methods `create / list / get / delete` (list/get may return a lightweight summary without
the full `schema` blob for `list`). **No secrets/values** — schema metadata only; file is
git-ignored like the others.

## 5. Live introspection (`src/core/introspection.py`) — D-A / ADR-010 (safety-critical)
Builds a `Schema` from Oracle's `ALL_*` data-dictionary views. **Reuses
`OracleClient.run_select`** — every query passes `assert_safe_select` first and runs under
the read-only account; **no new execution path**, **SELECT-only**, **bind-parameterized**
([ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)), **scoped + capped**.

Structure (each part independently testable):
1. **SQL builders** → `(sql, binds)`; each asserted SELECT-safe in tests:
   - columns: `SELECT owner, table_name, column_name, data_type, column_id FROM all_tab_columns WHERE owner = :owner AND table_name LIKE :table_like ORDER BY table_name, column_id`
   - primary keys: join `all_constraints` (`constraint_type='P'`) ↔ `all_cons_columns`
   - foreign keys: join `all_constraints` (`constraint_type='R'`) ↔ `all_cons_columns` ↔ the
     referenced constraint's `all_cons_columns` (by `r_owner`/`r_constraint_name` + `position`) → `(from_table, from_column, to_table, to_column)`
2. **Mappers** (rows → `Schema`): build columns/tables, set `is_primary_key`, set
   `is_foreign_key` + `references_*`, append `RelationshipDefinition`s. Tested on synthetic rows.
3. **Orchestrator** `introspect_schema(client, owner, table_like="%", limits=None) -> IntrospectionResult`:
   runs the builders via `run_select`, maps, returns `IntrospectionResult(schema, warnings[], truncated)`.

**Scoping / safety:**
- `owner` is **required** (UI prefills the connection's username, upper-cased); `table_like`
  defaults to `%` but the UI nudges a filter. No full-catalog crawl.
- Bounded by `SafetyLimits` (row cap → `truncated` surfaced; the user narrows the filter).
- **Graceful degradation:** if the constraint views aren't visible to the account, catch and
  continue **columns-only**, appending a `warning` (no PK/FK) rather than failing.
- `ALL_*` only (objects visible to the connected user) — never `DBA_*`.

## 6. API (`src/api.py`) — D-B
| Method | Path | Body | Result |
|--------|------|------|--------|
| POST | `/schemas` | `{name, schema}` (or `{name, schema_csv, relationships_csv?}`) | 201 `SchemaRecord` |
| GET | `/schemas` | — | `[SchemaRecord summary]` |
| GET | `/schemas/{id}` | — | `SchemaRecord` (full) / 404 |
| DELETE | `/schemas/{id}` | — | 204 / 404 |
| POST | `/schemas/introspect` | `{profile_id? \| connection?, owner, table_like?, save?, name?}` | `SchemaRecord` (or schema dict) |

`/schemas/introspect` resolves the target (same `_resolve_target` as `/execute`), introspects
through the chokepoint, optionally saves. The introspection queries are SELECT-only — the
same safety guarantees as `/execute`.

## 7. UI (`src/app.py`) — D-C / D-E
Left-nav renames: **"Schema Upload" → "Schema Sources"**, **"Explore Schema" → "Data
Dictionary"**. Final nav: `Connections · Schema Sources · Data Dictionary · Query Builder ·
Reports · Templates · Settings`.
- **Schema Sources:** upload (existing) **+ Introspect from connection** (owner + table
  filter → `introspect_schema` via the active connection) **+ Save to library / Load saved**
  (`SchemaStore`).
- **Data Dictionary:** global **search/filter** (name, data type, PK-only, FK-only); table
  picker → **column-detail grid** (column, type, PK, FK, → target); **relationship
  navigation** (references-out + **where-used**); **export** (CSV/Excel via `utils`,
  Markdown via `to_compact_markdown`).
- Shared `st.session_state.schema`; smoke test updated for the renamed nav.

## 8. Test plan (D6)
| Area | Tests |
|------|-------|
| Helpers | `find_columns` (name/type/pk/fk filters), `references_out`, **`referenced_by`** (where-used), `table_detail` |
| Serialization | `schema_to_dict`/`from_dict` round-trip |
| Store | CRUD, file round-trip, summary-vs-full, delete semantics |
| Introspection | each SQL builder is a **safe SELECT** (`assert_safe_select`) and uses binds; mappers build correct PK/FK/relationships from synthetic rows; orchestrator with a **mocked client** (no DB); graceful degradation when constraint views fail |
| API | `/schemas` CRUD + 404s; `/schemas/introspect` happy path (mocked DB) + safety (SELECT-only) |
| UI | nav shows Data Dictionary/Schema Sources; sections render; introspect control present |

## 9. ADRs
- **ADR-010** — Live schema introspection via the SELECT-only chokepoint (read-only,
  bind-parameterized, scoped/capped; no new execution path).
- **ADR-011** — Schema persistence store (metadata only; mirrors profiles/reports).

## 10. Out of scope (confirmed, charter)
Data profiling / value sampling, write-back, ER-graph visualization, editable business
glossary, `DBA_*` views, full-catalog crawl.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Initial Phase-5 design (dictionary browser, schema-tool helpers, persistence store, SELECT-only introspection, /schemas API). |
