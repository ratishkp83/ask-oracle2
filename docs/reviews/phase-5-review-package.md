# Phase 5 — Review Package (input to the independent gate)

> **Prepared:** 2026-06-10 · For: owner-supplied independent reviewer · Gate: [external-review-gate](../process/external-review-gate.md)
> Hand the **filled Context block** below (plus this package) to the reviewer along with the [Adversarial Review & QA Prompt](../process/adversarial-reviewer-prompt.md). The reviewer (a fresh-context agent, **not** the author) writes findings to `docs/reviews/phase-5-review-r1.md`.

## Change set
- **Range:** `5335876..HEAD` — the 9 Phase-5 commits (`6a299f8 → 65bc995`).
- **Diff:** `git diff 5335876..HEAD`.
- **Primary new code:**
  - `src/core/introspection.py` — live SELECT-only dictionary introspection (the safety-critical addition).
  - `src/core/schema_store.py` — schema persistence (`SchemaRecord`/`SchemaSummary` + store).
  - `src/schema.py` — dictionary helpers (`find_columns`, `references_out`, `referenced_by`) + `schema_to_dict`/`schema_from_dict`.
  - `src/api.py` — `/schemas` CRUD + `POST /schemas/introspect`.
  - `src/app.py` — left-nav rename to **Schema Sources** + **Data Dictionary** (search/filter, where-used, export, introspect, save/load).
- **Commits:** `6a299f8` charter · `6b3f4ce` decisions · `4d08844` design · `41ba9f2` helpers · `8a00489` store (ADR-011) · `7598cc3` introspection (ADR-010) · `733ca59` /schemas API · `2067ec7` UI · `65bc995` docs.

## Filled Context block (paste into the adversarial prompt)
- **Phase under review:** Phase 5 — Data Dictionary Browser & Schema Tools.
- **Charter:** [charters/phase-5-charter.md](../charters/phase-5-charter.md) · **Design:** [data-dictionary-design.md](../data-dictionary-design.md) · **ADRs:** [ADR-010](../adr/ADR-010-schema-introspection-via-chokepoint.md) (introspection), [ADR-011](../adr/ADR-011-schema-persistence-store.md) (store).
- **Change set:** `5335876..HEAD`.
- **Phase-specific invariants to attack (in addition to the standing list in the prompt):**
  1. **Introspection cannot bypass the chokepoint.** Every dictionary query (`columns_sql`, `primary_keys_sql`, `foreign_keys_sql` in `introspection.py`) must pass `assert_safe_select` and run via `OracleClient.run_select` — **no new path** to the DB. Confirm there is still exactly **one** `cur.execute` and one `oracledb.connect`. Try to make introspection issue or accept anything non-SELECT.
  2. **Introspection inputs are bound, never interpolated** ([ADR-007](../adr/ADR-007-parameterized-reports-bind-variables.md)/[ADR-010](../adr/ADR-010-schema-introspection-via-chokepoint.md)). `owner` and `table_like` go in as `:binds`. Attack with `owner = "X' OR '1'='1"`, embedded quotes/semicolons, wildcards, and very long values — they must stay inert values; the SQL text must be unchanged.
  3. **Scoped + capped.** `owner` is required (blank/whitespace → 400). Results are bounded by `SafetyLimits` (`truncated` surfaced). Confirm there is **no** unscoped full-catalog crawl path.
  4. **`ALL_*` only + graceful degradation.** No `DBA_*` views. If constraint views aren't visible, introspection returns a **columns-only** schema + a warning — not a crash and not a leak of internals.
  5. **Persistence is metadata-only.** `SchemaRecord` / `schemas.json` must hold table/column/relationship **structure only** — no data values, no credentials, no connection passwords. Try to get a secret or row data into a saved schema. (`profile_id` is a stored reference id, not a credential.)
  6. **`/schemas/introspect` target resolution** reuses `_resolve_target` — exactly-one of `profile_id`/`connection` (422 on both/neither), 404 on unknown profile — identical to `/execute`. Probe for drift.
  7. **No regression** to the standing invariants — especially confirm adding introspection did **not** create a second execution path, weaken `assert_safe_select`, or change `/execute`/`/reports` behavior.
  8. **UI:** widget-key collisions across the new Data Dictionary / Schema Sources sections (Phase-2 `StreamlitDuplicateElementId` class); the Excel export path (`openpyxl`).

## Test status
- `pytest -q` → **155 passed** locally (mocked DB throughout — no live Oracle/LLM calls).
- New suites: `test_schema_tools.py` (6), `test_schema_store.py` (4), `test_introspection.py` (7), `test_schemas_api.py` (7), +1 in `test_app_smoke.py`.
- Run: `pip install -r requirements-dev.txt` then `APP_SECRET_KEY=… PYTHONPATH=. pytest -q`.
  (Note: `openpyxl` is in `requirements.txt`; ensure the venv installed it — needed for `.xlsx`.)

## Known limitations / not covered (verify or flag)
- **No live Oracle** — introspection queries are validated against the safety layer and mapped from synthetic dictionary rows; actual `ALL_*` results, privilege behavior, and `truncated` under real volume are **not** automatically tested (pre-GA RISK-04 / [ITM in issue-log](../issue-log.md)).
- **UI** verified via headless `AppTest` only (no browser/visual pass).
- File-store durability/concurrency (atomic writes, multi-worker) is the known Phase-7 item (R1 → [ITM-013](../issue-log.md)/[RISK-16](../risk-register.md)); `schemas.json` shares this.
- Introspection on very large catalogs depends on the user scoping the owner/filter ([RISK-17](../risk-register.md)).

## Expected reviewer output
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + exact `file:line` + repro), blocking list (default: open S1/S2), QA results, could-not-verify — saved to `docs/reviews/phase-5-review-r1.md`.

---

## r2 scope (after r1 remediation)

- **r1 verdict:** **FAIL** — 1 blocking (F-1, S2). Full findings: [phase-5-review-r1.md](phase-5-review-r1.md). Triage + dispositions in [issue-log.md](../issue-log.md) (Phase-5 section).
- **Remediation change set for r2:** `865719a..HEAD` (remediation commit `ee14e70`). Re-run these probes + regression:
  - **F-1 (blocking)** — `create_schema` now normalizes via `schema_to_dict(schema_from_dict(body.definition))`; `schema.py:schema_from_dict` is whitelist-only. **Re-run the poison-blob probe** (`POST /schemas` with `db_password`/`rows`/`connection_string` in `definition`) → expect the stored + echoed definition to contain **only** `{tables, relationships}`; secrets gone. (Regression: `test_schemas_api.py::test_create_schema_strips_non_metadata`, `test_schema_tools.py::test_schema_from_dict_drops_unknown_keys`.)
  - **F-3** — `schema_from_dict` no longer raises; UI Load guarded. Re-run the malformed-definition probe → no `TypeError` (returns an empty/partial schema). (`test_schema_tools.py::test_schema_from_dict_tolerates_malformed`.)
  - **F-2 (200-path)** — degradation `warnings[]` are generic; re-run the `LeakyClient` ORA-error probe → **no `ORA`/host tokens in `warnings`** (raw exc now logged server-side only). The introspect **400** verbatim path is **deferred** → [ITM-015](../issue-log.md) (Phase-7, uniform with `/execute`) — confirm the deferral rationale is acceptable rather than re-raising as blocking.
  - **F-4** — `requirements.txt` pins `sqlglot==30.10.0` + `pydantic==2.13.4`/`oracledb==4.0.1`/`cryptography==48.0.1`; confirm a clean `pip install -r requirements.txt` reproduces the **159-green** set (green == shipped).
  - **F-5** — empty/whitespace `owner` → uniform **400**. (`test_schemas_api.py::test_introspect_empty_owner_is_400`.)
  - **Regression:** full suite (now **159**) green; confirm no new gaps and the chokepoint/bind invariants still hold.
- Output → `docs/reviews/phase-5-review-r2.md`.
