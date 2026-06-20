# Resume — Phase 9 B6: supporting screens (Reports · Data Dictionary · Connections · Settings)

> Paste the **RESUME PROMPT** block below into a new Claude Code session. It is self-contained.
> Saved 2026-06-14 after **B5b-3 (live Query Builder + intelligent cascading) closed** — Increments
> 1–5 done, independent exit-gate review **r1 = PASS**, and all six review findings remediated. The
> core ask→propose→review→run→cascade→pull loop is built, tested, and live-verified against XE. What's
> left for a complete product is the four **supporting screens**, which are still placeholders.

---

## RESUME PROMPT (copy from here)

Resume **Ask Oracle Reports v2 — Phase 9 B6: build the supporting screens** (Reports, Data Dictionary,
Connections, Settings) in the React CXO surface, built as **logical packets (one screen at a time)**.
After each packet's code change: run the gates, **do an internal code review**, present findings, and
**HOLD for owner sign-off** before the next packet. Never auto-run the plan to completion (review-gate
at every checkpoint).

### Workspace & state
- Repo: `D:\Ratish\Personal\Project\ask-oracle-reports-main v2` (note the space). Branch `v2`,
  **HEAD `eab9cca`**. Use the junction `D:\Ratish\Personal\Project\aor-v2` for all commands (the space
  breaks some tooling). **LOCAL COMMITS ONLY — no push** until the July GitHub-Actions reset.
- **Gates** (run from the junction): backend `.\.venv\Scripts\python.exe -m pytest -q` (**427**);
  frontend `.\node_modules\.bin\vitest run` (**74**); `.\node_modules\.bin\tsc --noEmit -p tsconfig.json`
  clean; `.\node_modules\.bin\vite build` green. `vite build` does **not** typecheck — always run `tsc`.
- **Read first:** `docs/HANDOFF.md` (the 🟢 Phase-9 banner) → `docs/charters/phase-9-react-cxo-ui.md`
  (§5b the CXO bar, §8 the results-hierarchy spec, §14 build plan B6/B7). The whole B5b history is in
  `docs/RESUME-phase-9-inc3.md` (marked COMPLETE) + `docs/CHANGELOG.md` (Phase-9 section) +
  `docs/reviews/phase-9-b5b-review-r1.md` (exit-gate PASS).

### What's already built (the executive core — done & committed)
- `web/` React surface against `/v1` (ADR-019): app shell (`web/src/app/`), typed `/v1` client + Zod
  (`web/src/lib/api/*`), `SessionProvider` (profile + schema + autoRun, persisted; ids only, never a
  secret), TopBar **ConnectionPicker**, inline **SchemaPicker**, the **Ask** flow
  (`web/src/features/ask/AskPage.tsx` state machine + `ProposedSql` editable review), the executive
  **Results view** with SQL-aware deterministic derivation + multi-level **cascade** + live
  **Pull-detail** wrap + **Auto-run** toggle + F3 trend path-to-detail
  (`web/src/components/exec/*`, `web/src/lib/derive/*`).
- Routing in `web/src/router.tsx`; the four supporting routes (`/reports`, `/dictionary`,
  `/connections`, `/settings`) currently render `web/src/app/PlaceholderPage.tsx`.

### THE NEXT ACTION — B6, one screen per packet (build → gates → internal review → present → HOLD)
Replace the four `PlaceholderPage` routes with real screens, bound to the **existing `/v1` endpoints**
(no new backend needed unless a gap surfaces — flag it, don't silently add). Keep the design system
(`web/src/styles/tokens.css`: warm-paper canvas, deep-petrol `#0E5C63`, Inter + Fraunces) and the CXO
bar. **Recommended order** (closes the two "add one in admin" handoffs first, then value-adds):

1. **Connections** (`/connections`) — *recommended first.* List/add/test/delete saved connections so the
   user never has to bounce to Streamlit. Endpoints: `GET/POST /profiles`, `DELETE /profiles/{id}`,
   `POST /profiles/{id}/test`, `POST /test-connection` (unsaved). Adding a profile needs the password
   field — it is **sent once to create the profile and never stored client-side** (invariant 4; the
   server encrypts it). Include the **Default schema** field (ADR-018 `current_schema`). On success this
   removes the **E10** admin handoff in the TopBar picker.
2. **Data Dictionary** (`/dictionary`) — browse saved schemas + curated **EBS packs**. Endpoints:
   `GET /schemas`, `GET /schemas/{id}` (table/column detail), `DELETE /schemas/{id}`,
   `POST /schemas/introspect` (save a live schema — removes the **E11** admin handoff), `GET /packs`,
   `GET /packs/{module}` (GL/AP/AR/PO/OM). Metadata only — names/counts, never row data.
3. **Reports** (`/reports`) — saved reports: list, run, save-new, edit, delete; reuse the executive
   Results view + export/email. Endpoints: `GET/POST/PUT/DELETE /reports`, `POST /reports/{id}/run`
   (supports `binds` for parameterized reports — ADR-007), `GET /templates`, `GET /templates/{id}`,
   `POST /reports/export`, `POST /reports/email`.
4. **Settings** (`/settings`) — *lightest.* Show active model + email-enabled + safety-limit status; the
   per-request **LLM override** (`LLMSettings` on `/nl2sql`, ADR-004) is per-session. **No `/settings`
   endpoint exists** — this is mostly display + the existing per-request override; flag if the owner
   wants a persisted settings store (a backend gap, not in scope without sign-off).

Each screen: RTL tests (mock the client), keep the suite green, verify in-browser at **1366×768 with no
full-page scroll** (only an inner region may scroll — the Connections/schemas/reports tables are the
scroll regions). After B6: **B7** broader frontend acceptance + the owner's CXO review.

### Non-negotiable invariants (carry — verify each screen holds them)
1. **SELECT/CTE-only chokepoint** is sacred — React runs SQL only via `POST /execute` (and report runs
   via `POST /reports/{id}/run`, which is the same server-side chokepoint).
2. **AI proposes / user approves** — the editable review is the gate; **Auto-run** (ADR-022, default-off)
   is the only sanctioned skip, and the chokepoint still applies. Never bypass the server.
3. **Schema-names-only to the LLM** — never send row/cell data to any model; all derivation stays
   local/deterministic (`web/src/lib/derive/*`).
4. **No client-side DB secrets** — connections by `profile_id`; a password is posted once to create a
   profile and never persisted in the browser.
5. **Sanitized errors with `error_id`** — friendly message + ref id via `ApiError.errorId`, never raw.
**CXO bar:** premium look + premium type + **no full-page scroll** (verify at 1366×768) + self-explanatory
labels + clarity over novelty.

### Open backlog (not blocking B6)
- **ITM-026** — make the Ask example chips dynamic (recent/most-run questions); blocked on query-history
  persistence (not built). **ITM-031** — frontend ESLint debt (vendored shadcn-dominated; not a CI gate;
  consider scoping ESLint to exclude `components/ui` + typing the test mocks/`client.ts`). Both optional.

### How to run & verify
- **Backend:** `.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000` (loads
  `.env`: Groq key + `GROQ_MODEL=llama-3.3-70b-versatile`; live Oracle `AOR_LIVE_*`; SMTP). Vite
  dev-proxies `/v1` → `:8000`. **Port-8000 churn (known nuisance):** a foreign process intermittently
  grabs 8000 → `/v1/*` returns 404 `{"detail":"Not Found"}`. Fix: `Get-NetTCPConnection -LocalPort 8000
  -State Listen | %{ Stop-Process -Id $_.OwningProcess -Force }`, then restart uvicorn (the launch may
  report a spurious exit 127 even while it serves — confirm with a real `GET /v1/health`).
- **User-facing dev server:** `.\node_modules\.bin\vite --port 5174 --strictPort` from the junction.
- **Agent screenshots:** the `ask-oracle-web-verify` launch entry (port **5175**) — separate, leaves
  5174 up. Verify at **1366×768**. The `screenshot` tool has been flaky — prefer `preview_eval`
  DOM/computed-style assertions for objective proof; **React flushes async — click in one `preview_eval`
  call and read in a separate call**.
- **Live Oracle:** XE listener `OracleOraDB21Home1TNSListener` + `OracleServiceXE` must be Running; the
  profile "XE (read-only)" carries `current_schema=AOR_DEMO` (BUG-008 fix means unqualified SQL now
  runs); a saved AOR_DEMO schema exists in the schema store (introspect via the new Data Dictionary screen
  or `POST /schemas/introspect` `{profile_id, owner:"AOR_DEMO", save:true, name:"AOR_DEMO"}`).
- **Space-in-path fix** is in `vite.config.ts` + `vitest.config.ts` (`preserveSymlinks`) — keep it; run
  from the junction.

### First step this session
Read `docs/HANDOFF.md` (Phase-9 banner) + the charter §5b/§8/§14 + `web/src/router.tsx` +
`web/src/app/PlaceholderPage.tsx`, and skim a built screen (`web/src/features/ask/AskPage.tsx` +
`web/src/app/ConnectionPicker.tsx`) for the conventions. Then **start the Connections screen**: build it,
run the gates, do an internal code review, present findings, and **HOLD for sign-off** before the next
screen.

## (end of prompt)
