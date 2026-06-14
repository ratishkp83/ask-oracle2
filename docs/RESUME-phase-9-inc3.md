# Resume — Phase 9 B5b-3 Increment 3: live Query Builder wiring (split into packets)

> **✅ COMPLETE (2026-06-14).** Increments 3, 4 (incl. the owner-requested Auto-run toggle + F3),
> and 5 (docs + ADR-019..022 + independent exit-gate review r1 = **PASS**) are all done and committed
> locally (HEAD `adb3cf8`; 427 backend / 69 frontend green). For current state read
> [HANDOFF.md](HANDOFF.md) → the Phase-9 banner. This doc is kept as the build record.

> Paste the **RESUME PROMPT** block into a new Claude Code session. It is self-contained.
> Saved 2026-06-14 after **Increment 1** (multi-level cascading drill-down) and
> **Increment 2** (backend `schema_id` on `POST /nl2sql`) were built, internally
> reviewed, tested, and committed locally. The north star is unchanged: **fully
> intelligent reporting + cascading** — the AI reads intent, renders the right
> executive view deterministically, and the user cascades from summary down to the
> underlying detail.

---

## RESUME PROMPT (copy from here)

Resume **Ask Oracle Reports v2 — Phase 9 B5b-3 Increment 3: live Query Builder wiring**, built as **logical delivery packets**. After **each** packet's code change: run the gates, **perform an internal code review**, present findings, and **HOLD for owner sign-off** before the next packet. Never auto-run the plan to completion.

### Workspace & state
- Repo: `D:\Ratish\Personal\Project\ask-oracle-reports-main v2` (note the space). Branch `v2`, **HEAD `04cf442`**.
- Junction `D:\Ratish\Personal\Project\aor-v2` → the repo (use it; the space breaks some tools). Run Vite/npm/pytest from the junction.
- **LOCAL COMMITS ONLY — no push** until the July GitHub-Actions reset. Commit at green checkpoints; flag (don't gate) irreversible ops.
- **Gates:** backend `.\.venv\Scripts\python.exe -m pytest -q` (**425 passing**); frontend `.\node_modules\.bin\vitest run` (**42 passing**); `.\node_modules\.bin\tsc --noEmit -p tsconfig.json` clean; `.\node_modules\.bin\vite build` green. `vite build` does **not** typecheck — always run `tsc` too.
- **Owner workflow (non-negotiable): a REVIEW GATE at every packet** — finish a packet, run gates, **do an internal code review** (correctness + invariants + the CXO bar, verified in the running app), present findings, and HOLD for sign-off before advancing.

### What's already built & committed this phase (local)
- **B1–B5a, B5b-1, B5b-2** (earlier sessions): the `web/` React executive surface, the four executive Results components, SQL-aware deterministic derivation (`web/src/lib/derive/sql.ts`, `columns.ts`, `kpis.ts`, `chart.ts`, `aggregate.ts`), edge-case hardening, and an intelligent aggregated demo (`web/src/features/ask/sampleResult.ts`).
- **Increment 1 — multi-level cascading drill-down** (`cb6f8ef`, fix `a862588`, review fixes `7f9343e`): new pure drill-stack model `web/src/lib/derive/cascade.ts` (`dimensionOrder` = GROUP BY order with column-order fallback; `filterRows` ANDs the stack; shared `dimKey`/`NULL_KEY`). `pickChart` gained an optional cascade-`order` param (back-compatible) + `chartForDim`, and **skips a dimension that is constant in the drilled scope** so 3+ dim cascades reach real detail. `ResultsView` holds a `DrillLevel[]` stack: every breakdown chart is clickable, KPIs/chart/grid re-scope at each level, a clickable **breadcrumb** walks back up, deepest dim / single record → the **Pull-live-detail leaf**. All local/deterministic; no rows leave the browser. Verified in-browser on the demo (region → customer → single record, breadcrumb jump-back, no full-page scroll at 1366×768).
- **Increment 2 — backend `schema_id`** (`04cf442`): `NL2SQLRequest.schema_id` (optional); the handler loads the saved record (unknown id → clean **404**, raised before the `try`), rebuilds the schema via `schema_from_dict` (**names only — invariant 3 holds**), `schema_csv` still wins; chokepoint + Phase-6.5 posture untouched. `tests/test_nl2sql_schema_id.py` (3). **The client does not send `schema_id` yet** — that wiring is Packet 3b/3c below.

### Decisions already resolved (owner — do not re-litigate)
1. **`schema_id` on `POST /nl2sql`** — done in Inc 2.
2. **AVG roll-up KPI** = honest "Average across N groups" (done, B5b-1).
3. **Live "Pull <value> data"** = deterministically wrap the approved SQL `SELECT * FROM (<approved>) WHERE <dim> = :v [AND …]` (binds, SELECT-only), show it in the review step for re-approval, then `/execute`. No fresh LLM call. (**Increment 4.**)
4. **LLM column-annotation pass** (names-only) — deferred; scaffold a gated interface defaulted OFF. Deterministic path must work without it.
5. **Build order** = Inc 1 → 2 → 3 → 4 → 5 (Inc 1 & 2 done).
6. **Schema picker placement** = **inline in the Ask panel** (small "Schema: AOR_DEMO ▾" above the question box), so the top bar carries only the connection selector. Default to the sole schema when exactly one exists.

### Non-negotiable invariants (carry)
1. **SELECT/CTE-only chokepoint** (`src/db.py`, `src/core/sql_safety.py`, `POST /execute`) is sacred. React runs SQL **only** via `/execute`.
2. **AI proposes, user approves** — `/nl2sql` returns SQL for review; the human triggers `/execute`. The editable review step is the deliberate gate. Never auto-run.
3. **Schema-names-only to the LLM** — NEVER send row/cell data to any model. All KPI/chart/summary/cascade derivation stays **local/deterministic**.
4. **Secrets via env, server-side** — the React app never holds DB passwords (connections by `profile_id`).
5. **Sanitized errors with `error_id`** — friendly message + ref id, never raw driver/SMTP text.

### The CXO design bar (carry)
Premium look + premium typography + **no full-page scroll** (only the results grid scrolls; verify at 1366×768) + self-explanatory labels + first-run = ask-a-question + executive hierarchy (summary → KPIs → drivers → detail grid) + clarity over novelty.

### THE TASK — Increment 3 in delivery packets (build → gates → internal review → HOLD, per packet)

**Packet 3a — Session context + connection picker (TopBar).**
- New `SessionProvider` React context: `{ profileId, setProfileId, schemaId, setSchemaId }`, **persisted to localStorage** so it survives reload. Mount in `web/src/app/providers.tsx`.
- Typed client: `getProfiles()` → `GET /profiles`; Zod schema mirroring `ProfilePublic` (`id, name, host, port, service_name?, sid?, current_schema?, username, environment`). Add to `web/src/lib/api/{endpoints,schemas}.ts`.
- `TopBar` (`web/src/app/TopBar.tsx`): replace the static health pill's dead chevron with a real **connection dropdown** (active profile name + `current_schema`); default to the remembered id, else the first profile. Keep the health badge.
- **E10 zero-profiles**: a calm "No connection — add one in admin" state pointing to Streamlit during beta; downstream Run is disabled.
- Tests (RTL, mock the client): renders the profile list, selecting one updates context + persists; zero-profiles state. Keep the suite green.

**Packet 3b — Schema picker (inline in Ask panel) + client deltas.**
- Typed client: `getSchemas()` → `GET /schemas`; Zod mirroring `SchemaSummary` (`id, name, source, profile_id?, table_count, created_at, updated_at`). Add `schema_id?` to the `nl2sql` body type and `binds?` to the `execute` body type (binds used in Inc 4; server already supports both).
- Inline **schema picker** above the question textarea in the Ask panel: "Schema: <name> ▾" from `GET /schemas`, writing `schemaId` into session context. Default to the sole schema when exactly one exists.
- **E11 no-schema**: non-blocking notice ("No schema selected — accuracy may be lower; add one in admin"); `nl2sql` is still allowed.
- Tests (RTL, mock client): schema list renders + selection persists; default-to-sole-schema; no-schema notice. Green.

**Packet 3c — Ask state machine + editable proposed-SQL review step.**
- Rewrite `web/src/features/ask/AskPage.tsx` into a state machine: `idle → proposing → review → running → results` (+ a per-step error sub-state). Keep **"See a sample result"** (the no-DB demo path) working.
- New `ProposedSql` review component: **editable SQL `<textarea>`** (the approve-before-run gate, invariant 2), a **confidence** chip (level + reasons, collapsible) and the explanation, and **"Run query"** (disabled with no connection → E10 hint).
- Wire it: question → `POST /nl2sql` (with `schema_id` from context, or `ebs_modules`) → review/edit → `POST /execute` (with `profile_id` from context, on the possibly-edited SQL) → `ResultsView` with the **real** result feeding the SQL-aware derivation + cascade.
- **E9 per-step errors** → friendly message + `error_id` (from `ApiError.errorId`), never raw, at both the propose and run steps.
- Tests (RTL, mock client): question→generate→review shows SQL + confidence; edit SQL + Run → `execute` called with the edited SQL + `profile_id` → `ResultsView` renders KPIs; nl2sql error → `error_id` banner; no-connection → Run disabled. Backend stays green.
- **Live end-to-end** against XE: connection "XE (read-only)" + a saved AOR_DEMO schema → ask → review → run → real Results + cascade.

### Then (later increments — keep the review gate)
- **Increment 4 — Live "Pull <value> data"** (Decision 3): build `SELECT * FROM (<approved>) WHERE <dim> = :v [AND …]` over the active drill stack (binds, SELECT-only) → route through the review step for re-approval → `/execute`. Wire `ResultsView`'s `onPullDetail(filters)` (already scaffolded) in live mode; demo mode keeps `onPullQuery`. **Also address deferred finding F3** (below) here. + tests.
- **Increment 5 — Docs + exit-gate**: new ADR for SQL-aware derivation + cascading; ADR-019 (React surface) · ADR-020 (email/export API); RISK-22 (API egress); close ITM-025; update the charter, `docs/CHANGELOG.md` (`## [Unreleased]` Phase-9 section), `docs/issue-log.md` (ITM-026 = dynamic example chips, still open). Independent exit-gate review (reviewer ≠ author).

### Carried review finding to resolve in Increment 4
- **F3 (Low):** a **date-dimension cascade level** renders a non-clickable trend line (Recharts lines have no click handler) and, because the chart is non-null, the "Pull live detail" leaf never appears — so a trailing date dimension has **no path to detail**. Demo is unaffected (no dates). Fix in Inc 4 when Pull-detail is wired + dates are realistic: offer "Pull live detail" on non-drillable line levels too.

### How to run & verify
- **Backend:** `.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload` (loads `.env`: SMTP; Groq key + `GROQ_MODEL=llama-3.3-70b-versatile`; live Oracle `AOR_LIVE_*`). Vite dev-proxies `/v1` → `:8000`.
- **User-facing dev server:** `.\node_modules\.bin\vite --port 5174 --strictPort` from the junction.
- **Agent screenshots:** the `ask-oracle-web-verify` launch entry (port **5175**, in `C:\Users\ratis\.claude\launch.json`) — separate, leaves 5174 up. Verify at 1366×768. Recharts bars: dispatch a bubbling `click` on `.recharts-bar-rectangle` via `preview_eval`. **React state flushes asynchronously — click in one `preview_eval` call and read the result in a *separate* call, or you'll read stale DOM.** The `screenshot` tool worked last session but has been flaky; fall back to `preview_eval` DOM/computed-style assertions for objective proof.
- **Live Oracle (for 3c end-to-end):** XE listener `OracleOraDB21Home1TNSListener` + `OracleServiceXE` must be Running; profile "XE (read-only)" carries `current_schema=AOR_DEMO`; a saved/introspected schema must exist for `schema_id` (introspect via Streamlit or upload one).
- **Space-in-path fix** is in `vite.config.ts` — keep it; run Vite from the junction.

### First step this session
Read this doc, then the Inc-1/Inc-2 code (`web/src/lib/derive/cascade.ts`, `web/src/components/exec/ResultsView.tsx`, the `nl2sql` handler in `src/api.py`, `web/src/lib/api/*`). Then **start Packet 3a**: build it, run the gates, do an internal code review, present findings, and **HOLD for sign-off** before Packet 3b.

## (end of prompt)
