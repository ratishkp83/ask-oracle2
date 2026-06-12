# D6 — Test Strategy

> **Document:** Test Strategy · **Version:** 1.8 · **Status:** Baseline · **Owner:** QA/Engineering · **Last updated:** 2026-06-12

## 1. Objectives

Prove the product's core guarantees on every change: **read-only safety**, **credential confidentiality**, **bounded execution**, and **contract stability**.

## 2. Test levels

| Level | Scope | Tooling | State |
|-------|-------|---------|-------|
| Unit | Safety engine, crypto, profile store, LLM config resolution | pytest | ✅ Implemented |
| API/integration | `/execute`, `/profiles` via TestClient (DB monkeypatched) | pytest + FastAPI TestClient | ✅ Implemented |
| UI smoke (headless) | Streamlit left-nav sections render; Connections/Settings/Templates flows | streamlit `AppTest` | ✅ Implemented (`test_app_smoke.py`) |
| Manual UI / live DB | Browser visuals, real connection success, live NL→SQL, **parameterized report run vs. real EBS** | Checklist (below) + Oracle sandbox | ⏳ Recommended pass |

## 3. Current coverage (baseline)

**262 automated tests pass locally** (160 through Phase 5 + 25 in Phase 6 + 57 in Phase 6.5 + 20 in Round C1 incl. review-r1 remediation):

- **Pre-deployment hardening (Phase 6.5)** — `test_auth.py` (16): auth is a no-op with
  `APP_API_KEY` unset (default posture pinned); with it set, a 401 matrix across endpoints
  incl. `/metrics`, `/health` exemption, wrong/right key, uniform 401 envelope
  (`error_id` + `X-Request-ID`), **no key material in logs**, CORS env parse + the
  `*`-forfeits-credentials invariant, preflight unaffected. `test_llm_providers.py` (+17):
  ITM-010 encoding matrix (decimal/hex/octal/dotted/short-form rejected), all-numeric-invalid
  hosts fail closed, digit-leading real hostnames pass, IPv6 regression.
  `test_fileio.py` (7): atomic-write round-trip, overwrite, parent dirs, `default=`,
  **failed write keeps old content**, no temp residue. Review r1: `validate_base_url` also
  rejects **Unicode fullwidth-digit** IP encodings via NFKC fold (R1) and `_cors_config`
  falls back on blank `ALLOWED_ORIGINS` (R3). `test_store_robustness.py` (6):
  corrupt v2/legacy records quarantined (skip, not 500), **preserved verbatim across saves**
  incl. the migration save, profile + schema stores, log-once-per-instance.
  `test_error_handling.py` (+5): ITM-017 — unexpected `/nl2sql` failure returns generic +
  `error_id` (full detail server-side), `LLMError`/`ValueError`/`SecretConfigError` stay
  verbatim (the 500 now with a breadcrumb), UI `log_error_for_ui` ref.
- **Observability & error handling (Phase 6)** — `test_logging_config.py` (7): JSON formatter
  emits valid JSON + base keys, `request_id` stamping, text mode, **idempotent** handlers,
  `LOG_LEVEL`, audit record round-trips as **secret-free** JSON. `test_error_handling.py`
  (13): **ITM-015 leak proof** (no host/DSN/username in any client body **or headers**; full
  driver detail present server-side keyed by the same `error_id`) across `/execute`,
  `/test-connection`, `/profiles/{id}/test`, **and `/schemas/introspect`**, inbound
  `X-Request-ID` honoured + **sanitized** (no CR/LF/header injection) + echoed + reused as
  `error_id`, safe messages (404/409/safety-400) stay verbatim and merely **gain** `error_id`,
  validation `422` gains `error_id`, catch-all generic `500`, and the **shared UI sanitizer**
  returns a ref + logs full detail. `test_metrics.py` (5): counter increments
  (executed/rejected/errored) + latency via the chokepoint, `GET /metrics` JSON is secret-free.
- **Reproducibility (review r1 F-1/F-2):** the validated set was re-pinned to a clean-installable,
  Python-3.13-capable configuration and **proven by a clean-room `pip install -r
  requirements-dev.txt` + `pytest` → 185 passed on a fresh 3.13 venv** (not the resident
  dev venv) — restoring the "green == shipped" guarantee.

- **Data dictionary & schema tools (Phase 5)** — `test_schema_tools.py` (6): helpers
  (`find_columns` filters, `references_out`, **`referenced_by`/where-used**, serialization
  round-trip). `test_schema_store.py` (4): store CRUD, duplicate-name, summary-vs-full,
  file round-trip. `test_introspection.py` (7): **every dictionary query is a safe SELECT**
  + bind-parameterized, mappers (PK/FK/relationships), orchestrator happy-path +
  graceful-degradation + owner-required (mocked DB). `test_schemas_api.py` (7): `/schemas`
  CRUD + 404/409/422, `/schemas/introspect` inline + save + require-target + blank-owner-400.
  `test_app_smoke.py` +1: Data Dictionary renders with a seeded schema.

Through Phase 4 (130):
- `test_sql_safety.py` (24): accept/reject matrix incl. literal/identifier false-positive guards, stacked statements, `FOR UPDATE`, PL/SQL, MERGE/GRANT/DDL/DML.
- `test_profiles.py` (6): encryption-at-rest, decrypt round-trip, no password leakage, duplicate-name & service/sid validation.
- `test_execute_endpoint.py` (13): unsafe-SQL rejection, target validation (422), unknown profile (404), success inline + via profile, `/profiles` CRUD without password, clean provider-failure error (F2).
- `test_app_smoke.py` (5): headless AppTest — nav options; **all seven left-nav sections render without exception**; Settings LLM override; Templates catalog; Connections create → on-disk encryption.
- **Reports & bind safety (Phase 4)** — `test_reports.py` (13): store CRUD, duplicate-name, update/delete, file round-trip, **legacy migration**, param-name validation, `coerce_report_binds` (defaults/required/typing/unknown-key). `test_bind_safety.py` (11): `validate_binds` accept/reject matrix, injection value cannot alter parsed SQL, `run_select` hands binds to `cur.execute` as a separate arg, **DML-with-binds still rejected**, parameterized SELECT runs. `test_reports_api.py` (9): `/reports` CRUD + 404/409, `/reports/{id}/run` happy/bound-profile/missing-bind/no-target/unknown-report/unknown-bind/DML-rejected. `test_templates.py` (7): catalog covers all 5 modules, **every template is a safe SELECT**, declared params == `:binds`, unique ids, endpoints.
- **LLM (Phase 3)** — `test_llm_redaction.py` (2), `test_llm_providers.py` (9), `test_llm_policy.py` (5), `test_llm_confidence.py` (8), `test_nl2sql.py` (5): strict redaction, provider/credential resolution + `base_url` SSRF guard + repr masking, `LLM_POLICY` selection + graceful errors, heuristic confidence incl. join/per-table resolution, NL→SQL parse/safety + clean provider-failure (mocked provider, no network).

## 4. Coverage targets

- Safety layer: **100%** of branches; every new forbidden construct gets a regression case.
- API endpoints: every status code path has a test.
- Overall line coverage target: **≥ 80%** (introduce `pytest-cov` in CI).

## 5. Environments & test data

- **Local/CI:** no real Oracle; the driver is monkeypatched. `APP_SECRET_KEY` set to a test value via root `conftest.py`; `STORAGE_DIR` redirected to a throwaway path.
- **Test data:** synthetic only. **No production credentials or PII** in tests or fixtures.

## 6. CI

GitHub Actions (`.github/workflows/ci.yml`) installs `requirements-dev.txt` and runs `pytest -q` on push/PR across a **Python 3.11 + 3.13 matrix** (`fail-fast: false`) — the validated set is confirmed on every interpreter actually used (ITM-016 closed). Gate: merges require green CI.

## 7. Manual UI smoke checklist (Phase-2 closure)

- [ ] Connections: add profile (service & SID variants), list shows **no password**, test selected, delete.
- [ ] Sidebar: switch between saved profile and manual entry; test connection.
- [ ] Settings: set Groq/OpenAI provider+model+key (session only); confirm status line; revert to server default.
- [ ] Query: NL→SQL generates and is editable; run a SELECT; verify `truncated` warning when capped.
- [ ] Raw SQL: a DML statement is rejected with a clear message.
- [ ] Missing `APP_SECRET_KEY`: Connections shows a clear configuration error.
- [ ] Reports: save SQL with `:params`, bind a profile, run with parameter values, export CSV/XLSX; missing required param shows a clear error.
- [ ] Templates: load a GL/AP/AR/PO/OM template, run vs. a **real EBS** instance (schema-variance caveat), save-as-report.
- [ ] Data Dictionary: **introspect** a schema from a live read-only connection (owner + filter); verify scoping/caps; browse/search; export CSV/Excel/Markdown; save + reload from the library.
- [ ] Observability: confirm stdout shows **JSON** log lines (set `LOG_FORMAT=text` for dev); force a DB error and confirm the UI/API shows the **generic message + ref id** while the full ORA-/DSN detail appears only in the server log under that id; `GET /metrics` returns query counts + latency.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | QA/Eng | Baseline; 48-test coverage recorded, CI + UI smoke defined. |
| 1.1 | 2026-06-10 | QA/Eng | Phase 4: +43 tests (reports store/migration, bind safety, /reports API, templates, 7-section smoke) → 118 total; manual checklist extended. |
| 1.2 | 2026-06-10 | QA/Eng | Phase-4 review r1 remediation: +12 tests (SELECT INTO, non-finite binds, exactly-one target, no-plaintext connection.json) → 130 total. |
| 1.3 | 2026-06-10 | QA/Eng | Phase 5: +25 tests (dictionary helpers, schema store, introspection SELECT-safety + mapping, /schemas API, dictionary smoke) → 155 total. |
| 1.4 | 2026-06-10 | QA/Eng | Phase 6: +22 tests (logging config/JSON, error sanitization + correlation incl. ITM-015 leak proof, metrics) → 182 total; CI 3.11+3.13 matrix; observability manual-check added. |
| 1.5 | 2026-06-10 | QA/Eng | Phase 6 r1 remediation: +3 tests (introspect leak, inbound-id sanitization, sanitize unit) → 185; re-pinned to a clean-install-proven 3.13-capable set (F-1/F-2); leak tests now assert headers + cover `/schemas/introspect`. |
| 1.6 | 2026-06-11 | QA/Eng | Phase 6.5: +51 tests (auth on/off + CORS invariant, ITM-010 encoding matrix, atomic-write contract, corrupt-record quarantine, ITM-017 surfaces) → **236 total**. |
| 1.7 | 2026-06-11 | QA/Eng | Phase 6.5 review r1 remediation: +6 tests (Unicode fullwidth-digit SSRF fold + genuine-IDN pass, blank-`ALLOWED_ORIGINS` fallback) → **242 total**. |
| 1.8 | 2026-06-12 | QA/Eng | Round C1: +20 tests (`test_pii.py` PII-scrubbing matrix + flag/external-path; `connection.json` migration; review-r1 F1 delete-warning + F2 load-TOCTOU) → **262 total**. Plus the out-of-band live-Oracle pass vs XE 21c (`scripts/c1_live_smoke.py`, evidence in `reviews/round-C1-live-pass.md`). |
