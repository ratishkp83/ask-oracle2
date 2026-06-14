# Resume Prompt — Phase 9 B5b: live wiring + SQL-aware intelligence + edge cases

> Paste the block below into a new Claude Code session to resume. It is self-contained.
> Saved 2026-06-14 after B5a (executive Results view + drill-down + CSV/Excel/Email) was
> built, reviewed, and committed. The owner asked to make the reporting/drill-down
> **intelligent per the query** and to **handle the no-data / over-data edge cases** — done in a
> fresh session.

---

## RESUME PROMPT (copy from here)

Resume **Ask Oracle Reports v2 — Phase 9 B5b: live Query Builder + SQL-aware intelligent derivation + edge-case hardening**.

### Workspace & state
- Repo: `D:\Ratish\Personal\Project\ask-oracle-reports-main v2` (note the space). Branch `v2`, **HEAD `7fc1f89`**.
- Junction `D:\Ratish\Personal\Project\aor-v2` → the repo (use it; the space breaks some tools).
- **LOCAL COMMITS ONLY — no push** until the July GitHub-Actions reset. Commit at green checkpoints; flag (don't gate) irreversible ops.
- Backend test gate: `.\.venv\Scripts\python.exe -m pytest -q` (**422 passing**).
- **Owner workflow (non-negotiable): a REVIEW GATE at every checkpoint** — finish a unit, *review it (correctness + invariants + the CXO design bar, verified in the running app), present findings, and HOLD for sign-off before advancing.* Do not auto-run the plan to completion.

### What's already built (Phase 9: B1–B5a, all committed locally)
- **Charter (approved):** `docs/charters/phase-9-react-cxo-ui.md` — design system, invariants, build plan B1…B8, owner decisions (Fraunces + deep-petrol `#0E5C63` + warm-paper canvas `#F7F6F3`, light-only beta, core-first). Read it first.
- **Backend (additions to `src/api.py`, root + `/v1`, auth-gated, tested):**
  - `POST /reports/email` — emails the *shown* result (columns+rows) via the Phase-8 mailer. No LLM, no re-query; opt-in `503`; SendResult→HTTP (ok/200, rejected/400, transport-error/502 w/ mailer `error_id`); payload cap 100k×1k. `tests/test_email_api.py`.
  - `POST /reports/export` — server-side CSV/xlsx download (openpyxl; **no spreadsheet lib in the browser**); filename sanitized; same cap. `tests/test_export_api.py`.
- **Frontend (`web/`):** Vite+React+TS+Tailwind+Radix/shadcn. **The repo root stays the npm/Vite project** (reuses the installed `node_modules`); Vite `root: 'web'`. `src/` is pure Python again; the 49 shadcn primitives live in `web/src/components/ui`.
  - **Space-in-path gotcha (keep this):** Vite 5.4.1's dev dep-optimizer crashes on the `%20` `node_modules` path under Node 24. Fixed in `vite.config.ts` by pinning `vite@^5.4.20` + `resolve.preserveSymlinks: true` + deriving `root`/alias from `process.cwd()` (NOT `__dirname`, which realpaths back to the spaced dir). Run Vite from the junction so `process.cwd()` is space-free.
  - **Design system:** `web/src/styles/tokens.css` (shadcn vars re-aliased to the approved palette; Inter body + Fraunces display; `.num` = tabular numerals). App shell: `web/src/app/{AppShell,TopBar,LeftRail,providers}.tsx` (top bar has a live `/health` badge). Typed client: `web/src/lib/api/{client,endpoints,schemas}.ts` (Zod at the boundary; `ApiError` surfaces `error_id`). TanStack Query.
  - **Executive Results view (B5a) — the core:** `web/src/components/exec/` = `SummaryBand`, `KpiCard`, `DriverChart` (Recharts), `ResultGrid` (TanStack Table + Virtual, **the only scroll region**), `EmailDialog`, `ResultsView` (composes the four bands + a reusable `ResultScope` + drill-down + `NoBreakdown`).
  - **Local derivation (the "intelligence" today):** `web/src/lib/derive/` = `columns.ts` (`classifyColumns` by name tokens + value sampling; `rankMeasures`), `kpis.ts` (`deriveKpis`), `chart.ts` (`pickChart`, bar/line auto-pick, `exclude` for drill). `web/src/lib/format.ts` (formatting; tabular; whole-number integer columns). **All derivation is local/deterministic — NO row data to the LLM.**
  - **Drill-down:** click a chart bar → the whole view re-scopes to that value (scoped KPIs + breakdown chart on the *next* dimension + filtered grid + Back). A single-record value → a "No further breakdown" state + **"Pull <value> data"** that seeds an Ask question.
  - **Export/share:** CSV (client), Excel (server `/reports/export`), Email (`/reports/email`, recipient-confirmed, "the email is real").
  - **Preview harness:** "See a sample result" on the Ask page renders `web/src/features/ask/sampleResult.ts` (category-level) so the design is viewable without a live DB.

### Non-negotiable invariants (carry)
1. **SELECT/CTE-only chokepoint** (`src/db.py`, `src/core/sql_safety.py`, `POST /execute`) is sacred. React runs SQL only via `/execute`.
2. **AI proposes, user approves** — `/nl2sql` returns SQL for review; the human triggers `/execute`.
3. **Schema-names-only to the LLM** — NEVER send row/cell data to any model. This governs the new "intelligence" too: derivation must stay local/deterministic; the LLM may only see **schema/column names + the question**, never rows.
4. **Secrets via env, server-side** — the React app never holds DB passwords (connections by `profile_id`).
5. **Sanitized errors with `error_id`** — friendly message + ref id, never raw driver/SMTP text.

### The CXO design bar (non-negotiable)
Premium look + premium typography + **no full-page scroll** (only the results grid scrolls; verify at 1366×768) + self-explanatory labels + first-run lands on *ask a question* + executive hierarchy (summary → KPIs → drivers → detail grid) + clarity over novelty + beta-practical. The Ask input sits at ~eye level.

### THE TASK this session (design first, then build — review gate before coding)

**1. SQL-aware intelligent derivation (deterministic; no rows to the LLM).**
The richest signals are already on screen and unused: the **proposed SQL** and the **NL question**. Use them to drive the rendering instead of guessing from column names:
- Parse the SQL SELECT/GROUP BY: **`GROUP BY` columns → dimensions**; **aggregate functions (`SUM`/`AVG`/`COUNT`/`MIN`/`MAX`) → measures + their exact aggregation**. This overrides the name heuristics in `columns.ts`/`kpis.ts` (e.g., KPI sum-vs-avg comes from the SQL, not `AVG_HINT`).
- Use `GROUP BY` to pick chart + drill dimensions precisely; use the question for labels/intent.
- Keep the current **name+value heuristics as the FALLBACK** when SQL is ambiguous (`SELECT *`, expressions, sub-selects).
- *(Optional, opt-in)* an LLM pass over **schema/column names ONLY** to annotate units / measure-vs-dimension / good drill paths for cryptic EBS names (`SEGMENT1`, `ATTRIBUTE5`, `DR_AMT`). Never send rows; reuse the existing LLM config. Gate it; deterministic path must work without it.

**2. Edge cases (the explicit ask — "no data" and "over data"):**
- **Empty result (0 rows):** calm "No rows matched" state + the SQL disclosure + a "refine the question" affordance; KPIs/chart hide; derivation must not throw on empty.
- **Single value (1×1):** promote to a hero figure in the summary band.
- **Single-row / no-dimension:** KPIs only, chart hides gracefully (already partial).
- **Over-data / large results:** honor `/execute` truncation (the `truncated` chip exists); the grid is virtualized; ensure aggregation/classification stay fast at tens of thousands of rows (sampling is capped at 60 for typing — make aggregation O(n) and cap chart cardinality with "+N more"); guard pathological column counts. Export/email already cap at 100k rows.
- **Nulls / mixed types / all-null columns:** skip nulls in aggregation; `formatCell` → "—"; don't misclassify.
- **Errors:** nl2sql / execute / connection / email / export failures all surface a friendly message + `error_id`, never raw.

**3. B5b live wiring (turns the sample into real queries):**
- **Connection picker** in the top bar: `GET /profiles` → choose an active `profile_id` (React context) → pass to `/execute`. Handle zero-profiles with a clear path (Streamlit still does admin during beta).
- **Ask flow:** question → `POST /nl2sql` (needs schema context — a saved schema via `GET /schemas`, or EBS modules) → show the proposed SQL (editable) + confidence + explanation → user approves → `POST /execute` → `ResultsView` with the **real** result + SQL + question (feeds the SQL-aware derivation above).
- **Make "Pull <value> data" real:** run a scoped drill query (filtered re-run or a follow-up nl2sql).
- **No-schema / no-connection:** graceful guidance, not a crash.

**4. Frontend tests (start B7):** set up **Vitest + RTL** (not yet installed). Unit-test the derivation + the new SQL parser + every edge case (empty, 1×1, huge, cryptic names, nulls). This is where the intelligence gets pinned down. Keep the backend suite green.

### How to run & verify
- **Backend:** `.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload` (loads `.env`: SMTP is configured for real email; Groq key + `GROQ_MODEL=llama-3.3-70b-versatile`; live Oracle `AOR_LIVE_*`). Vite dev-proxies `/v1` → `:8000`.
- **User-facing dev server:** run `vite --port 5174 --strictPort` from the junction as a **Bash background process** — that one is reachable from the user's own browser. **The preview-MCP-managed server is NOT user-reachable.**
- **For agent screenshots:** start the **`ask-oracle-web-verify`** launch entry (port **5175**, in `C:\Users\ratis\.claude\launch.json`) — separate, leaves 5174 up for the user. Verify at 1366×768. Recharts bars: trigger via `preview_eval` dispatching a `click` on `.recharts-bar-rectangle` (programmatic clicks on SVG paths work via React delegation). Note CSS `uppercase` changes `innerText` — match case-insensitively in checks.
- **Live Oracle:** XE listener `OracleOraDB21Home1TNSListener` + `OracleServiceXE` must be Running; profile "XE (read-only)" carries `current_schema=AOR_DEMO`; a saved/introspected schema may exist (else introspect or upload one).
- **Build check:** `.\node_modules\.bin\vite build` (Rollup handles the spaced path fine; the dev optimizer is the one that needed the workaround).

### Doc governance (at phase close)
ADR-019 (React surface) · ADR-020 (email/export API) · a new ADR for **SQL-aware derivation** · RISK-22 (API egress) · close ITM-025 · update the charter, `docs/CHANGELOG.md`, `docs/issue-log.md` (ITM-026 = dynamic example chips, still open). Independent exit-gate review (reviewer ≠ author).

### First step this session
**Review the current state** (read the charter, the `## [Unreleased]` Phase-9 section of `docs/CHANGELOG.md`, and `web/src/lib/derive/*`), then **propose the SQL-aware-derivation design + an edge-case matrix for owner sign-off BEFORE coding** (the review gate). Then build in small, reviewed, committed increments.

## (end of prompt)
