# Ask Oracle Reports — HANDOFF (read me first)

> **Document:** Session Handoff · **Version:** 2.0 · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-11
> **Purpose:** the single entry point for any new/resumed session. Read this, then the linked governed docs, then continue. This file is updated at the end of every working session / phase.

## 0. How to work here (operating model)
Run this project like a structured, Big-4-style delivery practice: **doc-first, phase-gated**. Keep code and governed docs updated together. Define **Next Actions** every turn. Pause and ask on scope-changing or destructive/outward-facing decisions. Maintain the task tracker, risk register, issue log, ADRs, and change log.

## 1. What this is
**Ask Oracle Reports** — a commercial, AI-assisted, **read-only** reporting layer for Oracle Database / E-Business Suite. Connect → Ask (NL→SQL) → review SQL → run → export. Stack: Python + FastAPI (`src/api.py`), Streamlit UI (`src/app.py`), an (inactive) Vite/React scaffold; `python-oracledb` thin mode; Groq/OpenAI via an OpenAI-compatible client; Docker Compose / Render.

## 2. Environment & repo
- **Local repo (git):** `D:\Ratish\Personal\Project\ask-oracle-reports-main` (branch `main`). Note: the *folder* name is legacy (`-reports-main`); it is not a tracked reference.
- **Remote:** `origin` = https://github.com/ratishkp83/ask-oracle2 (branch `main`, in sync). Push with `git push` (upstream set). `gh` is **not** installed; auth works via cached Git Credential Manager. Commit per change; **push only when the owner asks.**
- **OS/shell:** Windows / PowerShell. Python via `py -3`. Project virtualenv at `.venv` (deps installed; both `.venv` and `.env` are git-ignored).
- **Run the suite (expect 185 passed):**
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

## 4. Current state (2026-06-11)
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
- *(At Phase-5 close: 160 tests; superseded by Phase 6 below — now **185 tests** and all
  **pushed**, `main` == `origin/main`.)*
- **Phase 6 (Observability & Error Handling): CLOSED** — exit gate PASSED (**r1
  PASS-WITH-FIXES → r2 PASS**; [r1](reviews/phase-6-review-r1.md)/[r2](reviews/phase-6-review-r2.md)).
  Build B1…B6: structured JSON logging + `request_id`/`error_id`, uniform DB-error
  sanitization (**ITM-015 CLOSED**), in-process metrics + `GET /metrics`, UI surfacing
  ([ADR-012](adr/ADR-012-observability-and-error-handling.md)). New modules:
  `core/logging_config.py`, `core/errors.py` (shared by API + UI), `core/metrics.py`;
  chokepoint (`db.py`/`sql_safety.py`) unchanged. **r1 F-1/F-2** corrected a premature
  ITM-016 closure: the validated set was **re-pinned to a clean-install-proven 3.13-capable
  configuration** (numpy 2.2.6 / pandas 2.2.3 / streamlit 1.58.0 / fastapi 0.136.3 / Pillow
  11.0.0; `httpx<0.28` keeps openai 1.43.0); F-3/F-4/F-5 fixed. **185 tests.** Pushed
  (`d059295..2a88a04`); **CI run #7 green on both 3.11 + 3.13 → ITM-016 CLOSED**; no open
  residual.
- **Phase 6.5 (Pre-Deployment Hardening): build B1…B6 COMPLETE 2026-06-11** ([charter](charters/phase-6.5-charter.md) ·
  [design](pre-deployment-hardening-design.md)). Decisions D-A…D-F + design owner-approved
  same day. Delivered: **B1** opt-in `X-API-Key` auth + env-driven CORS (`core/auth.py`,
  ADR-013); **B2** `validate_base_url` numeric-encoding decode, fail-closed (ITM-010);
  **B3** `core/fileio.py` atomic writes across the 4 JSON stores (ADR-014); **B4**
  corrupt-record quarantine (skip-and-log, preserve-on-save) in report/profile/schema stores;
  **B5** ITM-017 surfaces routed (nl2sql split; SecretConfigError verbatim + breadcrumb/refs);
  **B6** governed-doc sweep — **ITM-009/010/013/014/017 CLOSED; RISK-12 Closed, RISK-16
  Mitigating (single-worker D7 constraint)**. **236 tests**; chokepoint untouched. RISK-04
  (live-Oracle pass) stays out of scope (owner-scheduled). **Exit-gate review pending** — see §8.

## 5. Non-negotiables (must never regress)
- **SELECT/CTE only.** All DML/DDL/PL-SQL/stacked/`FOR UPDATE` rejected, fail-closed, via the single `/execute` chokepoint (`src/core/sql_safety.py`); both UI and API route through it. Verify with `tests/test_sql_safety.py` + `test_execute_endpoint.py`.
- **AI proposes SQL, never auto-runs.** User reviews/edits before execution.
- **Secrets via env only** — never commit keys; `.env` is git-ignored. Profile passwords are Fernet-encrypted at rest and never returned by the API. External LLM prompts carry **schema names only** (strict redaction).

## 6. Phase-exit review gate (every phase)
A phase is not "closed" until an **independent adversarial code review + QA** returns `PASS` / `PASS-WITH-FIXES` (no open blocking). **Reviewer ≠ author** — the **owner supplies a fresh reviewer agent**, briefed with [process/adversarial-reviewer-prompt.md](process/adversarial-reviewer-prompt.md) + the phase's change range. Loop: prepare package → review → triage to issue log → remediate blocking → re-review until PASS → record sign-off (tracker + CHANGELOG). Outputs live in `docs/reviews/phase-<N>-review-r<n>.md`.

## 7. Carried preconditions / open items (none blocking; all gate Phase 7 / pre-GA)
- **Phase-7 (networked/multi-tenant) preconditions — now IN REMEDIATION under Phase 6.5**
  ([charter](charters/phase-6.5-charter.md)): ITM-009 (CORS `*`+credentials+`0.0.0.0`
  bind, **plus** unauthenticated `/health`+`/metrics` → restrict origins + add auth / RISK-12);
  F7/ITM-010 (`base_url` host normalization — reject integer/hex/octal IP encodings); ITM-013/014
  (file-store atomic writes + corrupt-record robustness / RISK-16); **ITM-017** (non-DB `str(exc)`
  surfaces — config 500 / NL→SQL 400 / a UI config path — route through the generic+`error_id`
  treatment, Phase-6 r1 F-7).
- **Pre-GA:** manual UI + **live-Oracle pass** (RISK-04 — introspection/templates/reports not yet
  validated against a real instance); legacy `connection.json` → encrypted-profile migration
  (ITM-006/RISK-09); `use_container_width` Streamlit deprecation (ITM-007); optional NL-question
  PII scrubbing (ITM-008). See [issue-log.md](issue-log.md) / [risk-register.md](risk-register.md)
  for the full list (all S3/S4, none blocking).

## 8. Next action
**Phase 6.5 — "Pre-Deployment Hardening" — Discovery OPENED 2026-06-11** (owner chose the
bundled hardening mini-phase over opening Phase 7 first). The charter
([charters/phase-6.5-charter.md](charters/phase-6.5-charter.md)) bundles the four carried code
preconditions — ITM-009 (opt-in API-key auth + env-driven CORS, incl. the `/health`+`/metrics`
posture), ITM-010 (`validate_base_url` numeric-encoding bypass), ITM-013/014 (atomic writes
across the 4 JSON stores + corrupt-record robustness), ITM-017 (non-DB `str(exc)` surfaces) —
into one charter → design → build → independent exit-gate review. RISK-04 (live-Oracle pass)
stays a separate, owner-scheduled pre-GA activity.

**Build B1…B6 is COMPLETE (2026-06-11; 236 tests green; all five carried ITMs closed).**
**The gate right now is the R6.5.x independent exit-gate review** ([gate](process/external-review-gate.md)):
prepare the review package (R6.5.1), then the **owner supplies a fresh reviewer agent**
(reviewer ≠ author, briefed with [process/adversarial-reviewer-prompt.md](process/adversarial-reviewer-prompt.md)
+ the phase change range) → triage findings → remediate blocking → re-review until
PASS / PASS-WITH-FIXES → record sign-off. After the gate: Phase 6.5 closes and Phase 7
(optional) may open, with RISK-04 (owner-scheduled live-Oracle pass) still standing pre-GA.

**First steps on resume:** confirm the working tree is clean and **236 tests pass**
(`.\.venv\Scripts\python.exe -m pytest tests -q` with the env vars in §2), then check
[task-tracker.md](task-tracker.md) R6.5.x — if the review hasn't run, the owner runs the
reviewer against the package; if findings are open, remediate and re-review.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial handoff after Phase 3 closure + repo relocation to ask-oracle2. |
| 1.1 | 2026-06-10 | Delivery | Phase 4 dev+test complete (118 tests); next action = R4.x exit-gate review over `3f6c03e..HEAD`. |
| 1.2 | 2026-06-10 | Delivery | Phase 4 CLOSED — gate r1 PASS-WITH-FIXES; F1–F6/R1–R2 dispositioned (F1 → ADR-009 read-only-account precondition); 130 tests. Next = Phase 5 Discovery. |
| 1.3 | 2026-06-10 | Delivery | Phase 5 dev+test complete (155 tests): dictionary browser, schema store (ADR-011), SELECT-only introspection (ADR-010), /schemas API, Data Dictionary UI. Next = R5.x exit-gate review over `6a299f8..HEAD`. |
| 1.4 | 2026-06-10 | Delivery | Phase 5 CLOSED — gate r1 FAIL (F-1) → r2 PASS-WITH-FIXES; F-1…F-5/N-1 fixed, F-2(400)→ITM-015; 160 tests. Next = Phase 6 Discovery (Observability; folds in ITM-015). |
| 1.5 | 2026-06-10 | Delivery | Phase 6 Discovery OPENED — charter drafted (`charters/phase-6-charter.md`); decisions D-A…D-G pending owner approval; **no code until approved**. Folds in ITM-015 (+ optional ITM-016 per D-G). |
| 1.6 | 2026-06-10 | Delivery | Phase 6 decisions resolved + design approved + **build B1…B6 complete** (182 tests; ITM-015 + ITM-016 CLOSED); review package ready. Next = owner runs the exit-gate reviewer (R6.2). |
| 1.7 | 2026-06-10 | Delivery | Phase 6 **CLOSED** — exit gate r1 PASS-WITH-FIXES (F-1/F-2 S2 dependency/CI hygiene) → re-pinned to a clean-install-proven 3.13-capable set + F-3/F-4/F-5 fixed → r2 PASS; **185 tests**. Residual: push to demonstrate CI matrix (ITM-016). |
| 1.8 | 2026-06-10 | Delivery | Pushed `d059295..2a88a04`; **CI run #7 green on both 3.11 + 3.13 → ITM-016 CLOSED.** Phase 6 fully closed, no open residual. |
| 1.9 | 2026-06-10 | Delivery | Resume-readiness pass: removed stale §8 leftovers ("draft Phase 6 charter"/"160 tests"/"unpushed"); §4/§7 reconciled (185 tests, all pushed, carried items incl. ITM-017); next = Phase 7 (optional) or owner direction. |
| 2.0 | 2026-06-11 | Delivery | Phase 6.5 (Pre-Deployment Hardening) Discovery OPENED — bundles ITM-009/010/013/014/017 (RISK-12/16) into one gated mini-phase; charter drafted; next action = owner resolves decisions D-A…D-F before any code. |
| 2.1 | 2026-06-11 | Delivery | P6.5 decisions D-A…D-F resolved (all as recommended); design + build sequence B1…B6 drafted (`pre-deployment-hardening-design.md`); next action = owner approves the design before any code. |
| 2.2 | 2026-06-11 | Delivery | P6.5 design approved + build B1…B6 complete (236 tests; ITM-009/010/013/014/017 CLOSED; RISK-12 Closed/RISK-16 Mitigating; ADR-013/014). Next action = R6.5.x exit-gate review (owner-supplied reviewer). |
