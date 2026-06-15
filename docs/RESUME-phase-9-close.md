# RESUME — after Phase 9 close (read me to start a new session)

> **Document:** Session resume brief · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-15 · **HEAD:** `96b0e18` (branch `v2`)
> **Purpose:** a self-contained prompt to resume Ask Oracle Reports **v2** in a fresh session. Paste the block below (or just read this file). Phase 9 is CLOSED — pick up from a clean, fully-gated state.

---

Resume Ask Oracle Reports v2. Phase 9 (React CXO UI) is CLOSED — pick up from a clean, fully-gated state. Read the docs first, confirm gates, then ask me what to tackle. Do NOT auto-run a plan: this project uses a review-gate at every checkpoint (build → gates → internal review → present → HOLD for my sign-off).

## Workspace & freeze
- Repo at the junction `D:\Ratish\Personal\Project\aor-v2` (the real dir name has a space — always use the junction). Branch: `v2`. Windows/PowerShell; Python via `.\.venv\Scripts\python.exe`.
- **LOCAL COMMITS ONLY — NO PUSH** until the GitHub/usage limit resets (~start of July 2026). The entire v2 (Phases 8 + 9) is committed locally and awaits that push. Never commit secrets.

## Current state (HEAD `96b0e18`, 2026-06-15)
- Phase 8 (email a report) CLOSED. Phase 9 (bespoke React CXO surface under `web/`, against the existing `/v1` FastAPI; Streamlit stays the admin tool) CLOSED:
  - B5b live Query Builder + cascading; B6 the four supporting screens (Connections, Data dictionary, Reports, Settings); B7 broader acceptance.
  - Post-B7 fixes: user-readable errors (ADR-024), report parameter value-pickers incl. run-time FK auto-derivation (ADR-023), off-topic/missing-column/consistent-decline NL guard (ADR-025), Auto-run toggle UX.
  - Owner CXO acceptance SIGNED OFF + independent exit-gate review r1 = PASS-WITH-FIXES (reviewer ≠ author; 5 S4 findings remediated/accepted).
- Gates green: **pytest 433 · vitest 130 · tsc clean · vite build**.

## Read first (source of truth = repo `/docs`)
1. `docs/HANDOFF.md` (the Phase-9 banner at top). 2. `docs/CHANGELOG.md` ([Unreleased]). 3. `docs/reviews/phase-9-b6b7-review-r1.md` + `phase-9-b7-acceptance.md`. 4. `docs/roadmap.md`. 5. `docs/adr/` (ADR-019..025). Also the assistant memory `project_ask_oracle_reports_v2.md`.

## Gates (run from the junction)
- `.\.venv\Scripts\python.exe -m pytest -q`            (433)
- `.\node_modules\.bin\vitest run`                      (130)
- `.\node_modules\.bin\tsc --noEmit -p tsconfig.json`   (clean)
- `.\node_modules\.bin\vite build`                       (green)

## Run / verify (this dev box)
- Backend runs on **PORT 8010** (NOT 8000 — `sentinel-pmo-ai` owns 8000). Launch entry **`ask-oracle-api`** (uvicorn 8010). Dev servers proxy `/v1` → 8010 via `AOR_API_TARGET`, set in the `ask-oracle-web`/`-verify` entries of `C:\Users\ratis\.claude\launch.json`.
- Servers: `ask-oracle-web` (5174, owner reviews here), `ask-oracle-web-verify` (5175, agent screenshots). **Preview-managed servers get reaped between turns** — restart via `preview_start` of `ask-oracle-api` / `ask-oracle-web` / `ask-oracle-web-verify`; confirm with `GET http://127.0.0.1:8010/v1/health` (200) and `http://localhost:5174/v1/health`.
- Live data: XE listener `OracleOraDB21Home1TNSListener` + `OracleServiceXE` must be Running; profile "XE (read-only)" has `current_schema=AOR_DEMO`; a saved AOR_DEMO schema exists (DEPARTMENTS, EMPLOYEES). Screenshot tool is flaky → prefer `preview_eval` DOM/console assertions; verify at 1366×768.

## Invariants (never regress)
SELECT-only chokepoint (SQL only via `/execute` & `/reports/{id}/run`); AI-proposes/approve (Auto-run default-off is the only sanctioned skip; chokepoint still applies; off-topic guard never runs SQL); schema-names-only to the LLM (derivation is local); no client-side DB secrets (connections by `profile_id`; passwords/LLM key transient, never localStorage); sanitized errors with `error_id` (never raw driver text).

## Operating model
Big-4 doc-first, phase-gated, discovery-before-build; opinionated tradeoff-driven discovery before code; REVIEW-GATE + HOLD-for-sign-off at every checkpoint; independent adversarial exit-gate per phase (reviewer ≠ author, ADR-006).

## Open backlog (non-blocking)
- **ITM-034**: rename "Introspect" → plainer wording (Data dictionary; bar B-4). Files: `web/src/features/dictionary/IntrospectDialog.tsx` + `DataDictionaryPage.tsx`.
- **ITM-026**: dynamic Ask example chips (needs query history).
- **ITM-031**: frontend ESLint debt (vendored-shadcn-dominated; not a CI gate).

## First step
Read the docs above, run the four gates to confirm green, then ask the owner whether to: (a) do ITM-034, (b) start the next phase per `docs/roadmap.md` (discovery + charter for owner sign-off BEFORE coding), or (c) something else. End goal for the product: **fully intelligent + cascading reporting**.
