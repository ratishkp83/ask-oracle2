# Ask Oracle Reports — HANDOFF (read me first)

> **Document:** Session Handoff · **Version:** 1.4 · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-10
> **Purpose:** the single entry point for any new/resumed session. Read this, then the linked governed docs, then continue. This file is updated at the end of every working session / phase.

## 0. How to work here (operating model)
Run this project like a structured, Big-4-style delivery practice: **doc-first, phase-gated**. Keep code and governed docs updated together. Define **Next Actions** every turn. Pause and ask on scope-changing or destructive/outward-facing decisions. Maintain the task tracker, risk register, issue log, ADRs, and change log.

## 1. What this is
**Ask Oracle Reports** — a commercial, AI-assisted, **read-only** reporting layer for Oracle Database / E-Business Suite. Connect → Ask (NL→SQL) → review SQL → run → export. Stack: Python + FastAPI (`src/api.py`), Streamlit UI (`src/app.py`), an (inactive) Vite/React scaffold; `python-oracledb` thin mode; Groq/OpenAI via an OpenAI-compatible client; Docker Compose / Render.

## 2. Environment & repo
- **Local repo (git):** `D:\Ratish\Personal\Project\ask-oracle-reports-main` (branch `main`). Note: the *folder* name is legacy (`-reports-main`); it is not a tracked reference.
- **Remote:** `origin` = https://github.com/ratishkp83/ask-oracle2 (branch `main`, in sync). Push with `git push` (upstream set). `gh` is **not** installed; auth works via cached Git Credential Manager. Commit per change; **push only when the owner asks.**
- **OS/shell:** Windows / PowerShell. Python via `py -3`. Project virtualenv at `.venv` (deps installed; both `.venv` and `.env` are git-ignored).
- **Run the suite (expect 75 passed):**
  ```powershell
  $env:PYTHONPATH = "D:\Ratish\Personal\Project\ask-oracle-reports-main"
  $env:APP_SECRET_KEY = "test-secret-key-not-for-production"
  .\.venv\Scripts\python.exe -m pytest tests -q
  ```
  CI mirrors this in `.github/workflows/ci.yml` (runs on push/PR).

## 3. Read order (source of truth = `/docs`)
1. **This file.**
2. [00-governance-index.md](00-governance-index.md) — doc map, conventions, the phase-exit gate.
3. [task-tracker.md](task-tracker.md) and [roadmap.md](roadmap.md) — current state / what's next.
4. [process/external-review-gate.md](process/external-review-gate.md) + [process/adversarial-reviewer-prompt.md](process/adversarial-reviewer-prompt.md) — the mandatory end-of-phase review.
5. Active charter under [charters/](charters/), plus [oracle-llm-design.md](oracle-llm-design.md), [issue-log.md](issue-log.md), [risk-register.md](risk-register.md), [adr/](adr/), [CHANGELOG.md](CHANGELOG.md).

## 4. Current state (2026-06-10)
- **Phases 1–4 complete.** Phase 4 CLOSED — exit gate r1 = PASS-WITH-FIXES; F1 → read-only
  account precondition ([ADR-009](adr/ADR-009-readonly-db-account-precondition.md)). Earlier
  Phase-4 pieces: Report v2 + bind-through-chokepoint ([ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)),
  `/reports` ([ADR-008](adr/ADR-008-reports-core-module-api-parity.md)), `/templates`, left-nav.
- **Phase 5 (Data Dictionary Browser & Schema Tools): CLOSED.** Exit gate **r1 = FAIL**
  (F-1 S2, metadata-only persistence not enforced) → remediated → **r2 = PASS-WITH-FIXES**
  ([r1](reviews/phase-5-review-r1.md) · [r2](reviews/phase-5-review-r2.md)). Built `4d08844 → HEAD`:
  dictionary helpers + serialization (`schema.py`); schema persistence (`core/schema_store.py`,
  [ADR-011](adr/ADR-011-schema-persistence-store.md)); **live SELECT-only introspection through
  the chokepoint** (`core/introspection.py`, [ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md));
  `/schemas` CRUD + introspect; **Schema Sources** + **Data Dictionary** UI.
- **r1/r2 remediation:** F-1 fixed (POST /schemas normalizes → metadata-only enforced);
  F-2 200-path `warnings[]` generic / 400-path → ITM-015 (Phase 7); F-3/F-4/F-5/N-1 fixed.
  Dependency pins reconciled to the validated set (`sqlglot==30.10.0` etc.).
- **160 automated tests green** (130 + 30). Commits local and **unpushed** (owner controls push).
- **Note:** `openpyxl` (declared) was missing from the local `.venv` and was installed; CI
  installs it from requirements.

## 5. Non-negotiables (must never regress)
- **SELECT/CTE only.** All DML/DDL/PL-SQL/stacked/`FOR UPDATE` rejected, fail-closed, via the single `/execute` chokepoint (`src/core/sql_safety.py`); both UI and API route through it. Verify with `tests/test_sql_safety.py` + `test_execute_endpoint.py`.
- **AI proposes SQL, never auto-runs.** User reviews/edits before execution.
- **Secrets via env only** — never commit keys; `.env` is git-ignored. Profile passwords are Fernet-encrypted at rest and never returned by the API. External LLM prompts carry **schema names only** (strict redaction).

## 6. Phase-exit review gate (every phase)
A phase is not "closed" until an **independent adversarial code review + QA** returns `PASS` / `PASS-WITH-FIXES` (no open blocking). **Reviewer ≠ author** — the **owner supplies a fresh reviewer agent**, briefed with [process/adversarial-reviewer-prompt.md](process/adversarial-reviewer-prompt.md) + the phase's change range. Loop: prepare package → review → triage to issue log → remediate blocking → re-review until PASS → record sign-off (tracker + CHANGELOG). Outputs live in `docs/reviews/phase-<N>-review-r<n>.md`.

## 7. Carried preconditions / open items
- **Gate Phase 7 (networked/multi-tenant), not blocking now:** ITM-009 (CORS `*`+credentials+`0.0.0.0` bind → restrict origins + add auth / RISK-12) and F7/ITM-010 (`base_url` host normalization — reject integer/hex/octal IP encodings).
- **Pre-GA:** manual UI + live-Oracle pass (RISK-04). See [issue-log.md](issue-log.md) / [risk-register.md](risk-register.md) for the full list.

## 8. Next action
**Open Phase 6 — "Observability & error handling" — Discovery charter**
(`docs/charters/phase-6-charter.md`): objectives; scope (structured logs, metrics, error
reference IDs, and **uniform DB-error-`detail` sanitization across all endpoints — folds in
ITM-015**); deliverables; risks; success criteria; open decisions. **Present it for owner
approval before writing code.** Then: decisions → build + tests + doc updates → owner runs the
exit-gate reviewer → remediate to PASS → close Phase 6.

**Unpushed:** all Phase-4 + Phase-5 commits are local; **push when the owner asks**. Carried
items: pre-GA manual/live-Oracle pass (RISK-04); Phase-7 preconditions (CORS/auth ITM-009,
base_url ITM-010, driver-error sanitization ITM-015, file-store durability ITM-013/014);
minor CI Python matrix (ITM-016).

First steps on resume: confirm the working tree is clean and **160 tests pass**
(`pytest tests -q`), then draft the Phase 6 Discovery charter.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial handoff after Phase 3 closure + repo relocation to ask-oracle2. |
| 1.1 | 2026-06-10 | Delivery | Phase 4 dev+test complete (118 tests); next action = R4.x exit-gate review over `3f6c03e..HEAD`. |
| 1.2 | 2026-06-10 | Delivery | Phase 4 CLOSED — gate r1 PASS-WITH-FIXES; F1–F6/R1–R2 dispositioned (F1 → ADR-009 read-only-account precondition); 130 tests. Next = Phase 5 Discovery. |
| 1.3 | 2026-06-10 | Delivery | Phase 5 dev+test complete (155 tests): dictionary browser, schema store (ADR-011), SELECT-only introspection (ADR-010), /schemas API, Data Dictionary UI. Next = R5.x exit-gate review over `6a299f8..HEAD`. |
| 1.4 | 2026-06-10 | Delivery | Phase 5 CLOSED — gate r1 FAIL (F-1) → r2 PASS-WITH-FIXES; F-1…F-5/N-1 fixed, F-2(400)→ITM-015; 160 tests. Next = Phase 6 Discovery (Observability; folds in ITM-015). |
