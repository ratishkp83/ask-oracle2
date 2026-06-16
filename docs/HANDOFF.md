# Ask Oracle Reports — HANDOFF (read me first)

> **Document:** Session Handoff · **Version:** 3.9 · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-15 (ITM-034 closed)
> **Purpose:** the single entry point for any new/resumed session. Read this, then the linked governed docs, then continue. This file is updated at the end of every working session / phase.

> ---
> ### 🟢 v2 ACTIVE — Phase 10 Discovery OPENED (charter APPROVED 2026-06-15) · Phase 9 CLOSED
> **Phase 10 — Cascading Report Deliverables + Local Insight Narration** ([charter](charters/phase-10-cascading-reports.md),
> 🟢 approved). Advances the end goal "fully intelligent + cascading reporting": a **styled single-file HTML
> bundle** (parent summary → narrated KPIs → nested per-value child sections) you can **download or email**,
> plus **local, deterministic insight narration** (no LLM, no row egress). Decisions D-A…D-H resolved. Architecture:
> **client-orchestrated fan-out reusing the TS `derive/*` layer**; each cascade child is a `pullDetail`-style
> deterministic derivation of the **approved** parent through the existing `/execute` chokepoint (all five
> invariants hold). **OUT/deferred:** conversational Ask, semantic layer, scheduling, LLM-phrased insight,
> PDF/Excel, query history. Build plan B1 charter ✓ → B2 design + ADR-026/027 ✓ → B3 insight engine ✓ →
> B4 fan-out + bundle + download ✓ → B5 (a backend cascade-persistence + `/reports/email-bundle`; b frontend
> "Report" dialog Download/Email/Save + live fan-out) ✓ → **B6 docs + exit-gate = IN PROGRESS** (owner
> approved B5; doc sweep + complete product test done — **`tsc --build` clean · vitest 158 · vite build ·
> pytest 446 · OpenAPI 3.1.0 / 42 paths** — independent exit-gate review next). **Typecheck gate = `tsc --build`** (BUG-013: the previously-used
> `tsc --noEmit -p tsconfig.json` is a **no-op** — root `tsconfig.json` has `files:[]` + project
> references, so without `--build` it checks **zero** files; verified by a deliberate type error passing
> it while `tsc --build` caught it). `*.tsbuildinfo` is git-ignored. **Local commits only; NO PUSH until the July reset.**
>
> ### Phase 9: React CXO UI · B6 supporting screens COMPLETE (2026-06-15)
> **Workspace:** `D:\Ratish\Personal\Project\ask-oracle-reports-main v2` (junction `…\aor-v2`),
> branch **`v2`** — **local commits only; NO PUSH until the July limit reset.** Charter
> [phase-9-react-cxo-ui.md](charters/phase-9-react-cxo-ui.md). The bespoke **React** executive surface
> (`web/`) is built against the existing `/v1` FastAPI; Streamlit stays as the admin tool.
> **B5b** (live Query Builder + intelligent cascading) closed earlier — exit-gate r1 = PASS; details in
> [CHANGELOG.md](CHANGELOG.md) + [reviews/phase-9-b5b-review-r1.md](reviews/phase-9-b5b-review-r1.md).
> **B6 — the four supporting screens — COMPLETE**, built one packet at a time with a review-gate +
> HOLD-for-sign-off at every checkpoint (owner-driven): **Connections** (list/add/test/delete profiles,
> default-schema, password posted once — closes the E10 handoff), **Data dictionary** (saved schemas with
> table/column PK·FK detail + live introspect, and the curated EBS packs — closes E11), **Reports**
> (saved-report list/run/create/edit/delete + start-from-template, reusing the executive Results view +
> export/email), and **Settings** (per-session LLM override [ADR-004] wired into Ask + server-managed
> status copy; no backend change). Cross-cutting: **user-readable errors everywhere**
> ([ADR-024](adr/ADR-024-user-readable-error-presentation.md) — no developer text to users; `error_id`
> kept), a shared **ConfirmDialog**, and **report parameter value-pickers**
> ([ADR-023](adr/ADR-023-report-parameter-value-pickers.md) — explicit lookup + FK "Suggest" + **run-time
> auto-derivation** from SQL binds × dictionary FKs, all via the SELECT-only chokepoint).
> **428 backend / 128 frontend / tsc clean / vite build green.** Verified live end-to-end vs XE 21c
> (AOR_DEMO): all four screens at 1366×768 (no full-page scroll), report run → Results, friendly DB-error
> copy, and live FK dropdowns. **HEAD `74037d4`.** All five invariants hold (chokepoint; AI-proposes /
> approve incl. Auto-run; schema-names-only to the LLM; no client DB secrets; sanitized `error_id` errors).
> **B7 broader acceptance COMPLETE** ([reviews/phase-9-b7-acceptance.md](reviews/phase-9-b7-acceptance.md)) +
> post-B7 owner-found fixes (user-readable errors [ADR-024], report value-pickers + run-time FK
> auto-derivation [ADR-023], off-topic/missing-column/consistent-decline NL guard [ADR-025], Auto-run
> toggle UX). **Owner CXO acceptance SIGNED OFF 2026-06-15** (criterion #3). **Independent exit-gate review
> r1 = PASS-WITH-FIXES** (reviewer ≠ author, ADR-006; [reviews/phase-9-b6b7-review-r1.md](reviews/phase-9-b6b7-review-r1.md)):
> all 4 gates re-run green + all 5 invariants verified; 5 findings, **all S4**, remediated/accepted →
> **🎉 PHASE 9 CLOSED** (all §15 exit criteria met). **433 backend / 130 frontend / tsc clean / vite build.**
> Open backlog (non-blocking): **ITM-026** (dynamic Ask chips), **ITM-031** (frontend ESLint debt).
> **ITM-034 CLOSED 2026-06-15** — the Data dictionary's "Introspect" reworded to owner-approved
> "Read from database" (display-only; code/API/`source` enum unchanged; gates 433/130; live-verified).
> Ops: backend on **8010** (coexists with sentinel on 8000) via the
> `ask-oracle-api` launch entry; dev servers proxy via `AOR_API_TARGET`. **All Phase-9 work is local-only
> — still NO PUSH until the July reset.**
> **Phase 8 (email) CLOSED 2026-06-13.** Everything in §0–§7 below is **v1 history on `main`**.
> ---

## 0. How to work here (operating model)
Run this project like a structured, Big-4-style delivery practice: **doc-first, phase-gated**. Keep code and governed docs updated together. Define **Next Actions** every turn. Pause and ask on scope-changing or destructive/outward-facing decisions. Maintain the task tracker, risk register, issue log, ADRs, and change log.

## 1. What this is
**Ask Oracle Reports** — a commercial, AI-assisted, **read-only** reporting layer for Oracle Database / E-Business Suite. Connect → Ask (NL→SQL) → review SQL → run → export. Stack: Python + FastAPI (`src/api.py`), Streamlit UI (`src/app.py`), an (inactive) Vite/React scaffold; `python-oracledb` thin mode; Groq/OpenAI via an OpenAI-compatible client; Docker Compose / Render.

## 2. Environment & repo
- **Local repo (git):** `D:\Ratish\Personal\Project\ask-oracle-reports-main` (branch `main`). Note: the *folder* name is legacy (`-reports-main`); it is not a tracked reference.
- **Remote:** `origin` = https://github.com/ratishkp83/ask-oracle2 (branch `main`, in sync). Push with `git push` (upstream set). `gh` is **not** installed; auth works via cached Git Credential Manager. Commit per change; **push only when the owner asks.**
- **OS/shell:** Windows / PowerShell. Python via `py -3`. Project virtualenv at `.venv` (deps installed; both `.venv` and `.env` are git-ignored).
- **Run the suite (expect 307 passed):**
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
  Mitigating (single-worker D7 constraint)**. Chokepoint untouched. **Exit-gate review r1 =
  PASS-WITH-FIXES** ([phase-6.5-review-r1.md](reviews/phase-6.5-review-r1.md); no S1/S2) →
  **all four findings remediated** (R1 Unicode fullwidth-digit SSRF NFKC-fold, R2 fd-close on
  error path, R3 blank-`ALLOWED_ORIGINS` fallback, R4 D7 doc) → **242 tests**. RISK-04
  (live-Oracle pass) stays out of scope (owner-scheduled). **CLOSED on r1 by owner direction (no
  r2) 2026-06-11; pushed `2ba0a56..9209e3a`.** CI-matrix green confirmation on the pushed commit
  is deferred to Round C1.
- **Round C1 (Pre-GA Consolidation & Testing): CLOSED 2026-06-12** ([charter](charters/round-C1-charter.md) ·
  [design](round-C1-design.md) · [GA verdict](round-C1-ga-readiness.md)). Delivered ITM-007/006/008
  (closed), the **live-Oracle pass vs XE 21c + owner UI browser-test (RISK-04 Closed)**, and the CI
  green confirmation. Exit-gate review r1 PASS-WITH-FIXES → F1/F2 remediated; **262 tests**.
  **GA-readiness verdict: GA-ready core product subject to deployment preconditions; EBS pack beta
  pending ITM-012.** See §8.

## 5. Non-negotiables (must never regress)
- **SELECT/CTE only.** All DML/DDL/PL-SQL/stacked/`FOR UPDATE` rejected, fail-closed, via the single `/execute` chokepoint (`src/core/sql_safety.py`); both UI and API route through it. Verify with `tests/test_sql_safety.py` + `test_execute_endpoint.py`.
- **AI proposes SQL, never auto-runs.** User reviews/edits before execution.
- **Secrets via env only** — never commit keys; `.env` is git-ignored. Profile passwords are Fernet-encrypted at rest and never returned by the API. External LLM prompts carry **schema names only** (strict redaction).

## 6. Phase-exit review gate (every phase)
A phase is not "closed" until an **independent adversarial code review + QA** returns `PASS` / `PASS-WITH-FIXES` (no open blocking). **Reviewer ≠ author** — the **owner supplies a fresh reviewer agent**, briefed with [process/adversarial-reviewer-prompt.md](process/adversarial-reviewer-prompt.md) + the phase's change range. Loop: prepare package → review → triage to issue log → remediate blocking → re-review until PASS → record sign-off (tracker + CHANGELOG). Outputs live in `docs/reviews/phase-<N>-review-r<n>.md`.

## 7. Carried preconditions / open items (none blocking)
- **Phase-7 (networked/multi-tenant) code preconditions — ALL CLEARED under Phase 6.5**
  ([charter](charters/phase-6.5-charter.md)): ITM-009 (auth + CORS / RISK-12), ITM-010 (`base_url`
  encodings incl. the r1/R1 Unicode fold), ITM-013/014 (atomic writes + quarantine / RISK-16),
  ITM-017 (non-DB error surfaces) — **all closed**. The only remaining gate for a networked
  deploy is **RISK-04** (live-Oracle pass).
- **Pre-GA — now carried into Round C1** ([charter](charters/round-C1-charter.md)): the CI-matrix
  green confirmation on `9209e3a`; manual UI + **live-Oracle pass** (RISK-04 — owner provides a
  read-only instance); legacy `connection.json` → encrypted-profile migration (ITM-006/RISK-09);
  `use_container_width` Streamlit deprecation (ITM-007); optional NL-question PII scrubbing
  (ITM-008). See [issue-log.md](issue-log.md) / [risk-register.md](risk-register.md) (all S3/S4).

## 8. Next action
**Phase 6.5 — "Pre-Deployment Hardening" — CLOSED 2026-06-11.** Full lifecycle in one day:
Discovery → decisions D-A…D-F → design → build B1…B6 → independent exit-gate review
**r1 = PASS-WITH-FIXES** (no S1/S2; [phase-6.5-review-r1.md](reviews/phase-6.5-review-r1.md),
reviewer ≠ author) → all four findings remediated (R1 Unicode-digit SSRF NFKC-fold, R2 fd-close,
R3 blank-`ALLOWED_ORIGINS` fallback, R4 D7 doc) → **closed on r1 by owner direction (no r2)**.
**242 tests; pushed `2ba0a56..9209e3a`** (`main` == `origin/main`). The CI 3.11+3.13 matrix runs
on that push; **green confirmation is carried into Round C1** (no `gh` on the dev box — confirm
in the Actions tab).

**Active work = Round C1 — Pre-GA Consolidation & Testing — building 2026-06-11**
([charter](charters/round-C1-charter.md) · [design](round-C1-design.md)). Decisions resolved
(D-A **owner has Oracle XE** → live pass runs this round, EBS templates still ITM-012; D-B full
scope; D-C build ITM-008 behind a default-off flag). Build order B1…B6:
- **B1 — ITM-007 DONE:** 14 `use_container_width=True` → `width="stretch"` in `app.py`; **ITM-007
  CLOSED**; 242 tests.
- **B2 — ITM-006 DONE:** `connection.json` write path retired (`save_connection_config` removed,
  Save button gone); `migrate_legacy_connection()` reads-and-deletes any legacy file at startup
  (also clears any pre-F5 plaintext file). **ITM-006 CLOSED, RISK-09 Closed**; 245 tests.
- **B3 — ITM-008 DONE:** `core/llm/pii.py` opt-in NL-question PII scrubbing behind default-off
  `SCRUB_PII` (external send only; local verbatim; email/SSN/card/phone masked). **ITM-008
  CLOSED**; 260 tests. *(All C1 code items B1–B3 complete.)*
- **B4 — CI confirm DONE:** owner confirmed in the Actions tab — **CI run #12 green** on `f374380`
  (B1–B3 head), plus #10 (`9209e3a`) + #11 (`a395003`) green; a green run = both 3.11 + 3.13 legs.
- **B5 — RISK-04 live pass DONE + UI browser-tested → RISK-04 Closed:** XE 21c on this machine
  (read-only `aor_readonly` + `aor_demo` sample in `XEPDB1`; conn in git-ignored `.env` `AOR_LIVE_*`).
  `scripts/c1_live_smoke.py` drove the real product code → **ALL PASS**
  ([evidence](reviews/round-C1-live-pass.md)); the **owner also browser-tested the Streamlit UI
  against XE satisfactorily 2026-06-12**. EBS-template validation stays ITM-012 (needs real EBS).
- **RC1 DONE:** independent exit-gate review **r1 = PASS-WITH-FIXES** (no S1/S2;
  [round-C1-review-r1.md](reviews/round-C1-review-r1.md)) → both findings remediated
  (C1-R1-F1 storage delete-failure now logs a warning; C1-R1-F2 load TOCTOU → try/except); 262 tests.
- **B6 DONE — Round C1 CLOSED:** GA-readiness verdict recorded
  ([round-C1-ga-readiness.md](round-C1-ga-readiness.md)) — **GA-ready for the core read-only
  reporting product** subject to the §5 deployment preconditions; the **EBS template pack is beta
  pending ITM-012**.

**Deployment GA-readiness hardening COMPLETE (2026-06-12)** — post-Phase-7 unplanned improvement, no gate required (no app/chokepoint code changed). DH-1…DH-6: `render.yaml` now declares `APP_SECRET_KEY`/`APP_API_KEY`/`ALLOWED_ORIGINS` + `LOG_LEVEL`/`LOG_FORMAT`/`STORAGE_DIR`; Dockerfiles pinned to Python 3.13-slim (CI matrix); `docker-compose.yml` adds Compose profiles (`--profile api|ui|frontend`), named `storage` volume, and the missing Streamlit `ui` service; `.env.example` adds 6 missing vars; D7 v1.6 updated. **BUG-006 fixed** (Dockerfiles were silently excluded from git since repo init by the Vite `*.local` gitignore glob — negation exceptions added). **ITM-019 opened** (Render ephemeral storage — deployment architecture decision, see issue log). Pushed `1c1abf2..f353ebc`; 293 tests unchanged.

**Project state: ALL PHASES CLOSED (2026-06-12) — Phases 1–6, 6.5, Round C1, and Phase 7.**
Phase 7 exit-gate review r1 = **PASS** ([phase-7-review-r1.md](reviews/phase-7-review-r1.md); no
blocking; all 7 invariants) → two S4 findings remediated (P7-R1-F1 `ebs_modules` unknown→422;
P7-R1-F2 `/v1` POST auth tests) → **293 tests**. **Phase 7 CLOSED.** Standing carries (both need
external access, not code): **ITM-012** (validate EBS pack/template contents vs a real EBS — the
validator `scripts/ebs_pack_validate.py` + [self-audit](reviews/ebs-pack-self-audit.md) are ready);
**ITM-018** (the deferred Oracle 23ai vector track — needs a 23ai instance).

----

**Phase 7 (what shipped, for reference) — build B1…B7 COMPLETE (2026-06-12):** Decisions resolved (defer 23ai / 5 modules core /
read-only / fold in `/v1`). Delivered ([design](ebs-intelligence-design.md)): **B1**
`core/ebs_packs.py` curated packs + glossary for GL/AP/AR/PO/OM ([ADR-015](adr/ADR-015-ebs-metadata-packs.md));
**B2** opt-in `ebs_modules` NL→SQL context (external-only, combined context through
`assert_no_values`); **B3** UI (Data Dictionary packs browser + Query Builder module multiselect);
**B4** read-only `/packs` API; **B5** `/v1` prefix via APIRouter mounted twice (**T-18 CLOSED**;
back-compat + auth + safety preserved); **B6** 23ai deferral ([ADR-016](adr/ADR-016-defer-23ai-vector-track.md),
**ITM-018**); **B7** doc sweep. **285 tests; chokepoint + redaction untouched.** Pack contents
still need real-EBS validation (ITM-012).

Exit-gate review **r1 = PASS** → P7-R1-F1/F2 (S4) remediated → **293 tests**. **Phase 7 CLOSED.**

**Open carries (two items; nothing is pending in code):**
- **ITM-012** — EBS pack + template validation vs a real EBS 12.2 instance (tooling ready: `scripts/ebs_pack_validate.py` + `docs/reviews/ebs-pack-self-audit.md`; gated on access).
- **ITM-018** — Oracle 23ai vector track (deferred per ADR-016; needs a 23ai instance to charter).

**ITM-011 CLOSED (2026-06-12):** `expand_list_binds` in `src/db.py`; `"list"` ParamType in `reports.py`; 14 new tests → **307 total**.
**ITM-019 CLOSED:** Render Disk decision; `render.yaml` commented `disk:` blocks; D7 §5.

**First steps on resume:** confirm the working tree is clean and **307 tests pass**
(`.\.venv\Scripts\python.exe -m pytest tests -q` with the env vars in §2). **Nothing is pending in
code** — all planned phases + ITM-011/019 are closed. Future work is owner-initiated: **ITM-012** (run
`scripts/ebs_pack_validate.py` against a real EBS 12.2 instance to validate pack/template contents)
and **ITM-018** (open a chartered 23ai effort once a 23ai instance exists). *(XE setup persists on
this box for the core product: listener `OracleOraDB21Home1TNSListener` must be running, then
`python scripts/c1_live_smoke.py`; the Streamlit UI runs via preview server `ask-oracle-ui` →
localhost:8501 with the pre-loaded "XE (read-only)" profile.)*

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
| 2.3 | 2026-06-11 | Delivery | P6.5 exit-gate review r1 = PASS-WITH-FIXES (no S1/S2); all four findings remediated (R1 Unicode SSRF NFKC-fold, R2 fd-close, R3 blank-CORS fallback, R4 doc) → 242 tests. Gate cleared; closure (R6.5.4) pending optional r2 spot-check + push. |
| 2.4 | 2026-06-11 | Delivery | **Phase 6.5 CLOSED** (on r1, no r2, per owner) + pushed `2ba0a56..9209e3a`. **Round C1 (Pre-GA Consolidation & Testing) opened** — carries CI-green confirmation, RISK-04 live pass, ITM-006/007/008; decisions D-A…D-C pending owner. |
| 2.5 | 2026-06-11 | Delivery | Round C1 decisions resolved (XE / full scope / build ITM-008); design + XE runbook done; **B1 ITM-007 CLOSED** (242 tests). Next = B2 ITM-006, B3 ITM-008; B5 live pass awaits owner XE setup (design §6). |
| 2.6 | 2026-06-11 | Delivery | **B2 ITM-006 CLOSED / RISK-09 Closed** (connection.json write path retired); 245 tests. |
| 2.7 | 2026-06-11 | Delivery | **B3 ITM-008 CLOSED** (opt-in `SCRUB_PII` PII scrubbing); 260 tests; all C1 code items (B1–B3) done. |
| 2.8 | 2026-06-11 | Delivery | **B5 RISK-04 live-Oracle pass against XE 21c: ALL PASS** (`scripts/c1_live_smoke.py`; evidence `reviews/round-C1-live-pass.md`); RISK-04 Med→Low. Remaining: B4 CI confirm, RC1 review, B6 verdict. |
| 2.9 | 2026-06-12 | Delivery | **B4 done** (owner confirmed CI run #12 green) + **owner UI browser-test against XE satisfactory → RISK-04 Closed**; RC1.1 review package prepared. Remaining: RC1.2 independent review (owner-supplied) → B6 GA verdict. §8 stale-duplicate cleaned. |
| 3.0 | 2026-06-12 | Delivery | **Round C1 CLOSED** — RC1 review r1 PASS-WITH-FIXES → F1/F2 remediated (262 tests); **B6 GA-readiness verdict recorded** (GA-ready core product; EBS pack beta/ITM-012). **Phases 1–6 + 6.5 + C1 all closed; only Phase 7 (optional) remains.** |
| 3.1 | 2026-06-12 | Delivery | Phase 7 Discovery OPENED — EBS metadata packs + glossary (primary) vs 23ai vector (decide-deliberately; XE 21c constraint) + optional fold-ins; next action = owner resolves decisions D-A…D-D before any code. |
| 3.2 | 2026-06-12 | Delivery | Phase 7 build **B1…B7 COMPLETE** (285 tests; ADR-015/016; T-18 CLOSED; ITM-018): EBS packs + glossary, opt-in NL→SQL context, `/packs`, UI, `/v1` prefix, 23ai deferral. Next = R7.2 independent exit-gate review (owner-supplied). |
| 3.3 | 2026-06-12 | Delivery | **Phase 7 CLOSED** — exit-gate review r1 = PASS (no blocking); P7-R1-F1/F2 (S4) remediated → 293 tests; ITM-012 validation method (validator + self-audit) shipped. **ALL PHASES CLOSED.** Carries: ITM-012, ITM-018 (need external access). |
| 3.4 | 2026-06-12 | Delivery | **Deployment GA-readiness hardening COMPLETE** — DH-1…DH-6: render.yaml security vars + Python 3.13; Dockerfiles pinned to 3.13-slim; docker-compose profiles + named volume + Streamlit ui service; .env.example 6 missing vars; D7 v1.6. BUG-006 fixed (Dockerfiles were untracked). ITM-019 RESOLVED (Render Disk). Pushed `f353ebc`. |
| 3.5 | 2026-06-12 | Delivery | **ITM-011 CLOSED** — `expand_list_binds` in `src/db.py` (list→`:name_0,:name_1,…` safe expansion; safety check on original SQL); `validate_binds` accepts non-empty flat lists; `"list"` ParamType + `_coerce_value` in `reports.py`; 14 new tests → **307 total**. Open carries: ITM-012, ITM-018. |
| 2.6 | 2026-06-11 | Delivery | **B2 ITM-006 CLOSED** (RISK-09 Closed): `connection.json` write path retired, read-and-delete migration; 245 tests. Next = B3 ITM-008. |
| 2.7 | 2026-06-11 | Delivery | **B3 ITM-008 CLOSED**: `core/llm/pii.py` opt-in PII scrubbing (`SCRUB_PII`); 260 tests. All C1 code (B1–B3) done. Remaining: B4 CI confirm, B5 XE live pass, RC1 review, B6 verdict. |
