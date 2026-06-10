# D6 — Test Strategy

> **Document:** Test Strategy · **Version:** 1.1 · **Status:** Baseline · **Owner:** QA/Engineering · **Last updated:** 2026-06-10

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

**118 automated tests pass locally** (75 from Phases 2–3 + 43 new in Phase 4):
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

GitHub Actions (`.github/workflows/ci.yml`) installs `requirements-dev.txt` and runs `pytest -q` on push/PR. Gate: merges require green CI.

## 7. Manual UI smoke checklist (Phase-2 closure)

- [ ] Connections: add profile (service & SID variants), list shows **no password**, test selected, delete.
- [ ] Sidebar: switch between saved profile and manual entry; test connection.
- [ ] Settings: set Groq/OpenAI provider+model+key (session only); confirm status line; revert to server default.
- [ ] Query: NL→SQL generates and is editable; run a SELECT; verify `truncated` warning when capped.
- [ ] Raw SQL: a DML statement is rejected with a clear message.
- [ ] Missing `APP_SECRET_KEY`: Connections shows a clear configuration error.
- [ ] Reports: save SQL with `:params`, bind a profile, run with parameter values, export CSV/XLSX; missing required param shows a clear error.
- [ ] Templates: load a GL/AP/AR/PO/OM template, run vs. a **real EBS** instance (schema-variance caveat), save-as-report.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | QA/Eng | Baseline; 48-test coverage recorded, CI + UI smoke defined. |
| 1.1 | 2026-06-10 | QA/Eng | Phase 4: +43 tests (reports store/migration, bind safety, /reports API, templates, 7-section smoke) → 118 total; manual checklist extended. |
