# D6 — Test Strategy

> **Document:** Test Strategy · **Version:** 1.0 · **Status:** Baseline · **Owner:** QA/Engineering · **Last updated:** 2026-06-10

## 1. Objectives

Prove the product's core guarantees on every change: **read-only safety**, **credential confidentiality**, **bounded execution**, and **contract stability**.

## 2. Test levels

| Level | Scope | Tooling | State |
|-------|-------|---------|-------|
| Unit | Safety engine, crypto, profile store, LLM config resolution | pytest | ✅ Implemented |
| API/integration | `/execute`, `/profiles` via TestClient (DB monkeypatched) | pytest + FastAPI TestClient | ✅ Implemented |
| UI smoke (headless) | Streamlit screens render; Connections/Settings flows | streamlit `AppTest` | ✅ Implemented (`test_app_smoke.py`) |
| Manual UI / live DB | Browser visuals, real connection success, live NL→SQL | Checklist (below) + Oracle sandbox | ⏳ Recommended pass |

## 3. Current coverage (baseline)

**51 automated tests pass locally:**
- `test_sql_safety.py` (24): accept/reject matrix incl. literal/identifier false-positive guards, stacked statements, `FOR UPDATE`, PL/SQL, MERGE/GRANT/DDL/DML.
- `test_profiles.py` (6): encryption-at-rest, decrypt round-trip, no password leakage, duplicate-name & service/sid validation.
- `test_execute_endpoint.py` (12): unsafe-SQL rejection, target validation (422), unknown profile (404), success inline + via profile, `/profiles` CRUD without password.
- `test_nl2sql_config.py` (6): per-user LLM resolution + env fallback (no network).
- `test_app_smoke.py` (3): headless AppTest — all six screens render without exception; Settings LLM override; Connections create → on-disk encryption. (Caught + validated the fix for BUG-005, a duplicate-widget-ID crash.)

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

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | QA/Eng | Baseline; 48-test coverage recorded, CI + UI smoke defined. |
