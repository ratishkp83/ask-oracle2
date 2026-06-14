# Resume — Phase 9 B5b-3: live wiring + multi-level cascading (the intelligent-reporting north star)

> Paste the **RESUME PROMPT** block into a new Claude Code session. It is self-contained.
> Saved 2026-06-14 after **B5b-1** (SQL-aware deterministic derivation) and **B5b-2**
> (edge-case hardening) were built, reviewed, and committed locally, and an **intelligent
> aggregated demo sample** was added for manual testing. The **MANUAL DEMO** section below
> is for the owner to run and test by hand right now.

---

## MANUAL DEMO — run and test by hand (no database needed)

The demo runs entirely client-side (the "See a sample result" path uses a built-in
aggregated dataset), so you do **not** need Oracle or the backend running.

**1. Start the user-facing dev server** (PowerShell), from the junction:

```powershell
cd D:\Ratish\Personal\Project\aor-v2
.\node_modules\.bin\vite --port 5174 --strictPort
```

**2. Open** http://localhost:5174 in your browser. (The top-bar health badge will say
"offline" because the backend isn't running — that's expected for the sample demo.)

**3. On the Ask page, click "See a sample result →"** (bottom-left link).

**What to look for — the SQL-aware intelligence (this is the win):**
The sample question is *"Outstanding AR by region and customer — FY26"* over an
aggregated query (`GROUP BY region, customer_name`, with `SUM`, `COUNT`, `AVG`).
The KPI cards prove the derivation reads the SQL, not column-name guesses:

| KPI | Shows | Why it's correct |
|-----|-------|------------------|
| **Outstanding** | `$4.88M` · *Total · 10 values* | `SUM(outstanding_amount)` → summed |
| **Invoices** | `79` · *Total · 10 values* | `COUNT(invoice_id)` → rolled up as a grand total count |
| **Avg days overdue** | `26` · *Average across 10 groups* | `AVG(days_overdue)` → **averaged, not summed** (256 would be wrong), and labelled honestly |

- Click **"View SQL"** in the summary band to see the exact query that "ran".
- The **driver chart** rolls *outstanding* up **by region** (4 bars: North America,
  EMEA, APAC, LATAM) even though the grid rows are per-customer — that's the rollup.

**What to look for — cascading drill-down:**
- **Click the "North America" bar.** The whole view *cascades* to North America:
  KPIs re-scope (`$2.70M` / `42` / `29` across 4 groups), the chart becomes a
  **customer breakdown** for that region, and the grid filters to its 4 customers.
  Use **"Back to report"** to return.
- **Click the "LATAM" bar** (smallest). LATAM has a single customer, so you get the
  **"No further breakdown"** state with a **"Pull LATAM data →"** button — the hook
  for fetching live detail (wired for real in B5b-3).

**Edge states to eyeball (optional):** these are unit- + RTL-tested; they appear in
real use once live wiring lands — empty result → a calm "No rows matched" + Refine;
a single 1×1 value → a big hero figure.

**Known limitation the next session fixes:** the cascade is currently **one level
deep** (region → customer breakdown). The end goal is **multi-level cascading**
(region → customer → … → detail), which is the headline task below.

---

## RESUME PROMPT (copy from here)

Resume **Ask Oracle Reports v2 — Phase 9 B5b-3: live Query Builder wiring + multi-level cascading drill-down**. The end goal the owner stated: **fully intelligent reporting + cascading** — the AI reads intent, renders the right executive view deterministically, and the user can cascade from a summary down through every dimension to the underlying detail.

### Workspace & state
- Repo: `D:\Ratish\Personal\Project\ask-oracle-reports-main v2` (note the space). Branch `v2`, **HEAD `fece48d`**.
- Junction `D:\Ratish\Personal\Project\aor-v2` → the repo (use it; the space breaks some tools). Run Vite/npm from the junction.
- **LOCAL COMMITS ONLY — no push** until the July GitHub-Actions reset. Commit at green checkpoints; flag (don't gate) irreversible ops.
- **Gates:** backend `.\.venv\Scripts\python.exe -m pytest -q` (**422 passing**); frontend `.\node_modules\.bin\vitest run` (**31 passing**); `.\node_modules\.bin\vite build` green.
- **Owner workflow (non-negotiable): a REVIEW GATE at every checkpoint** — finish a unit, *review it (correctness + invariants + the CXO design bar, verified in the running app), present findings, and HOLD for sign-off before advancing.* Do not auto-run the plan to completion.

### What's already built this phase (committed locally)
- **B1–B5a** (earlier sessions): charter, `POST /reports/email` + `/reports/export`, the `web/` React app (design system, shell, typed `/v1` client + Zod, TanStack Query), and the executive **Results view** (SummaryBand, KPI cards, Recharts DriverChart, virtualized ResultGrid, CSV/Excel/Email, 1-level drill-down). See `docs/charters/phase-9-react-cxo-ui.md` and `docs/RESUME-phase-9-b5b.md`.
- **B5b-1 — SQL-aware deterministic derivation** (`122a9f2`): `web/src/lib/derive/sql.ts` is a fail-safe, non-validating reader of the proposed SELECT — `GROUP BY` → dimensions; `SUM/AVG/COUNT/MIN/MAX` → measures with their exact aggregation. It overrides the name heuristics in `columns.ts`/`kpis.ts`/`chart.ts` (KPI roll-up + per-bucket chart use the real agg; `aggregate.ts` `foldAgg` is O(n)); name+value heuristics remain the **fallback** (it returns `null`/`reliable:false` on `SELECT *`, CTEs, set ops, window aggregates, or count mismatch and **never throws**). `ResultsView` wires `parseSelectMeta(sql)` into classification. **Sends nothing anywhere — schema/SQL only to local logic, never rows to an LLM.** 19 tests.
- **B5b-2 — edge-case hardening** (`00d71dd`): E1 empty (calm "No rows matched" + SQL disclosure + Refine), E2 single value (1×1 hero), E3 single row, E4 large/50k (O(n), chart capped at 6 + "+N more"), E5 300 cols, E6 nulls/mixed (`formatCell`→"—"; not misclassified), E7 all-null, E8 AVG/MIN/MAX never summed. Vitest+RTL (`vitest.config.ts`, `web/src/test/setup.ts`); suite 19→31.
- **Intelligent demo sample** (`fece48d`): `web/src/features/ask/sampleResult.ts` is now an aggregated multi-dimensional result so "See a sample result" shows the intelligence + cascade live (see the MANUAL DEMO section of this doc).

### Decisions already resolved (owner, this session — do not re-litigate)
1. **Add `schema_id` to `POST /nl2sql`** — small additive backend change: load the saved definition from `_schema_store` → `schema_from_dict` → existing `generate_sql_from_nl`. Invariant-safe (names only). Add a test. (Needed because the demo schema AOR_DEMO is not EBS, so `ebs_modules` alone can't supply context.)
2. **AVG roll-up KPI** — show the average of group values, labelled honestly ("Average across N groups"); no fabricated weighted mean. (Done in B5b-1.)
3. **Live "Pull <value> data" drill** — deterministically wrap the approved SQL: `SELECT * FROM (<approved>) WHERE <dim> = :v` (bind, SELECT-only), show it in the review step for approval, then `/execute`. No fresh LLM call.
4. **LLM column-annotation pass** (names-only, for cryptic EBS columns) — **deferred**; scaffold a gated interface defaulted OFF. Deterministic path must work without it.

### Non-negotiable invariants (carry)
1. **SELECT/CTE-only chokepoint** (`src/db.py`, `src/core/sql_safety.py`, `POST /execute`) is sacred. React runs SQL **only** via `/execute`.
2. **AI proposes, user approves** — `/nl2sql` returns SQL for review; the human triggers `/execute`. Never auto-run.
3. **Schema-names-only to the LLM** — NEVER send row/cell data to any model. All KPI/chart/summary/cascade derivation stays **local/deterministic**.
4. **Secrets via env, server-side** — the React app never holds DB passwords (connections by `profile_id`).
5. **Sanitized errors with `error_id`** — friendly message + ref id, never raw driver/SMTP text.

### The CXO design bar (carry)
Premium look + premium typography + **no full-page scroll** (only the results grid scrolls; verify at 1366×768) + self-explanatory labels + first-run = ask-a-question + executive hierarchy (summary → KPIs → drivers → detail grid) + clarity over novelty.

### THE TASK this session (design first, then build in small reviewed increments)

**A. Multi-level cascading drill-down (the north-star feature).** Today's drill is one level (region → customer breakdown). Make it cascade through **every** dimension to the detail: maintain a **drill stack** (breadcrumb), make the breakdown chart in a drilled scope **clickable** to push the next dimension, re-scope KPIs/chart/grid at each level using the **SQL-aware** dimension order (`GROUP BY` order from `sql.ts`), and provide Back/breadcrumb navigation. At the deepest dimension (or a single record) → the "no further breakdown → **Pull live detail**" path. All re-scoping stays local/deterministic. Design this first (drill-stack model + how dimension order is chosen) and get sign-off before coding.

**B. B5b-3 live wiring (turn the sample into real queries).**
- **Connection picker** in the top bar: `GET /profiles` → active `profile_id` in React context → passed to `/execute`. Graceful zero-profiles state (E10) pointing to Streamlit admin during beta.
- **Ask flow:** question → `POST /nl2sql` (schema context via the new **`schema_id`**, or `ebs_modules`) → show the **editable proposed SQL** + confidence + explanation → user approves → `POST /execute` → `ResultsView` with the **real** result feeding the SQL-aware derivation + cascade. No-schema state (E11). Per-step errors → friendly message + `error_id` (E9), never raw.
- **Backend:** add `schema_id` to `NL2SQLRequest` + handler + one test (Decision 1). Keep the chokepoint and Phase-6.5 posture untouched.
- **Live "Pull <value> data":** the wrap-and-approve drill query (Decision 3).

**C. Frontend tests:** unit-test the drill-stack model + the cascade re-scoping; RTL the live Ask state machine (mock the client). Keep backend 422 green.

### How to run & verify
- **Backend:** `.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload` (loads `.env`: SMTP; Groq key + `GROQ_MODEL=llama-3.3-70b-versatile`; live Oracle `AOR_LIVE_*`). Vite dev-proxies `/v1` → `:8000`.
- **User-facing dev server:** `.\node_modules\.bin\vite --port 5174 --strictPort` from the junction (reachable from the user's browser).
- **Agent screenshots:** the `ask-oracle-web-verify` launch entry (port **5175**, in `C:\Users\ratis\.claude\launch.json`) — separate, leaves 5174 up. Verify at 1366×768. Recharts bars: dispatch a bubbling `click` on `.recharts-bar-rectangle` via `preview_eval` (React delegation). **Note: the preview `screenshot` tool was timing out in the last session even though `preview_eval`/console were healthy — fall back to DOM/computed-style assertions via `preview_eval` for objective proof, and retry the screenshot.**
- **Live Oracle (for B5b-3 end-to-end):** XE listener `OracleOraDB21Home1TNSListener` + `OracleServiceXE` must be Running; profile "XE (read-only)" carries `current_schema=AOR_DEMO`; a saved/introspected schema must exist for `schema_id` (else introspect via Streamlit or upload one).
- **Space-in-path fix** is in `vite.config.ts` (vite ^5.4.20 + `preserveSymlinks` + `process.cwd()` roots) — keep it; run Vite from the junction.

### Doc governance (at phase close)
ADR-019 (React surface) · ADR-020 (email/export API) · a new ADR for **SQL-aware derivation + cascading** · RISK-22 (API egress) · close ITM-025; update the charter, `docs/CHANGELOG.md` (the `## [Unreleased]` Phase-9 section), `docs/issue-log.md` (ITM-026 = dynamic example chips, still open). Independent exit-gate review (reviewer ≠ author).

### First step this session
Review the current state (this doc, the charter, `web/src/lib/derive/*`, `web/src/components/exec/ResultsView.tsx`), then **propose the multi-level-cascading design + the B5b-3 live-wiring plan for owner sign-off BEFORE coding** (the review gate). Then build in small, reviewed, committed increments.

## (end of prompt)
