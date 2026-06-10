# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/); the project predates formal semantic versioning, so entries are grouped by delivery phase.

## [Unreleased]

### Added (Phase 4 — Reports, Templates & UX · dev complete, pending exit-gate review)
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
- Tests: **+43** (reports store/migration, bind safety, `/reports` API, templates,
  7-section smoke) → **118 total** green.

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
