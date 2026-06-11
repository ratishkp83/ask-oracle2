# Round C1 — Design + Build Sequence (Pre-GA Consolidation & Testing)

> **Document:** Design · **Version:** 1.0 · **Status:** 🔄 Baseline (decisions resolved 2026-06-11; building) · **Owner:** Engineering · **Last updated:** 2026-06-11
> Charter: [charters/round-C1-charter.md](charters/round-C1-charter.md) (D-A Oracle XE available · D-B full scope · D-C build ITM-008 behind a default-off flag).

## 1. Purpose & scope recap
Verification + pre-GA cleanups, **no new features**, around the unchanged SELECT-only chokepoint:
confirm CI green on the Phase-6.5 push, run the **RISK-04 live-Oracle pass** against the owner's
XE, and clear ITM-006/007/008. Non-negotiables hold (SELECT/CTE-only chokepoint, AI-proposes,
secrets-via-env, metadata-only persistence, read-only DB account per ADR-009).

## 2. Build sequence (each step = one commit; code + its tests/docs together)
| Step | Item | Content | Risk |
|------|------|---------|------|
| **B1** | C1-4 / **ITM-007** | Mechanical: `use_container_width=True` → `width="stretch"` (14 sites in `app.py`) | Low |
| **B2** | C1-3 / **ITM-006** | Legacy `connection.json` → encrypted-profile migration; retire the plaintext manual-save path | Med (credential path) |
| **B3** | C1-5 / **ITM-008** | NL-question PII scrubbing behind a default-off flag (opt-in, before external LLM send) | Med (LLM path) |
| **B4** | C1-1 | Confirm CI 3.11+3.13 green on `9209e3a`; record run number | Low (owner/Actions) |
| **B5** | C1-2 / **RISK-04** | Live-Oracle + manual UI/observability pass against XE (runbook §6) | Med (real DB) |
| **B6** | C1-6 | Governed-doc sweep + GA-readiness verdict; close ITM-006/007/008; disposition RISK-04 | Low |
| **RC1.x** | gate | Independent exit-gate review for the code-touching items (B1–B3) — reviewer ≠ author | — |

## 3. ITM-007 — Streamlit `use_container_width` deprecation (B1)
- Verified: `streamlit==1.58.0` accepts `width` on `st.button`, `st.dataframe`, `st.download_button`.
- All 14 call sites are `use_container_width=True` (no `=False`), so each maps to `width="stretch"`
  (`=False` would have been `width="content"`). Pure substring replace; no behaviour change.
- Validate: `tests/test_app_smoke.py` (the 7-section headless `AppTest`) stays green; grep proves
  zero `use_container_width` remain.

## 4. ITM-006 — legacy `connection.json` → encrypted profiles (B2)
- **Today:** `src/storage.py` persists the manual single-connection config (host/port/service/sid/
  username only — the **password is already stripped** and never written, Phase-4 F5). The
  encrypted `ProfileStore` is the real persistence path.
- **Design:** add a one-time `migrate_legacy_connection()` (in `storage.py` or `core/profiles.py`):
  if `connection.json` exists, create an encrypted profile from its non-secret fields (name e.g.
  "Imported connection"; the user supplies the password on next connect/test — it was never
  stored), then delete `connection.json`. Stop writing `connection.json` going forward (the UI
  "manual connection" either creates a profile directly or is dropped — finalized against
  `app.py` at build). `load_connection_config` is retained for the migration read only.
- **Invariant:** no plaintext password at rest at any point (it never was); the migrated profile's
  password field stays empty until the user re-enters it through the encrypted path.
- Validate: a migration test (legacy file present → profile created sans password → file removed);
  no regression to `ProfileStore` encryption-at-rest tests.

## 5. ITM-008 — optional NL-question PII scrubbing (B3, per D-C)
- **Gate:** new env flag **`SCRUB_PII`** (default **off**). Scrubbing applies **only** when the flag
  is on **and** the request is going to an **external** provider (local stays verbatim). This
  complements — does not replace — the existing strict schema-context redaction
  (`core/llm/redaction.py`, which already sends schema **names only**).
- **Module:** `src/core/llm/pii.py` — `scrub_pii(text) -> (scrubbed, n_masked)` with conservative
  regex patterns masked to typed placeholders: email → `[EMAIL]`, phone → `[PHONE]`, SSN-like →
  `[SSN]`, credit-card-like (Luhn-length digit runs) → `[CARD]`, long bare digit runs → `[NUMBER]`.
- **Hook:** in the external send path (the NL question that goes into the external prompt). Exact
  call site finalized against `nl2sql.py`/the external provider at build; it wraps the user
  question before it reaches `ExternalLLMProvider.complete(...)`.
- **Rationale (why default-off):** scrubbing can degrade legitimate queries that reference real
  values — so it is opt-in per tenant, alongside the existing `LLM_POLICY=external_disabled`
  escape hatch. Matches the standing ITM-008 disposition.
- Validate: each pattern masked; flag-off → passthrough; an external-path test asserts the prompt
  carries the scrubbed question when the flag is on; local path unaffected.

## 6. C1-2 live-Oracle pass — XE runbook (B5)
> Owner runs the **setup** (privileged) once; the **pass** is then executed (manual UI walk, or the
> optional scripted smoke). Use a **least-privilege read-only account** (ADR-009) — never `SYSTEM`.
> The password is a secret: put it in env / the git-ignored `.env`, never in source or a commit.

### 6.1 Setup (run in SQL*Plus / SQLcl as a privileged user; XE 21c PDB is `XEPDB1`)
```sql
ALTER SESSION SET CONTAINER = XEPDB1;   -- adjust if your PDB differs

-- Least-privilege read-only account for the app (ADR-009):
CREATE USER aor_readonly IDENTIFIED BY "CHANGE_ME_strong";
GRANT CREATE SESSION TO aor_readonly;

-- Tiny sample schema so introspection + a report have something to read:
CREATE USER aor_demo IDENTIFIED BY "CHANGE_ME_demo";
GRANT CREATE SESSION, CREATE TABLE, UNLIMITED TABLESPACE TO aor_demo;

CREATE TABLE aor_demo.departments (
  department_id   NUMBER PRIMARY KEY,
  department_name VARCHAR2(60) NOT NULL
);
CREATE TABLE aor_demo.employees (
  employee_id   NUMBER PRIMARY KEY,
  first_name    VARCHAR2(40),
  last_name     VARCHAR2(40) NOT NULL,
  email         VARCHAR2(80),
  salary        NUMBER(10,2),
  department_id NUMBER REFERENCES aor_demo.departments(department_id)
);
INSERT INTO aor_demo.departments VALUES (10,'Finance');
INSERT INTO aor_demo.departments VALUES (20,'Engineering');
INSERT INTO aor_demo.employees VALUES (1,'Ada','Lovelace','ada@example.com',120000,20);
INSERT INTO aor_demo.employees VALUES (2,'Alan','Turing','alan@example.com',130000,20);
INSERT INTO aor_demo.employees VALUES (3,'Grace','Hopper','grace@example.com',125000,10);
COMMIT;

GRANT SELECT ON aor_demo.departments TO aor_readonly;
GRANT SELECT ON aor_demo.employees   TO aor_readonly;
```

### 6.2 Connection details
- host `localhost` · port `1521` · **service_name** `XEPDB1` (use `XE` only if connecting to the CDB)
- username `aor_readonly` · password = the one you set · **introspection owner** = `AOR_DEMO`

### 6.3 What the pass exercises (record pass/fail + the `error_id` on any failure)
1. **Connect / test** — add a profile (or inline connection) for `aor_readonly@localhost:1521/XEPDB1`; Test → OK.
2. **Introspection** — introspect owner `AOR_DEMO`; expect `DEPARTMENTS`/`EMPLOYEES`, PK/FK, columns.
3. **Saved report** — create + run a SELECT (e.g. `SELECT department_name, COUNT(*) … GROUP BY …`) with a bind; export CSV/Excel.
4. **Safety** — confirm a DML attempt (`UPDATE …`) is rejected with the safety reason (not run).
5. **Observability** — confirm JSON logs to stdout, an `error_id` on a forced error, `GET /metrics` counts.
6. **EBS templates** — **out of scope for XE** (GL/AP/AR/PO/OM tables don't exist here) → stays ITM-012 (needs a real EBS instance).

### 6.4 Execution options
- **Manual UI walk** (primary): `streamlit run src/app.py`, follow §6.3, capture screenshots/notes.
- **Optional scripted smoke** (engineer): a small read-only script driving `OracleClient` with the
  connection from env vars (`AOR_LIVE_HOST/PORT/SERVICE/USER/PASSWORD`) for steps 1–4; password read
  from env, never logged. Built at B5 only if the owner wants an automated record.

## 7. Test plan
- Offline suite stays green (242 → grows with ITM-006/008 tests). ITM-007 is smoke-covered.
- ITM-006: legacy-migration test. ITM-008: PII pattern + flag-on/off + external-path tests.
- B5 live pass is recorded evidence (not an offline test); any defect is filed in the issue log.

## 8. Risks → mitigation
Carried from the charter (C1-R1 no-`gh` → owner confirms CI; C1-R2 instance now available via XE;
C1-R3 EBS-template mismatch → ITM-012; C1-R4 ITM-006 credential path → encrypted store + tests +
reviewer re-check). No change to the chokepoint or the Phase-6.5 security posture.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-11 | Engineering | Initial design + build sequence (B1…B6) + XE live-pass runbook, per resolved decisions D-A…D-C. |
