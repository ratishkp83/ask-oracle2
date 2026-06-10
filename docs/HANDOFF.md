# Ask Oracle Reports — HANDOFF (read me first)

> **Document:** Session Handoff · **Version:** 1.1 · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-10
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
- **Phases 1–3 complete.** Phase 3 CLOSED via the gate (r1 FAIL → r2 `PASS-WITH-FIXES`).
- **Phase 4 (Reports, Templates & UX): DEV + TEST COMPLETE, exit gate pending.** Built across
  `78f1ad3 → HEAD`: Report v2 store + legacy migration (`core/reports.py`); **bind variables
  through the chokepoint** (`db.py:validate_binds`, `/execute` `binds`; [ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md));
  `/reports` CRUD + `/reports/{id}/run` sharing `_run_sql` ([ADR-008](adr/ADR-008-reports-core-module-api-parity.md));
  13 curated EBS templates (`core/templates.py`, `/templates`); left-nav UI with Reports +
  Templates sections. Design: [reports-templates-ux-design.md](reports-templates-ux-design.md).
- **118 automated tests green** (75 + 43 new). Commits are local and **unpushed** (owner controls push).

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
**Run the Phase 4 exit gate (R4.x).** Development + testing are complete; the remaining
step is the mandatory **independent adversarial review + QA** (reviewer ≠ author). The
**owner supplies a fresh reviewer agent** briefed with
[process/adversarial-reviewer-prompt.md](process/adversarial-reviewer-prompt.md) over the
Phase-4 change range **`3f6c03e..HEAD`**. Reviewer focus areas: the bind-through-chokepoint
change (can a parameter value defeat SELECT-only? — see `test_bind_safety.py`), `/reports`
run path, legacy report migration, and the left-nav UX. Then: triage → remediate blocking
→ re-review until **PASS** → record sign-off (tracker + CHANGELOG) → **push when the owner
asks**.

First steps on resume: confirm the working tree is clean and **118 tests pass**
(`pytest tests -q`), then proceed with the R4.x exit-gate review.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial handoff after Phase 3 closure + repo relocation to ask-oracle2. |
| 1.1 | 2026-06-10 | Delivery | Phase 4 dev+test complete (118 tests); next action = R4.x exit-gate review over `3f6c03e..HEAD`. |
