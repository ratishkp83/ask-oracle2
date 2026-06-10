# Phase 5 — Independent Adversarial Review & QA (R1)

> **Reviewer:** Independent fresh-context agent (not the author) · **Date:** 2026-06-10
> **Phase:** Phase 5 — Data Dictionary Browser & Schema Tools
> **Change set:** `5335876..HEAD` (10 commits, `6a299f8 → 865719a`)
> **Gate:** [External Review & QA Gate](../process/external-review-gate.md) · **Prompt:** [adversarial-reviewer-prompt.md](../process/adversarial-reviewer-prompt.md) · **Package:** [phase-5-review-package.md](phase-5-review-package.md)
> **Environment:** `.venv` Python 3.13.2 · `pytest` 155 passed · mocked DB throughout (no live Oracle/LLM).

---

## 1. Verdict

**FAIL — second iteration required.**

One blocking finding (**F-1, S2**): the phase-specific invariant *"persistence is metadata-only"* is **not enforced**. `POST /schemas` accepts and persists an arbitrary `definition` blob verbatim — I stored a fake `db_password`, raw row data (SSNs), and a `connection_string` into a saved schema and read them back out. The fix is a ~1-line normalization that also removes F-3.

> **Owner waiver path:** there is no authentication/tenancy boundary anywhere in this product (the API is unauthenticated, `CORS allow_origins=["*"]`), so the "attacker" is also the data owner — no privilege boundary is crossed and the system never *originates* a secret into the store. If the owner formally accepts "clients may store their own blobs in plaintext `schemas.json`" as a documented risk, F-1 can be reclassified S3 and the verdict becomes **PASS-WITH-FIXES**. I am not exercising that waiver myself; as the hostile reviewer I hold it blocking because the invariant was declared absolute, the product encrypts the *same class of secret* (profile passwords) at rest, and the fix is trivial.

Everything genuinely safety-critical in Phase 5 **passed**: the SELECT-only chokepoint is intact (no new DB path), introspection inputs are bound never interpolated, scope/cap/`ALL_*`-only/graceful-degradation all hold, and `/schemas/introspect` target-resolution is byte-for-byte parity with `/execute`. The blocking item is a persistence-hygiene gap on the generic CRUD path, not a break in the introspection safety story.

---

## 2. Findings table

| ID | Sev | Category | Location (`file:line`) | Description | Reproduction (exact) | Recommended fix |
|----|-----|----------|------------------------|-------------|----------------------|-----------------|
| **F-1** | **S2** | Invariant (metadata-only persistence) / data-at-rest | [`src/api.py:490-506`](../../src/api.py) → [`src/core/schema_store.py:74-88,126-130`](../../src/core/schema_store.py) | `SchemaCreate.definition` is `Dict[str, Any]` and is stored **verbatim**; `_new_record` only reads `definition["tables"]` for a count and persists the whole dict to plaintext `schemas.json`. Arbitrary keys (passwords, row data, connection strings) survive at rest and are echoed by `GET /schemas/{id}`. The introspection and CSV paths are clean (always `schema_to_dict(...)`); only this raw passthrough is unconstrained. Profile passwords are encrypted at rest (ADR-009) — schemas are a plaintext sink for the same data class. | `POST /schemas {"name":"poison","definition":{"tables":{"EMP":[]},"db_password":"hunter2-SECRET","rows":[["alice","123-45-6789"]],"connection_string":"u/p@host:1521/XE"}}` → `201`; `GET /schemas/{id}` returns all three secret fields verbatim. (Executed via `TestClient`, mocked DB.) | Normalize before persisting: `definition = schema_to_dict(schema_from_dict(body.definition))` (or whitelist top-level keys to `{tables, relationships}` and validate column dicts). This both enforces metadata-only and fixes F-3. Consider rejecting unknown keys with `400`. |
| **F-2** | **S3** | Error handling / internals disclosure | [`src/core/introspection.py:167,175`](../../src/core/introspection.py) and [`src/api.py:534-538`](../../src/api.py) | Constraint-view degradation embeds the **raw exception** in a user-facing warning (`f"Primary keys unavailable ({exc})."`), returned in the **200** `warnings[]`; the introspect failure path returns `str(exc)` in the `400` `detail`. Oracle errors carry internal host/service/object names. This partially violates phase-invariant 4 ("graceful degradation … **not a leak of internals**") and the standing "no internals in API responses." (Pre-existing pattern for `/execute`/`/test-connection`; Phase 5 adds the **new** `warnings[]` surface on a *success* response.) | `LeakyClient` raising `ORA-12514 … host=db-prod-internal:1521` on the PK/FK query → 200 response `warnings: ["Primary keys unavailable (ORA-12514 … host=db-prod-internal:1521).", …]`. Introspect 400 path returns `"ORA-00942: table SYS.SECRET_INTERNAL does not exist @ host=prod-db-01"`. | Return a generic warning/detail ("Primary keys unavailable for this account."); log the raw `exc` server-side only. At minimum scrub host/connection tokens. Apply consistently with the standing `/execute` error shape. |
| **F-3** | **S3** | Robustness (unguarded UI path) | [`src/app.py:459-465`](../../src/app.py) → [`src/schema.py:283-292`](../../src/schema.py) | `schema_from_dict` does `ColumnDefinition(**c)`; a stored definition with unexpected/missing column keys raises `TypeError`. The UI **Load** button calls it with **no try/except**, so a malformed saved schema crashes Streamlit with a traceback. Reachable because F-1 lets any blob be stored. | `POST /schemas {"name":"x","definition":{"tables":{"X":[{"foo":1}]}}}`, then UI → Schema Sources → Library → **Load** → `TypeError: ColumnDefinition.__init__() got an unexpected keyword argument 'foo'` (verified `schema_from_dict({'tables':{'X':[{'foo':1}]}})` raises). | Fixing F-1 (normalize on write) removes the stored-blob vector. Independently, wrap the Load call in `try/except` and surface a clean `st.error`. |
| **F-4** | **S3** | Dependencies / reproducibility | [`requirements.txt`](../../requirements.txt) vs `.venv` | The test venv has drifted from the pins: **pydantic 2.13.4** (pinned `==2.8.2`), **oracledb 4.0.1** (pinned `==2.5.1`, a major bump), **sqlglot 30.10.0** (pinned floor-only `>=25.0.0`). The 155-green result was produced on versions a clean `pip install -r requirements.txt` would **not** reproduce. The SELECT-only guarantee is parser-version-sensitive, yet sqlglot is unpinned — a different sqlglot may parse exotic SQL differently and silently change fail-closed behavior. | `pip show pydantic oracledb sqlglot` in `.venv` vs `requirements.txt`. | Pin sqlglot to an exact tested version; reconcile pydantic/oracledb pins with what's actually run in CI; run the suite under the pinned set (or update pins to the validated set) so green == shipped. |
| **F-5** | **S4** | Contract drift | [`src/api.py:153`](../../src/api.py) (`owner: Field(..., min_length=1)`) vs [`introspection.py:146-147`](../../src/core/introspection.py) | Phase-invariant 3 / package says "blank/whitespace owner → **400**." Empty `""` is rejected by Pydantic `min_length=1` as **422**; whitespace `"   "`/`"\t"` reaches the orchestrator and returns **400**. Both fail-closed (good), but the empty case contradicts the documented "→ 400". | `POST /schemas/introspect {"connection":…,"owner":""}` → `422`; `{"owner":"   "}` → `400`. | Either document both codes in [05-api-contracts](../05-api-contracts.md), or normalize: drop `min_length` and let the orchestrator return a uniform `400`, or strip+validate in the model so blank and whitespace both yield the same status. |

---

## 3. Blocking items (must fix before Phase 5 closes)

1. **F-1 (S2)** — Enforce metadata-only persistence on `POST /schemas`. Normalize the `definition` through `schema_from_dict`→`schema_to_dict` (or whitelist `{tables, relationships}`) so secrets/row-data cannot be persisted to `schemas.json`. *Fixing this also closes F-3.*

S3/S4 items (F-2, F-4, F-5) are **not** blocking by the gate's default rule but should be logged to the issue-log; F-2 in particular is a cheap, worthwhile hardening and ties to a stated invariant.

---

## 4. QA results (executed)

All probes run against the real safety layer / API via the project `.venv`; DB mocked. Throwaway probe scripts were removed after the run.

| Invariant / attack | Method | Result |
|---|---|---|
| **Inv-1 — single chokepoint, no new DB path** | `grep` for `oracledb.connect` / `cur.execute` / `.cursor()` across `src/` | **PASS** — exactly one each, both in [`src/db.py:113,140,141`](../../src/db.py). Introspection routes through `OracleClient.run_select` → `assert_safe_select`. No second path. |
| **Inv-1/2 — builders are safe SELECTs, inputs bound** | `assert_safe_select` on `columns_sql`/`primary_keys_sql`/`foreign_keys_sql` × 7 hostile owners (`X' OR '1'='1`, `HR'; DROP TABLE EMP;--`, `… UNION SELECT password FROM sys.user$--`, `%%`, 5000-char, trailing-space, `HR/**/`) | **PASS** — 21/21: every builder yields an allowed SELECT, hostile value never appears in SQL text, always returned as the `:owner`/`:table_like` **bind value**. |
| **Inv-2 — orchestrator keeps payloads inert** | `introspect_schema(owner="X' OR '1'='1", table_like="%' OR '1'='1")` with a capture client | **PASS** — all 3 emitted queries: payload bound (`{'owner':"X' OR '1'='1", …}`), `OR '1'='1` absent from SQL text, each still `assert_safe_select`-allowed. |
| **Inv-2 — bind backstop** | `validate_binds({"owner": <dict/list/object>})` | **PASS** — each non-scalar raises `SqlSafetyError`. |
| **Inv-3 — scoped + required** | empty / whitespace / tab owner via API | **PARTIAL** — all rejected fail-closed; empty→**422**, whitespace/tab→**400** (see **F-5**). No unscoped crawl path: `owner` always bound in `WHERE`. |
| **Inv-3 — capped + honest truncation** | introspect with `truncated=True` columns result | **PASS** — `IntrospectionResult.truncated` propagates; API surfaces `truncated`. |
| **Inv-4 — `ALL_*` only** | `grep DBA_/dba_` across `src/` | **PASS** — no matches; introspection uses `ALL_TAB_COLUMNS`/`ALL_CONSTRAINTS`/`ALL_CONS_COLUMNS` only. |
| **Inv-4 — graceful degradation** | constraint queries raise `ORA-00942` | **PASS (structure)** — returns columns-only schema + 2 warnings, no crash; **but** warnings leak raw `exc` (**F-2**). |
| **Inv-5 — metadata-only persistence** | `POST /schemas` with secrets/rows in `definition` | **FAIL → F-1** — stored & echoed verbatim. |
| **Inv-6 — target resolution parity with `/execute`** | neither / both / unknown-profile on both endpoints | **PASS** — `422 / 422 / 404` identical on `/execute` and `/schemas/introspect`. |
| **Inv-7 — no regression** | chokepoint count + `assert_safe_select` unchanged + 155-test suite | **PASS** — safety layer untouched by Phase 5; `/execute`/`/reports` unchanged; full suite green. |
| **Inv-8 — UI widget keys / Excel export** | static read of `app.py` new sections + `dataframe_to_excel_bytes` | **PASS (no blocker found)** — new widgets carry explicit `key=`s; sections are mutually exclusive (one renders per nav), so cross-section `download_button` label reuse cannot collide in a single render; `openpyxl==3.1.5` present and engine wired in [`src/utils.py:24-28`](../../src/utils.py). Not exercised in a live browser (headless `AppTest` only) — see §5. |
| **Suite** | `pytest -q` on `.venv` | **155 passed**, 1 deprecation warning (`httpx`/starlette TestClient) — cosmetic. |

---

## 5. Could-not-verify

- **Live Oracle behavior** — no instance available. Actual `ALL_*` shapes, privilege/visibility behavior, `call_timeout`, and `truncated` under real volume are validated only against the safety layer + synthetic dictionary rows (matches package RISK-04 / ITM). The *fail-closed* and *bind-not-interpolate* guarantees do **not** depend on a live DB and were verified directly.
- **Browser UI** — verified by reading source only; no headless `AppTest`/visual pass was run in this review. The `StreamlitDuplicateElementId` class and the F-3 Load-crash traceback were reasoned + reproduced at the function level, not observed in a running app.
- **File-store durability/concurrency** — `schemas.json` shares the known atomic-write/multi-worker gap (package R1 → ITM-013 / RISK-16); not load-tested here.
- **sqlglot parse coverage under the *pinned* floor** — probes ran on sqlglot 30.10.0 (installed), not the `>=25.0.0` floor; behavior on the lowest allowed version is unverified (see **F-4**).
