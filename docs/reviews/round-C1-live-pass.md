# Round C1 / B5 — Live-Oracle Pass (RISK-04 evidence)

> **Date:** 2026-06-11 · **Instance:** Oracle Database 21c **XE**, PDB `XEPDB1`, localhost:1521
> **Account:** `aor_readonly` — least-privilege read-only (`CREATE SESSION` + `SELECT` on the sample schema only), per [ADR-009](../adr/ADR-009-readonly-db-account-precondition.md)
> **Driver:** `python-oracledb==4.0.1` **thin mode** (no Oracle client install needed)
> **Harness:** [`scripts/c1_live_smoke.py`](../../scripts/c1_live_smoke.py) — drives the **actual product code**, not a reimplementation.

## Setup
A privileged session (SYS via Windows OS authentication — `sqlplus / as sysdba`, no stored
password) created, in `XEPDB1`:
- `aor_readonly` — the app's connecting account: `CREATE SESSION` + `SELECT` on the two sample
  tables. Nothing else.
- `aor_demo` — a **locked** (no-login) schema owner holding a tiny sample: `DEPARTMENTS` /
  `EMPLOYEES` (PK on each, an FK `EMPLOYEES.DEPARTMENT_ID → DEPARTMENTS.DEPARTMENT_ID`, 5 rows).

The read-only connection is stored in the git-ignored `.env` (`AOR_LIVE_*`); the password is
never printed or committed. SQL is in [round-C1-design.md §6.1](../round-C1-design.md).

## Result — ALL PASS

| # | Step (real code path) | Result | Evidence |
|---|----------------------|--------|----------|
| 1 | **Connect + `OracleClient.run_select`** (`SELECT 1 FROM dual`) | ✅ PASS | round-trip ~0.06s |
| 2 | **Live introspection** (`introspect_schema`, owner `AOR_DEMO`) | ✅ PASS | tables `[DEPARTMENTS, EMPLOYEES]`, **1 FK relationship** detected, no degradation warnings |
| 3 | **Bind-parameterized report** (`WHERE department_id = :dept`, bind=20) | ✅ PASS | 2 rows; bind passed as a **value**, never interpolated (ADR-007) |
| 4 | **CSV export** (pandas, as the app does) | ✅ PASS | 74 bytes, expected rows present |
| 5 | **Safety gate rejects `UPDATE`** (through the chokepoint) | ✅ PASS | `SqlSafetyError: Only SELECT/CTE queries are allowed…` — **not run against the DB** |
| 6 | **Safety gate rejects `SELECT … FOR UPDATE`** | ✅ PASS | `SqlSafetyError: Row-locking clauses … not allowed.` |

**Verdict: ALL PASS.** The connect → introspect → bound-report → export → safety path is
validated against a real Oracle instance. The SELECT-only chokepoint holds against live XE
(defense-in-depth: even though `aor_readonly` lacks write privileges, the safety layer rejects
DML/locking **before** the database is touched).

## Scope / residuals (not failures)
- **EBS templates (GL/AP/AR/PO/OM)** reference E-Business Suite objects that don't exist on plain
  XE → **not** exercised here; remains [ITM-012](../issue-log.md) (needs a real EBS instance).
- **Streamlit UI browser-visual walk** — the data path is proven here and the headless `AppTest`
  smoke covers section rendering in CI; an optional human click-through against XE can be done for
  visual confirmation but is not required to close the live-DB portion of RISK-04.
- **Observability** (JSON logs / `error_id` / `/metrics`) was validated offline in Phase 6; not
  re-exercised in this DB pass.

## Reproduce
```powershell
# After the §6.1 setup (account + sample schema) and .env AOR_LIVE_* are in place:
$env:PYTHONPATH="<repo>"; .\.venv\Scripts\python.exe scripts\c1_live_smoke.py
```
