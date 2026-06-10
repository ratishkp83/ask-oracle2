# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/); the project predates formal semantic versioning, so entries are grouped by delivery phase.

## [Unreleased]

### Added (Phase 6 — Observability & Error Handling)
- **Structured logging** ([ADR-012](adr/ADR-012-observability-and-error-handling.md)):
  `src/core/logging_config.py` — idempotent `configure_logging()`, **JSON to stdout**
  (`LOG_FORMAT=text` for local dev), level via `LOG_LEVEL`; a `request_id` `ContextVar`
  stamped on every record. The secret-free audit trail now emits **valid JSON** (content
  unchanged — SHA-256 fingerprint only).
- **Request correlation = error reference id**: `request_id_middleware` assigns/honours an
  `X-Request-ID` per request, echoes it as a response header, and injects it as `error_id`
  into **every** error body. The same id keys the matching server log line.
- **Uniform DB-error sanitization** (`src/core/errors.py`, **shared by API and UI**): raw
  driver/connection errors return a generic `"Database error — see server logs."` + `error_id`
  to the client; the full detail is logged server-side only. Safety-rejection reasons and
  validation messages stay verbatim. Central exception handlers (HTTPException / validation /
  catch-all 500) make the envelope uniform; the four DB-touching endpoints and three UI
  driver-error surfaces route through the one rule.
- **In-process metrics** (`src/core/metrics.py`): thread-safe counters
  (executed/rejected/errored) + latency, read-only via `GET /metrics` (counts only, no
  data/secrets; in-memory, resets on restart).
- **Governed docs:** `docs/observability-error-handling-design.md`, ADR-012; D3, D5, D6 (and
  D7/traceability/registers) updated in lockstep.
- Tests: **+25** → **185 total** green; CI runs a **Python 3.11 + 3.13 matrix** against a
  re-pinned, clean-install-proven 3.13-capable validated set (see the r1→r2 review below).

### Fixed (Phase 6)
- **ITM-015 (S3) CLOSED:** verbatim driver errors no longer leak DSN/host/port/username from
  `/execute`, `/reports/{id}/run`, `/schemas/introspect`, `/test-connection`,
  `/profiles/{id}/test`, or the UI — all sanitized uniformly (generic message + `error_id`;
  full detail server-side). Proven by `tests/test_error_handling.py`.

### Fixed (Phase 6 exit-gate review r1 → r2)
- **Phase 6 CLOSED** (gate passed 2026-06-10): independent review **r1 = PASS-WITH-FIXES**
  ([r1](reviews/phase-6-review-r1.md)) → remediated → **r2 = PASS** ([r2](reviews/phase-6-review-r2.md)).
  All 9 phase invariants + the suite were verified green; the 2 blocking S2 findings were
  **dependency/CI hygiene external to the Phase-6 code**.
- **F-1 / F-2 (S2):** the B5/ITM-016 "CI green on 3.11+3.13" claim was premature — the pinned
  `numpy==1.26.4`/`pandas==2.2.2` had **no Python-3.13 wheels** (3.13 leg uninstallable) and
  `httpx>=0.27` floated to 0.28, breaking `openai==1.43.0` on **every** leg; the branch being
  unpushed meant CI had **never run**. **Fixed:** the validated set was re-pinned to a
  clean-installable, 3.13-capable configuration (`numpy==2.2.6`, `pandas==2.2.3`,
  `streamlit==1.58.0`, `fastapi==0.136.3`, `uvicorn==0.49.0`, `Pillow==11.0.0`;
  `httpx>=0.27,<0.28` keeping `openai==1.43.0`; safety-critical `sqlglot==30.10.0` unchanged)
  and **proven by a clean-room `pip install` + `pytest` → 185 passed on a fresh Python-3.13 venv**.
- **F-3 (S3):** inbound `X-Request-ID` is now sanitized at ingress (`sanitize_correlation_id`:
  `[A-Za-z0-9_.-]`, ≤128) so it cannot forge a log line or split a header. **F-4 (S4):** the
  DB-error helper binds its `error_id` so the logged and returned ids cannot diverge. **F-5
  (S4):** leak tests now cover `/schemas/introspect` and assert response **headers** are clean.
  **F-7 (Info):** non-DB `str(exc)` surfaces deferred → ITM-017 (Phase-7). Suite **+3 → 185**.
- **ITM-016 (S4):** corrected from the premature B5 "closed" to **Mitigating** — the fix is in
  and clean-install-proven on 3.13; it **closes when the owner pushes** and CI demonstrates
  green on both interpreter legs (3.11 wheels confirmed; code interpreter-agnostic).

### Notes (Phase 6)
- All changes are **additive** and **do not touch** the SELECT-only chokepoint (`src/db.py`,
  `src/core/sql_safety.py`); error responses keep `detail` and add `error_id`; status codes
  unchanged. **Phase 6 CLOSED via the gate (r1 → r2 PASS); 185 tests; push pending for the CI
  demonstration (ITM-016).**

### Notes (Phase 5 closure)
- **Phase 5 CLOSED** (exit gate passed 2026-06-10): independent review **r1 = FAIL**
  (1 blocking — F-1/S2, metadata-only persistence not enforced) → remediated → **r2 =
  `PASS-WITH-FIXES`** (no open blocking) — [r1](reviews/phase-5-review-r1.md) ·
  [r2](reviews/phase-5-review-r2.md). F-1 fixed + independently re-verified (poison
  `POST /schemas` now persists only `{tables, relationships}`); F-2 200-path `warnings[]`
  leak fixed (400-path deferred → ITM-015, Phase-7, **deferral confirmed acceptable**);
  F-3/F-4/F-5 fixed; **N-1** (cosmetic `table_name` normalization, found in r2) fixed at
  closure. **F-4 caveat closed:** CI runs a from-scratch `pip install` on a clean runner
  (green == shipped); CI/dev Python-version matrix noted as ITM-016. Suite **160 tests** green.

### Added (Phase 5 — Data Dictionary Browser & Schema Tools)
- **Data-dictionary helpers** (`src/schema.py`): `find_columns` (name + data-type/PK/FK
  filters), `table_detail`, `references_out`, `referenced_by` (**where-used**), plus
  `schema_to_dict`/`schema_from_dict` serialization.
- **Schema persistence** ([ADR-011](adr/ADR-011-schema-persistence-store.md)):
  `src/core/schema_store.py` — `SchemaRecord`/`SchemaSummary` + `SchemaStore`
  (JSON/in-memory), metadata only; survives sessions.
- **Live SELECT-only introspection** ([ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md)):
  `src/core/introspection.py` builds a `Schema` from `ALL_TAB_COLUMNS`/`ALL_CONSTRAINTS`/
  `ALL_CONS_COLUMNS` **through the existing `run_select` chokepoint** — bind-parameterized,
  scoped (owner + filter), capped by `SafetyLimits`, `ALL_*` only, graceful degradation. No
  new DB path.
- **`/schemas` API**: CRUD + `POST /schemas/introspect` (introspect via the chokepoint,
  optionally save).
- **UI**: left-nav `Schema Upload → Schema Sources` (upload + introspect + save/load library)
  and `Explore Schema → Data Dictionary` (search/filter, column-detail grid, relationship
  navigation incl. where-used, export CSV/Excel/Markdown).
- **Governed docs:** `docs/data-dictionary-design.md`, ADR-010/011; D2 (FR-11/12/13), D3, D4,
  D5, D6, traceability updated in lockstep.
- Tests: **+25** → **155 total** green.

### Fixed (Phase 5 review r1 remediation)
- **F-1 (S2, blocking):** `POST /schemas` no longer persists arbitrary blobs — the
  `definition` is normalized through `schema_from_dict`→`schema_to_dict`, so injected
  secrets/row-data/connection-strings cannot reach `schemas.json` (**metadata-only enforced**).
  `schema_from_dict` is now whitelist-only and never raises.
- **F-3 (S3):** malformed stored definitions no longer crash the UI Load path (tolerant
  `schema_from_dict` + `try/except` guard).
- **F-2 (S3):** introspection degradation `warnings[]` (a 200 payload) are now generic; the
  raw driver exception is logged server-side only. (The introspect `400` verbatim error is
  deferred to ITM-015 / Phase 7, uniform with `/execute`.)
- **F-4 (S3):** `sqlglot==30.10.0` pinned exactly (the safety layer is parser-version-
  sensitive); `pydantic`/`oracledb`/`cryptography` pinned to the validated set so
  `pip install -r requirements.txt` reproduces the green suite.
- **F-5 (S4):** a blank `owner` (empty or whitespace) on `/schemas/introspect` now returns a
  uniform `400`.
- Suite **155 → 159** green. r1 verdict was **FAIL** (1 blocking); **r2 re-review pending**.

### Notes (Phase 4 closure)
- **Phase 4 CLOSED** (exit gate passed 2026-06-10): independent adversarial review
  **r1 = `PASS-WITH-FIXES`** (no S1/S2) — [phase-4-review-r1.md](reviews/phase-4-review-r1.md).
  Remediation: **F2** (reject `SELECT…INTO`), **F3** (reject non-finite number binds), **F4**
  (`/execute` exactly-one target → 422), **F5** (manual `connection.json` no longer persists
  the password — owner-approved) all **fixed** with regression tests; **F1** (a SELECT can
  call a side-effecting function — parse gate can't prove side-effect-freedom) **documented**
  as defense-in-depth: a least-privilege **read-only DB account is now a required deployment
  precondition** ([ADR-009](adr/ADR-009-readonly-db-account-precondition.md), Deployment §0),
  and the "no data modification" guarantee is reframed accordingly (D1/D3). **F6** (verbatim
  driver errors) deferred to Phase 7 (ITM-015); **R1/R2** (file-store durability/migration)
  backlogged (ITM-013/014, RISK-16). Owner closed F1 (account is the control) and F5 (don't
  persist the password). Suite now **130 tests** green.

### Added (Phase 4 — Reports, Templates & UX)
- **Parameterized saved reports.** New `src/core/reports.py`: Report v2 model
  (`id, name, description, sql, parameters[], default_profile_id?, template_id?,
  timestamps`), `ReportStore` (JSON/in-memory) with **legacy `{name:{sql}}` → v2
  migration on load**, and `coerce_report_binds` (defaults/required/typing, rejects
  unknown keys). Parameters are Oracle **bind variables**, never interpolated.
- **Bind safety at the chokepoint** ([ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)).
  `src/db.py`: `validate_binds` (scalar-only, name-validated) + `run_select(sql, limits,
  binds)`; `/execute` gains an optional `binds` map. The SELECT/CTE-only text check is
  unchanged, so the safety verdict is independent of bind values.
- **`/reports` API parity** ([ADR-008](adr/ADR-008-reports-core-module-api-parity.md)).
  CRUD + `POST /reports/{id}/run`; `/execute` refactored into shared `_resolve_target`
  + `_run_sql` so reports run through the exact same safety+limits+audit chokepoint.
- **EBS template catalog.** `src/core/templates.py`: 13 curated standard-EBS reference
  SELECTs (GL×3, AP×3, AR×2, PO×3, OM×2), parameterized, review-before-run; read-only
  `/templates` + `/templates/{id}`.
- **Left-nav UX.** Streamlit top tabs → sidebar radio nav (Connections, Schema Upload,
  Explore Schema, Query Builder, **Reports**, **Templates**, Settings) over one app with
  shared session state. Reports section runs parameterized reports with profile binding +
  export and saves SQL as reports; Templates section browses/loads/saves the catalog.
- **Governed docs:** `docs/reports-templates-ux-design.md`, ADR-007 & ADR-008; D3/D4/D5/D6
  and BRD/PRD (FR-8 upgraded, FR-10 added) + traceability updated in lockstep.
- Tests: **+43** at dev-complete (reports store/migration, bind safety, `/reports` API,
  templates, 7-section smoke) → 118; **+12** from r1 remediation → **130 total** green.

### Removed
- Dead report helpers in `src/storage.py` (`list_reports`/`save_report`/`get_report`/
  `delete_report`/`REPORTS_FILE`), superseded by the Report v2 store.

### Added
- **Governance baseline (P2.5):** full `/docs` governed set (Vision, BRD/PRD, Architecture, Data Models, API Contracts, Test Strategy, Deployment Plan), ADR log, Risk Register, Task Tracker, Issue Log, Traceability Matrix, Roadmap, and this changelog.
- Git version control initialized for the repository.
- Repository relocated to `ratishkp83/ask-oracle2` (2026-06-10); GitHub/app/Render references updated to match.
- GitHub Actions CI running the test suite (`.github/workflows/ci.yml`).
- Headless Streamlit UI smoke tests (`tests/test_app_smoke.py`, AppTest) — total suite now 51 tests.
- **Process:** mandatory **External Review & QA Gate** at every phase exit (independent adversarial review + QA, iterate-until-PASS), plus a reusable **Adversarial Review & QA Prompt** (`docs/process/`).
- **Phase 3 (dev complete, in review):** `src/core/llm/` provider abstraction (`ExternalLLMProvider` for Groq/OpenAI + `LocalLLMProvider` stub), `LLM_POLICY` toggle (`local_only`/`local_external`/`external_disabled`), **strict redaction** (external prompts = schema names only + tripwire), heuristic **confidence** (High/Med/Low), and NL→SQL now returns **SQL + explanation + confidence**. `/nl2sql` response extended; Streamlit shows explanation + confidence. (`docs/oracle-llm-design.md`.)

### Fixed (Phase 3 review r1 remediation)
- **F1 (S2):** confidence now validates JOIN predicates against `schema.relationships` (no more `High` on nonsensical joins; honors design §6).
- **F2 (S2):** provider-call failures return a clean `LLMError` message instead of leaking tenacity `RetryError[...]` (retry now `reraise=True`).
- **F4 (S3):** user-supplied `base_url` validated (https + block private/loopback/link-local/metadata) — SSRF guard.
- **F5 (S3):** confidence resolves columns per-table, not globally.
- **F6 (S4):** `api_key` masked in `LLMConfig`/`LLMSettings` repr.
- **F3 (S3):** corrected redaction wording (question text is sent by design; `external_disabled` mitigates); optional scrubbing deferred (ITM-008).
- Suite now **75 tests** (regression coverage for every finding).

### Notes (Phase 3 closure)
- **Phase 3 closed** (exit gate passed 2026-06-10): independent adversarial review **r1 FAIL → remediate → r2 `PASS-WITH-FIXES`** (no open blocking findings). r2 independently re-executed every probe; 75 tests green; governed docs current. Verdicts: [phase-3-review-r1.md](reviews/phase-3-review-r1.md), [phase-3-review-r2.md](reviews/phase-3-review-r2.md).
- r2 raised one **S4** hardening nit — **F7/ITM-010:** `validate_base_url` allows integer/hex/octal IP encodings of loopback (not exploitable on the tested stack; `getaddrinfo` fails closed). Backlogged under [RISK-11](risk-register.md).
- Deferrals confirmed acceptable: NL-question scrubbing (ITM-008) and pre-existing CORS hardening (ITM-009/RISK-12) — the latter a hard precondition for any networked/multi-tenant deployment.

### Fixed
- **BUG-005:** app crashed with `StreamlitDuplicateElementId` once a connection profile existed (duplicate `Delete selected` button across the Connections and Saved Reports tabs). Added unique widget keys to the affected buttons/selectboxes.
- `streamlit run src/app.py` now works from any working directory (added a `sys.path` shim in `src/app.py`).

### Notes
- **Phase 2 closed** (closure gate passed 2026-06-10): secrets rotated, 51 tests green, governance docs current.

## [Phase 2 — Hardened Connectivity & Safety] - 2026-06-10

### Added
- `src/core/` package: `sql_safety` (layered, fail-closed SELECT/CTE enforcement via sqlglot + denylist), `config` (`SafetyLimits`), `crypto` (Fernet), `profiles` (encrypted connection profiles + pluggable store), `audit` (secret-free logging).
- API: `/profiles` CRUD + `/profiles/{id}/test`; `/execute` as the single safety chokepoint (accepts `profile_id` or inline `connection`; returns `truncated`).
- Per-user LLM customization: `nl2sql.LLMConfig` (provider/model/key, env fallback) + `/nl2sql` `llm` field.
- Streamlit: **Connections** screen, profile-aware "Active Connection" sidebar, **Settings** screen (per-session LLM).
- Tests: 48 automated tests (safety, profiles, execute endpoint, LLM config).
- `requirements-dev.txt`; `sqlglot` + `cryptography` dependencies.

### Changed
- `db.py`: `run_select()` enforces row/time/result-size limits; `execute_query()` retained as a back-compat wrapper.
- `nl2sql.py`: removed duplicate safety check; uses the central layer.
- README, `.env.example`, `ask-oracle-techspec.md`: updated for the above.

### Security
- **Removed committed API keys** from `docker-compose.yml` and `src/api.py`; switched compose to `env_file`.
- `.gitignore`: now ignores `.env`, `storage/`, `__pycache__/`, `.venv/`.
- ⚠️ Previously committed Groq/OpenAI keys must be **rotated** (see [RISK-01](risk-register.md)).

## [Phase 1 — Productization] - prior

- Initial product: Streamlit + FastAPI + React scaffold; NL→SQL (Groq/OpenAI); schema upload; basic reports/export.
