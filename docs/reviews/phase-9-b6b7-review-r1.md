# Phase 9 — B6 supporting screens + B7 acceptance + post-B7 hardening — independent exit-gate review (r1)

- **Document:** Independent exit-gate review · **Verdict:** **PASS-WITH-FIXES** (no S1/S2 blocking)
- **Reviewer:** Independent (reviewer ≠ author, per ADR-006) · **Date:** 2026-06-15
- **Scope (git range):** `eab9cca..dc9598f` — 16 commits, 50 files (~4,756 insertions)
- **HEAD reviewed:** `dc9598f` · **Branch:** `v2` · **Method:** `docs/process/external-review-gate.md` + `adversarial-reviewer-prompt.md`

> This review re-ran all four gates independently, adversarially probed the five non-negotiable
> invariants (tried to break each), code-reviewed the new backend + frontend, and judged test adequacy
> (not just green). I did **not** write any of this code and did not modify any source/test/doc except
> creating this one file.

---

## 1. Gates — re-run by the reviewer (authoritative observed numbers)

All gates were run from the junction `D:\Ratish\Personal\Project\aor-v2` with the project venv / node tools.

| Gate | Command | Observed | Author's claim | Match |
|------|---------|----------|----------------|-------|
| Backend tests | `.venv\Scripts\python.exe -m pytest -q` | **433 passed, 1 warning** (14.7s) | 433 (prompt) / 428 (acceptance doc) | ✅ matches prompt |
| Frontend tests | `node_modules\.bin\vitest run` | **129 passed, 23 files** (14.8s) | 129 (prompt) / 128 (acceptance doc) | ✅ matches prompt |
| Typecheck | `node_modules\.bin\tsc --noEmit -p tsconfig.json` | **clean (exit 0)** | clean | ✅ |
| Build | `node_modules\.bin\vite build` | **green (exit 0, built in 7.2s)** | green | ✅ |

Notes:
- The one pytest warning is a pre-existing `StarletteDeprecationWarning` (httpx/testclient) — not introduced here.
- `vite build` emits the long-standing "chunk > 500 kB" advisory (single 941 kB JS bundle). Pre-existing, not a gate failure, not new to this range. (Low-value backlog: code-splitting.)
- The venv resolves to the **real spaced path** (`…ask-oracle-reports-main v2\.venv`) via the junction — confirms the workspace is correct. No spaced-path/junction tooling hiccup affected the gates.
- **Doc drift (S4, see F-1):** the acceptance doc (`phase-9-b7-acceptance.md`) and CHANGELOG `[Unreleased]` "Tests" line both record **428 / 128**. Those were written at `8be5283` (B6 close), *before* the four post-B7 nl2sql fix commits added tests. The true HEAD figures are **433 / 129**. Numbers are stale-low (the work grew), not overstated — no integrity concern, but they should be refreshed.

---

## 2. The five non-negotiable invariants — adversarial assessment

| # | Invariant | Verdict | Evidence / what I tried to break |
|---|-----------|---------|----------------------------------|
| 1 | **SELECT-only chokepoint** — SQL runs only via `/execute` and `/reports/{id}/run` | **HOLDS** | Both endpoints funnel through `_run_sql` → `assert_safe_select` (api.py:586-594) before `OracleClient.run_select`. The new run-time **value-picker lookups** execute via `execute({sql, profile_id})` (RunReportDialog.tsx:216) — i.e. the same chokepoint; verified the lookup SQL re-validates (it's a normal `/execute` call). `lookup_sql` is **persisted verbatim and never executed server-side** (only stored; `grep` shows no backend execution path — reports.py:58, test_reports_api.py round-trip only). The off-topic guard returns `sql=""` and the UI calls nothing. No new execution path opened. |
| 2 | **AI proposes / user approves** (Auto-run default-off is the only sanctioned skip; off-topic guard never runs SQL) | **HOLDS** | `autoRun` defaults off (session.tsx:68, persisted as `"1"` only when on). The off-topic branch (AskPage.tsx:127-131) sets a notice and returns **before** `runData`, even under Auto-run — and this is locked by a real test asserting `expect(execute).not.toHaveBeenCalled()` with `autoRun="1"` (AskPage.test.tsx:225-247). Backend `generate_sql_from_nl` returns `answerable=False, sql=""` for every non-usable generation — it cannot propose non-SELECT SQL (a fenced `DELETE` declines; test_nl2sql.py:51-59, 92-98). |
| 3 | **Schema-names-only to the LLM** (derivation local; no row data to any model) | **HOLDS** | Auto value-picker derivation is pure/local (`paramLookup.ts` — regex over the report SQL + the dictionary's FK metadata; no execution, no row data). External nl2sql context still goes through `build_external_context` + `assert_no_values` tripwire (nl2sql.py:147-153), unchanged. The dictionary screens fetch **metadata only** (`/schemas/{id}` PK/FK flags; `/packs` notes/glossary). No row values reach any model. |
| 4 | **No client-side DB secrets** | **HOLDS** | `localStorage` is used for exactly three keys: `aor.profileId`, `aor.schemaId`, `aor.autoRun` (session.tsx:43-45; grep across `web/src` confirms no other writer). The connection **password** lives only in transient form state (`AddConnectionDialog` `f.password`), sent once to `/test-connection`/`/profiles`. The per-session **LLM `api_key`** is held **in memory only** (`setLlmState`, never `writeStored`; session.tsx:69-70, 87-99) and re-rendered from memory only. Connections are referenced by `profile_id`; `ProfilePublicSchema` has no password field. |
| 5 | **Sanitized errors with `error_id`** | **HOLDS** | `_db_error` now returns a friendly support-oriented `detail` + `error_id`, full driver text logged server-side (api.py:136-145). The leak test asserts `dbhost.internal` / `SCOTT` / `ORA-12541` never appear in body **or headers** across `/execute`, `/reports/{id}/run`, `/test-connection`, while the raw string IS in the server log keyed to the same id (test_error_handling.py:65-127). The frontend single policy (`friendlyError`/`errorMessage`) passes safe server messages verbatim + ref, genericizes only network (status 0) and synthetic `Request/Export failed (NNN)` placeholders (client.ts:29-47); locked by `errorMessage.test.ts`. Every new error surface routes through it (verified per-screen). |

**All five invariants hold.** I could not construct a path that violates any of them.

---

## 3. Findings

Severity: S1 critical … S4 trivial. No S1/S2 → not blocking. (S1/S2 would force FAIL.)

| ID | Sev | File:line | Finding | Repro / note |
|----|-----|-----------|---------|--------------|
| F-1 | S4 | `docs/reviews/phase-9-b7-acceptance.md:21-22`, `docs/CHANGELOG.md` ("Tests" line ~61) | **Stale gate numbers.** Both record **pytest 428 / vitest 128**; the true HEAD is **433 / 129**. Written at `8be5283` before the 4 post-B7 nl2sql-fix commits added tests; never refreshed. | Run the gates at HEAD — see §1. Numbers are stale-low, not overstated. |
| F-2 | S4 | `web/src/lib/derive/paramLookup.ts:32` | **Multi-bind `IN (...)` only maps the first bind.** For `WHERE dept_id IN (:a, :b, :c)`, `deriveBindColumns` returns `{a: "DEPT_ID"}` only; `:b`/`:c` get no auto-picker and fall back to typed input. The `right` regex captures a single `BIND` after `in (`. | Verified by isolated execution of the function. **Not a safety issue** — everything still runs through the chokepoint, and ADR-023 explicitly promises graceful degradation to text. But it's an unstated heuristic gap and the test suite never exercises a multi-bind IN-list. Worth either handling or noting in ADR-023's "heuristic by nature" line. |
| F-3 | S4 | `src/api.py:522-526` | **Stale comment + a small "verbatim ValueError" surface.** The comment still cites *"unsafe generation"* as a `ValueError` that surfaces verbatim, but after ADR-025 `generate_sql_from_nl` no longer raises for unsafe SQL (it returns `answerable=False`). Separately, the `except (ValueError, …)` branch passes `str(exc)` through verbatim; if `schema_csv`/`relationships_csv` parsing raises a **pandas `ParserError`/`EmptyDataError`** (both `ValueError` subclasses) the developer-ish pandas message reaches the client. | Pre-existing (not introduced this range); not raw *driver* text and not secret-bearing, so ADR-024's premise mostly holds. Fix-when-it-fits: drop the stale comment; consider wrapping CSV-parse failures in a clean message. The React surface uses `schema_id`, not CSV, so this is an admin/API-only edge. |
| F-4 | S4 | `web/src/features/reports/ReportEditorDialog.tsx:109-119` | **`useEffect([open])` ignores `report`/`seed` prop changes while the dialog is open.** If the same mounted dialog instance is reopened with a *different* `report` without an intervening `open=false`, the form keeps the prior values (exhaustive-deps suppressed). | In current usage the dialog is closed between edits (ReportsPage drives `open`), so this is latent, not live. Low risk; flagged for completeness. |
| F-5 | S4 | `src/nl2sql.py` (guard, by design) | **Off-topic guard depends on model compliance.** A genuinely off-topic question for which the model nonetheless returns a valid `SELECT` (no sentinel) is proposed and, under Auto-run, executed. | This is the documented limitation (ADR-025 "depends on model compliance"; chokepoint is the backstop). Listed as a residual, not a defect — the conservative "prefer SQL if both fence+sentinel" rule correctly errs toward *not* blocking real questions. I confirmed the inverse failure (real question wrongly blocked) cannot happen for a fenced SELECT. |

No correctness/safety bug, injection, SSRF, secret-leak, or race was found in the new code. The `friendlyError` policy does not leak opaque/raw text and does not wrongly genericize a useful safe message (verified against the locked test matrix and by reading the two synthesized-placeholder regexes).

### Adversarial notes that came back CLEAN
- **`paramLookup.ts` parser:** string-literal `:x` inside `'...'` did **not** produce a false predicate mapping; `:a = :b` maps to a non-column (`A`) that won't match an FK → harmless empty lookup; 3-part `schema.table.col` correctly reduces to `COL`; `TRUNC(hire_date) = :hd` yields no mapping (function-wrapped column, falls back to text) — all safe degradations.
- **Off-topic guard `has_fence` logic:** a non-SQL generic ``` ``` ``` fence makes `has_fence=True` and suppresses the refusal, but the extracted fence content then fails `sql_is_safe_select` → declines gracefully. No unsafe slip-through; no technical "not a SELECT" error reaches the user (BUG-012 fix verified in code + tests).
- **`_run_sql` chokepoint:** `max_rows` only ever *narrows* the row cap (api.py:598-599); cannot widen.

---

## 4. Test adequacy (owner explicitly asked to judge the testing, not just green)

**Overall: strong and genuinely behavioral.** Assertions check behavior and contracts, not "renders".

- **Off-topic guard (`tests/test_nl2sql.py`, +5 tests → 13):** excellent adversarial coverage — sentinel decline, **prose** refusal without sentinel, **unfenced** non-SELECT (DML), **fenced** non-SELECT, both-fence-and-sentinel (prefer SQL), empty-schema, provider-failure secret-leak (asserts the key `sk-leak-123` and `RetryError` are absent), and a prompt-content assertion that the system prompt forbids proxies/mentions gender. The frontend mirror (`AskPage.test.tsx:225`) asserts `execute` is **not** called under Auto-run — the load-bearing invariant-2 assertion.
- **Value-pickers (`RunReportDialog.test.tsx`, `paramLookup.test.ts`, `ReportEditorDialog.test.tsx`):** explicit `lookup_sql` → dropdown via `/execute` with `profile_id` and correct bind coercion (number); **FK auto-derivation** end-to-end; FK "Suggest…" fill; persistence of lookup SQL. Backend round-trip (`test_reports_api.py:77`).
- **Error policy (`errorMessage.test.ts`):** locks each policy branch — safe message verbatim + ref, opaque→generic, export-placeholder→generic, network→ref-free, non-ApiError→generic. Backend leak test asserts body **and headers** clean while the server log retains the raw detail.
- **Four screens + ConfirmDialog:** each has list / empty-state / network-error-with-ref / server-error-with-ref / action-success / action-failure cases; connection test+save exercised; introspect blocked-without-connection path; template seeding.

**Gaps worth noting (none blocking):**
- **(matches F-2)** No test exercises a **multi-bind `IN (:a, :b)`** auto-derivation — the parser's first-bind-only behavior is uncovered, so a regression there would pass silently.
- The `friendlyError` "passes a useful 5xx message through" *positive* case (e.g. "The model is temporarily unavailable.") is asserted only indirectly (the test covers the opaque-5xx→generic direction and the 4xx-verbatim direction). A direct "non-opaque 5xx message survives" case would more fully lock ADR-024's explicit rejection of blanket-5xx-genericizing.
- The pandas-CSV `ValueError` surface (F-3) is untested on the verbatim path; minor and admin/API-only.

These are enhancement-grade, not adequacy failures. The suite would catch the regressions that matter for the five invariants.

---

## 5. Doc / ADR accuracy

- **ADR-023 (value-pickers):** matches code — three layers (persisted `lookup_sql` → FK-suggest → SQL-derived auto), precedence explicit→auto→text (RunReportDialog.tsx:162), live via `/execute`, degrades to text. The "heuristic by nature / falls back gracefully" caveat is honest (and is exactly where F-2 lives). Accurate.
- **ADR-024 (user-readable errors):** matches code — friendly `_db_error`, single `friendlyError`/`errorMessage` policy, pass-through-safe + genericize-only-opaque, ref always preserved. The "server sanitizes everything it returns" premise is true for the DB/safety/not-found surfaces; the only crack is the pandas-CSV `ValueError` (F-3), which the ADR doesn't call out. Substantially accurate.
- **ADR-025 (off-topic guard):** matches code precisely — sentinel parsed only when no fence, prefer-SQL-if-both, all non-usable generations resolve to one `answerable=False` notice, logged server-side, never the technical "not a SELECT" error; additive `answerable`/`message` contract (default `True`). Streamlit path updated too (app.py). Accurate.
- **Issue log (BUG-009..012, ITM-034):** each maps to the implemented behavior. BUG-012's "all decline shapes → one graceful notice" is realized at nl2sql.py:184-196 and covered by tests. ITM-034 (the "Introspect" wording nit) is real — the dialog/page still say "Introspect" (IntrospectDialog.tsx, DataDictionaryPage). Accurate (open, S4).
- **CHANGELOG `[Unreleased]`:** content accurate; only the test-count line is stale (F-1).

---

## 6. Verdict

**PASS-WITH-FIXES.** No S1/S2 findings; all four gates pass at the numbers I observed
(**pytest 433 · vitest 129 (23 files) · tsc clean · vite build green**); all five non-negotiable
invariants hold under adversarial probing; the off-topic guard, value-picker parser, and error policy
are sound; tests are behavioral and adequate for the invariants. The five findings are all **S4**
(non-blocking): refresh the stale gate numbers (F-1), note/handle the multi-bind `IN` parser gap
(F-2), tidy the stale comment + consider wrapping CSV-parse `ValueError`s (F-3), and two latent
robustness nits (F-4, F-5). None require gating; they can be closed fix-when-it-fits.

— Independent exit-gate reviewer (reviewer ≠ author, ADR-006), 2026-06-15

## 7. Author remediation (2026-06-15)
All five S4 findings addressed; gates re-run green (**pytest 433 · vitest 130 · tsc clean · vite build**):
- **F-1 — Fixed.** Acceptance-doc gate counts refreshed to the final 433/130 (noting the original B7 pass
  at `8be5283` was 428/128).
- **F-2 — Documented + tested.** `deriveBindColumns` now documents that a multi-value `IN (:a,:b,…)` maps
  only the first bind (the rest safely fall back to a typed input; multi-value IN binds are out of scope,
  cf. ITM-011); locked by a new test in `paramLookup.test.ts`.
- **F-3 — Fixed.** Corrected the stale "unsafe generation" comment in `api.py` (non-SELECT/off-topic now
  returns `answerable=False`, doesn't raise). The residual verbatim `ValueError` is the request's own
  malformed `schema_csv` feedback (no driver text / no secret) — kept as user-actionable input feedback.
- **F-4 — Documented.** Comment added to `ReportEditorDialog`'s open-only effect: the dialog is always
  closed between distinct edits, so report/seed never change while open (latent only).
- **F-5 — Accepted (no change).** The off-topic guard's model-compliance dependency is documented in
  ADR-025; the SELECT-only `/execute` chokepoint is the backstop.

**Outcome: exit-gate r1 PASS-WITH-FIXES → all findings remediated/accepted. With the owner's CXO
acceptance (2026-06-15), all Phase-9 §15 exit criteria are met → PHASE 9 CLOSED.**
