# Phase 9 — B5b-3 (live wiring + Inc 4) Independent Adversarial Review · r1

> **Reviewer:** Independent AI instance (fresh context, reviewer ≠ author) ·
> **Date:** 2026-06-14 · **Scope:** `04cf442..HEAD` (HEAD `a8f21ca`, branch `v2`) ·
> **Gate:** ADR-006 exit-gate review.

---

## 1. Verdict

**`PASS`** — no blocking findings. All five non-negotiable invariants hold under
adversarial inspection. The BUG-008 fix is correct and injection-safe, the
pull-detail wrap is a plain bound `SELECT` that re-enters the SELECT-only
chokepoint, and the Auto-run toggle is default-off, persisted, and read-only-safe.
Six observations are recorded below: all **S3/S4** (one tooling/repro wrinkle that
does not affect the product, the rest pre-logged deferrals or trivia). None gates
closure.

---

## 2. Scope reviewed

`git diff 04cf442..HEAD` — 29 files, +2037/−39. The substantive surface:

- **Frontend** (`web/src/`): `app/session.tsx` (SessionProvider incl. `autoRun`),
  `app/ConnectionPicker.tsx`, `app/TopBar.tsx`, `app/providers.tsx`,
  `features/ask/SchemaPicker.tsx`, `features/ask/AskPage.tsx` (state machine +
  auto-run + pull-detail + edit-sql entry points), `features/ask/ProposedSql.tsx`
  (editable review gate), `components/exec/ResultsView.tsx` (cascade + F3 +
  Edit-SQL), `lib/derive/pullDetail.ts` (Decision-3 wrap),
  `lib/api/{endpoints,schemas,config,client}.ts`.
- **Backend** (`src/api.py`): the BUG-008 fix in `_resolve_target` + `test_profile`.
- **Docs**: `docs/adr/ADR-019..022` (+ `adr/README.md`), CHANGELOG, issue-log,
  risk-register, phase-9 charter.
- **Tests**: `tests/test_execute_endpoint.py` (BUG-008 regression),
  `web/src/**/*.test.{ts,tsx}` (cascade, pull wrap, pickers, Ask state machine,
  auto-run, F3).

---

## 3. Gates — re-run independently by the reviewer

| Gate | Command (as run) | Result observed |
|------|------------------|-----------------|
| Backend tests | `.\.venv\Scripts\python.exe -m pytest -q` | **427 passed**, 1 warning, exit 0 (10.77s) |
| Frontend tests | `vitest run` (see note) | **69 passed** / 11 files, exit 0 (11.27s) |
| Type-check | `.\node_modules\.bin\tsc --noEmit -p tsconfig.json` | **clean**, exit 0 |
| Build | `.\node_modules\.bin\vite build` | **green** ("✓ built in 7.08s"), exit 0 (chunk-size advisory only) |

All four gate numbers match the author's claims (427 / 69 / clean / green).

**Reproduction note (P9B-R1-F1, S3 — tooling, not product):** the prompt's
prescribed frontend command `.\node_modules\.bin\vitest run` executed **from the
junction** `D:\...\aor-v2` did **not** reproduce the 69 — it reported `no tests`
(exit 1), and an explicit `--config` run failed earlier with
`Failed to load url …/web/src/test/setup.ts (resolved id: …/ask-oracle-reports-main v2/web/src/test/setup.ts)`.
Root cause: Vite canonicalizes the junction to its real target
(`…\ask-oracle-reports-main v2`, **with a space**) during module load and then
URL-encodes the space as `%20`, breaking the setup-file fetch. **Running vitest
with the working directory set to the real spaced path** (`Set-Location
'D:\Ratish\Personal\Project\ask-oracle-reports-main v2'; node
.\node_modules\vitest\vitest.mjs run`) produced a clean **69 passed / 11 files**.
So the suite is genuinely green; the prescribed command line is the only thing that
doesn't reproduce it cleanly. Recommendation in §5.

---

## 4. Invariants — adversarial verification

| # | Invariant | Hold? | Evidence |
|---|-----------|-------|----------|
| 1 | SELECT/CTE-only chokepoint is sacred; the React app runs SQL only via `POST /execute`, server re-validates | **HOLD** | `endpoints.ts` exposes exactly one SQL-running call (`execute` → `POST /execute`, line 44). A repo-wide grep for `post(` / `/execute` shows the only other POSTs are `/nl2sql` (no SQL run), `/reports/email`, `/reports/export` (already-fetched rows). `pullDetail.ts:50` produces `SELECT * FROM (<approved>)[WHERE …]` — a plain SELECT; it is routed back through `runData → execute` (`AskPage.tsx:91`). Server-side `_run_sql` calls `assert_safe_select` before any connection (`api.py:576`) and `run_select` re-validates again (`db.py:215`). Nothing in the client bypasses `/execute`. |
| 2 | AI proposes / user approves; editable review is the gate; Auto-run (ADR-022) only skips manual approve when explicitly enabled (default OFF), stays read-only-safe + editable | **HOLD** | `ProposedSql.tsx` is the editable gate; "Run query" is the only path to `/execute` and is disabled until a connection is set. Auto-run: `session.tsx:54` reads `aor.autoRun === "1"` → **default false**; `setAutoRun` persists `"1"`/removes key (`:66`). `AskPage.generate()` only auto-runs when `autoRun && !!profileId` (`:111`), else falls back to the review (E10). Even in auto-run the same `runData → execute` path is used, so the chokepoint still applies; the SQL remains reachable/editable via "Edit SQL" (`editSql`, `ResultsView` HeaderActions). RTL tests cover both auto-run paths + edit-rerun (AskPage.test.tsx). Auto-run cannot run non-SELECT (server rejects) nor bypass the server. |
| 3 | Schema-names-only to the LLM; no row/cell data to any model; all derivation local/deterministic | **HOLD** | `nl2sql()` body is `{natural_language, schema_id?, ebs_modules?}` (`endpoints.ts:27`) — no rows. All derivation modules (`cascade.ts`, `pullDetail.ts`, `kpis`, `chart`, `columns`, `sql`) read only `result.rows` already in the browser + the SQL text; none import the API client or call any model. `pullDetail.ts` builds SQL from column names + drill values locally (no network, no LLM). ADR-021 records this by-construction guarantee. |
| 4 | No client-side DB secrets; connections by `profile_id` only; localStorage stores only ids/prefs | **HOLD** | `session.tsx` persists exactly `aor.profileId`, `aor.schemaId`, `aor.autoRun` (ids/prefs). `ProfilePublicSchema` (schemas.ts) has **no password field**; `getProfiles` returns id/name/host/username/current_schema only. `execute` sends `profile_id`, never a credential. Grep for `password`/`setItem` confirms no secret is written anywhere client-side. |
| 5 | Sanitized errors with `error_id`; friendly message, never raw driver text | **HOLD** | `client.ts` `ApiError` carries `{message, status, errorId}`; `errorId` is `data.error_id ?? X-Request-ID`. `AskPage.toStepError` maps any non-ApiError to a generic "Something went wrong." `ProposedSql.tsx` and the ask form render `error.message` + `Reference: {errorId}`. Server side, `_run_sql` sanitizes DB exceptions to a generic 400 + `error_id` (`api.py`), and `nl2sql` maps provider failures to `GENERIC_NL2SQL_DETAIL` (api.py:519). No raw driver/DSN text reaches the client. |

---

## 5. Findings

| ID | Sev | Category | Location | Finding | Evidence | Suggested fix |
|----|-----|----------|----------|---------|----------|---------------|
| **P9B-R1-F1** | **S3** | Tooling / gate-repro | `vitest.config.ts`, junction `aor-v2` | The prescribed frontend gate `.\node_modules\.bin\vitest run` from the junction does **not** reproduce the 69 — it reports `no tests` (exit 1), and explicit-config runs fail loading `web/src/test/setup.ts` because Vite canonicalizes the junction to the spaced real path and `%20`-encodes the space. Product code is fine; the gate command is brittle. | Reviewer reproductions in §3. Running from the real spaced path → **69 passed**. | Make the gate junction-proof: set `resolve.preserveSymlinks: true` in `vitest.config.ts`/`vite.config.ts`, or use a space-free real path (a junction whose *target* has no space), or pin the documented gate command to `Set-Location '<real spaced path>'; node .\node_modules\vitest\vitest.mjs run`. Document whichever in the charter so the gate is reproducible by the next reviewer. |
| **P9B-R1-F2** | **S4** | Robustness (pre-logged) | `pullDetail.ts:50`, `ResultsView.tsx:82` | The pull-detail wrap references the inline view's output column by the driver-returned name (`quoteIdent`). If the approved SELECT projects a **duplicate** output name or an **unaliased expression**, the outer `"COL" = :p` predicate could be ambiguous/unresolved and the live pull would error. Not a security issue (still a bound SELECT; server rejects anything unsafe; error is sanitized + the SQL stays editable). | `buildPullDetailSql` quotes `f.column` = `result.columns[dimIndex]`; ambiguity only on pathological projections. Drill dims are GROUP-BY/categorical columns, which are normally uniquely named. | Optional: detect duplicate output names in `parseSelectMeta` and suppress the pull affordance (fall back to "Edit SQL"), or alias-wrap. Low priority; document the assumption (already noted in the `buildPullDetailSql` header comment). |
| **P9B-R1-F3** | **S4** | Input validation (deferred) | `schemas.ts:11,30` | `ProfilePublicSchema.environment` (`z.enum`) and `SchemaSummarySchema.source` (`z.enum`) are strict — one unexpected value fails the **whole list parse** and drops the connection picker to the E10 zero-state / schema picker to E11, rather than degrading gracefully. Values come from our own `Literal`s so drift is unlikely. | Already logged as **ITM-027** (and ITM-030 for the schema name-resolution edge), owner-approved deferral. | Wrap the enum (or list parse) in `.catch()` for graceful degradation, per ITM-027. |
| **P9B-R1-F4** | **S4** | Config (deferred) | `config.ts:9` | `ADMIN_URL` defaults to hardcoded `http://localhost:8501` in the bundle (env-overridable via `VITE_AOR_ADMIN_URL`). Beta-only affordance for the E10/E11 "add in admin" links. | Already logged as **ITM-028**, owner-approved deferral. | Source from runtime config or hide the link when unconfigured before GA. |
| **P9B-R1-F5** | **S4** | A11y (deferred) | `ConnectionPicker.tsx`, `SchemaPicker.tsx` | The custom `listbox` dropdowns are keyboard-operable (Tab/Enter/Escape + outside-click) but lack ↑/↓ roving-tabindex navigation within the list. | Already logged as **ITM-029**, owner-approved deferral. Functional for beta. | Add arrow-key roving navigation, or adopt Radix `Select` if jsdom friction is resolved. |
| **P9B-R1-F6** | **S4** | Consistency (trivia) | `AskPage.tsx:55` | `PhaseError` is typed as `(StepError & {phase}) | null` but the alias `type PhaseError` line keeps a stale union shape only used internally; harmless. The `editSql` review sets `confidence: undefined` while the pull-detail sets `confidence: null` — cosmetically inconsistent (both render no chip; `ConfidenceBlock` handles both). | Code read of `AskPage.tsx`. | None required; optionally normalize to `null`. |

No S1 or S2 findings.

---

## 6. BUG-008 — fix correctness & injection analysis

**The bug:** `_resolve_target` (profile branch) and `test_profile` built
`OracleConnectionConfig` **without** `current_schema`, so ADR-018's
`ALTER SESSION SET CURRENT_SCHEMA` never ran on the API path; the AI's unqualified
SQL hit ORA-00942. The field was only honored on the Streamlit path.

**The fix** (`api.py:438`, `api.py:545`): adds
`current_schema=resolved.current_schema` to both `OracleConnectionConfig`
constructions. The inline-connection branch (`api.py:550-562`) is unchanged and
correctly omits it (an inline ad-hoc connection has no saved default schema).

**Injection analysis — does passing `current_schema` open a path?** No.
`db.py:193-200` runs the `ALTER SESSION` only when `current_schema` is truthy, and
**only after** `validate_schema_name` (`db.py:128-133`) gates the value against
`^[A-Za-z][A-Za-z0-9_$#]*$` with a 128-char cap, raising `SqlSafetyError`
otherwise. The schema name is interpolated (it cannot be a bind in `ALTER
SESSION`), but the fail-closed identifier-charset check makes injection
impossible. The value also originates from a saved profile whose
`ProfileCreate.current_schema` is itself length-capped (`profiles.py:42`). This is
a session setting (no data change) run at connect time, outside the SELECT-only
user-query chokepoint. **Correct and safe.**

**Regression coverage:** `tests/test_execute_endpoint.py` adds
`test_execute_via_profile_applies_current_schema` (asserts `AOR_DEMO` reaches the
connection config via a captured `run_select`) and
`test_execute_via_profile_without_schema_passes_none` (asserts `None` when unset).
Both pass within the 427-green suite.

---

## 7. Pull-detail wrap — SQL-injection / read-only analysis

`buildPullDetailSql(approvedSql, filters)` (`pullDetail.ts`):

- **Shape:** `SELECT * FROM (\n<inner>\n)[WHERE …]` where `<inner>` is the approved
  SQL with a trailing `[;\s]+` stripped (`:36`). The result is unambiguously a
  plain `SELECT`; it re-enters `/execute` → `assert_safe_select` → `run_select`
  (double-validated server-side).
- **Identifiers:** column names are wrapped by `quoteIdent`, which escapes embedded
  `"` by doubling (`:18-20`), so a column literally named `WEIRD"COL` becomes
  `"WEIRD""COL"` (unit-tested, `pullDetail.test.ts:50`). No identifier is
  string-concatenated unquoted.
- **Values:** every non-NULL predicate uses a **bind** `:pN` (`:44-46`); the NULL
  bucket renders `IS NULL` with **no bind** (`:41`, tested). Values are never
  interpolated. Server-side `validate_binds` (`db.py:51-75`) re-checks bind names
  against `_BIND_NAME_RE` and values are scalars; binds go to the driver, never the
  SQL string (`db.py:218-230`).
- **Type assumption:** the header comment + ADR-021 document that filters only ever
  carry categorical/numeric drill dims (dates render as non-drillable trend lines),
  so a stringified bind against a NUMBER column relies on Oracle implicit
  conversion — acceptable and documented; a date is never bound as a string. F2
  above notes the duplicate-output-name edge.

**Conclusion:** the wrap cannot run anything but a read-only SELECT and is not
injectable via column names or values.

---

## 8. CXO bar / single-viewport (no full-page scroll)

Verified structurally (no browser needed):

- `AppShell.tsx` — root `h-screen flex flex-col overflow-hidden`; body
  `min-h-0 flex-1`; `<main>` `min-w-0 flex-1 overflow-hidden` (comment: "the frame
  never scrolls; only an inner results region may").
- `ResultsView`/`ResultScope` — header/KPIs/chart are `shrink-0`; the detail/grid
  container is the single `min-h-0 flex-1 … overflow-hidden` region wrapping
  `ResultGrid` (which scrolls internally).
- `ProposedSql.tsx` — the editable SQL textarea is the only `min-h-0 flex-1`
  scroll region; header/confidence/binds/error/actions are all `shrink-0`.

The grid (and the review textarea) is the only scroll region; the frame does not
scroll. Design intent holds.

---

## 9. Docs accuracy vs. code

| Doc | Claim | Verified against code |
|-----|-------|----------------------|
| CHANGELOG | "27 new frontend tests → **69 frontend**; backend **427**; tsc clean; vite build green" | ✓ Matches the gate numbers the reviewer observed. |
| CHANGELOG / issue-log | BUG-008 fix passes `current_schema` in both `_resolve_target` + `test_profile`; chokepoint untouched; 2 regression tests | ✓ `api.py:438,545`; `test_execute_endpoint.py` two tests present. |
| ADR-021 | Pull-detail = `SELECT * FROM (<approved>) WHERE <dim> = :v`, binds, IS NULL bucket, re-approval, no new LLM, chokepoint re-validates | ✓ Exactly matches `pullDetail.ts` + `AskPage.enterPullDetail`. |
| ADR-022 | Auto-run persisted, default-OFF; falls back to review with no connection; Edit-SQL; chokepoint never bypassed; reframes Inv 2 | ✓ Matches `session.tsx` + `AskPage` (`auto = autoRun && !!profileId`). |
| RISK-22 | React holds no DB secrets; persists no result data (only profileId/schemaId/autoRun); no row data to any LLM; export/email reuse Phase-8 guards | ✓ Consistent with `session.tsx`, `schemas.ts`, derivation modules. |
| issue-log F3 | date dim trend now gets a Pull-live-detail affordance; leaf context passed at top level; 3 RTL tests | ✓ `ResultsView.tsx:198` (`PullDetailInline` beside `line` charts) + `:129` (top-level leaf); `ResultsView.f3.test.tsx`. |
| Charter v1.2 | B5b done as increments; gate "427/69/tsc/build"; B8 exit-gate pending | ✓ Accurate; this review is that pending exit gate. |

Docs faithfully reflect the code. No discrepancies found.

---

## 10. Could-not-verify

| Item | Reason |
|------|--------|
| Live Oracle (XE) end-to-end of the pull-detail wrap + unqualified-SQL BUG-008 happy-path | No live Oracle instance in this review context. The author records a live XE verification in the issue-log/CHANGELOG; the mocked regression tests + static analysis cover the contract. |
| Visual/browser confirmation of the no-full-page-scroll CXO bar | Assessed structurally from the layout classes (as permitted by the prompt). |

---

## 11. Summary

Phase 9 B5b-3 (live wiring + Increment 4) is clean across all five non-negotiable
invariants. The SELECT-only chokepoint is the single SQL path and is re-validated
server-side; the pull-detail wrap is a bound, identifier-escaped, plain SELECT; the
Auto-run toggle is default-off, persisted, and read-only-safe (the chokepoint, not
the review gate, is the safety control — correctly reframed in ADR-022); no DB
secrets or result data are persisted client-side; and errors are sanitized with an
`error_id`. The BUG-008 fix is correct and cannot inject (gated by
`validate_schema_name`). Gates re-run by the reviewer: **427 backend / 69 frontend
/ tsc clean / vite build green** — all matching the author's claims.

The only non-trivial observation is **P9B-R1-F1 (S3)**: the prescribed frontend
gate command doesn't reproduce cleanly through the junction (a Vite `%20`
space-in-path issue); the suite is genuinely green when run from the real path.
The remaining five findings are S4 — pre-logged owner-approved deferrals
(ITM-027/028/029/030) and trivia.

**Verdict: `PASS`** (no S1/S2; the lone S3 is a tooling/repro note, not a product
defect). Recommend closing Phase 9 B5b-3 and addressing F1's gate-command brittleness
opportunistically so the next reviewer's gate is reproducible.
