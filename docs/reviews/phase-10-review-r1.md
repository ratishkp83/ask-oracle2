# Phase 10 — Independent Exit-Gate Review (r1)

> **Document:** Exit-gate review · **Phase:** v2 / Phase 10 — Cascading Report Deliverables + Local Insight Narration · **Reviewer:** Independent (≠ author, ADR-006) · **Date:** 2026-06-18 · **Process:** [external-review-gate.md](../process/external-review-gate.md) + [adversarial-reviewer-prompt.md](../process/adversarial-reviewer-prompt.md)

## Scope reviewed
- **Change range:** `7e6e67f..HEAD` (HEAD = `7ded9cc` `docs(phase-10): B6 governed-doc sweep + author acceptance`).
- **Branch:** `v2` (local commits only; no push). **Working tree clean** of source modifications (only pre-existing untracked `.claude/`, `docs/delivery/` — neither in this range; no `*.tsbuildinfo` tracked; `tsc --build` emissions are git-ignored).
- **Commits in range:** `c56847c` charter → `680a7da` design+ADR-026/027 → `e47099f` B3 insight → `8757a39` B4 fan-out+bundle+download → `1a0977a` BUG-013 → `d47c58f` B5a backend → `cc60c27` B5b frontend → `f316b45` Ask-copy polish → `7ded9cc` B6 docs sweep.
- **Files:** 36 changed (+2583 / −13). Core surfaces read in full: `web/src/lib/cascade/{spec,bundle,renderHtml}.ts`, `web/src/lib/derive/insight.ts`, `web/src/lib/derive/pullDetail.ts`, `web/src/components/exec/{CascadeReportDialog,InsightBand,ResultsView}.tsx`, `src/api.py` (email-bundle), `src/core/mailer/{message,sender}.py`, `src/core/reports.py`, all new tests, and the wiring in `AskPage.tsx`/`ReportsPage.tsx`/`endpoints.ts`/`schemas.ts`/`export.ts`.

## Gates — observed vs author's claim (all re-run from the junction)

| Gate | Author claim | Observed | Match |
|------|--------------|----------|-------|
| `tsc --build` (the real gate, BUG-013) | clean (exit 0) | **exit 0** | ✅ |
| `tsc --noEmit -p tsconfig.json` (the bare gate) | no-op (0 files) | **`--listFilesOnly` → 0 files, exit 0** — confirmed no-op | ✅ |
| `vitest run` | 158 passed | **158 passed (28 files)** | ✅ |
| `vite build` | green | **green (exit 0; built in 25s; only the pre-existing >500 kB chunk + stale caniuse-lite warnings, both benign)** | ✅ |
| `pytest -q` | 446 passed | **446 passed, 1 warning (pre-existing starlette/httpx deprecation)** | ✅ |

All gate numbers match the author's acceptance doc exactly. The BUG-013 claim is **independently verified**: `tsconfig.json` is `{ "files": [], "references": [...] }`, so the bare `tsc --noEmit -p tsconfig.json` type-checks **zero** files (`--listFilesOnly` emits nothing); only `tsc --build` compiles the referenced projects. The cascade props on `<ResultScope>` are *required* (`reportSql: string`, `reportTitle: string`, …), so a missing one is now a compile error — and `ResultsView.cascade.test.tsx:77` is a runtime regression net on top (it drives the dialog → Download → asserts an HTML blob, which throws on `undefined.length` if `reportRows` is unwired).

## Per-invariant verdict

| # | Invariant | Verdict | Evidence / what I tried |
|---|-----------|---------|--------------------------|
| 1 | **SELECT/CTE-only chokepoint** | **HOLDS** | The cascade adds no SQL-execution path. Child rows come from `bundle.ts:childRows` → `buildPullDetailSql(approvedSql, filters)` (`pullDetail.ts:34`) = `SELECT * FROM (<approved>) WHERE "COL" = :p0` and run through the **injected `run`**, which in both call sites (`AskPage.tsx`, `ReportsPage.tsx`) is `execute()` → `POST /execute` (`endpoints.ts:127`), i.e. the existing chokepoint that re-validates via `assert_safe_select`. `Report.cascade` is metadata only (names+ints, never executed — `reports.py:77`); `/reports/email-bundle` posts a prebuilt HTML string and runs no SQL (`api.py:820`). Values are **bound, never interpolated** (`pullDetail.ts:46`); the NULL bucket is `IS NULL` with no bind (`pullDetail.ts:41`). Locked by `bundle.test.ts:104-127`. |
| 2 | **AI proposes / user approves** | **HOLDS** | Children are deterministic value-bound derivations of the **approved** parent (the ADR-021 pull-detail transform); no Phase-10 path calls `/nl2sql` or any LLM. `grep` over `web/src/lib/cascade/**` and `insight.ts` finds no `nl2sql`/`llm`/`fetch`/`http` — only the injected chokepoint `run` and the email-bundle POST. Building/saving a report is an explicit user action in `CascadeReportDialog`. |
| 3 | **Schema-names-only to the LLM / no row data to any model** | **HOLDS** | `insight.ts`, `bundle.ts`, and `renderHtml.ts` are 100% local: no network/LLM imports; they read only `cols`, `rows`, `sqlMeta` already in the browser. No aggregate, label, or value leaves for a model. The only egress is (a) the chokepoint `run` (SQL text + binds — no rows), and (b) `/reports/email-bundle` (the HTML the user already holds). Phase 10 adds **zero** LLM calls anywhere. |
| 4 | **No client-side DB secrets** | **HOLDS** | Connections by `profile_id` throughout (`AskPage`/`ReportsPage` `onRunSql` pass `profile_id`). `emailBundle()` posts `{to, subject, body, html, cc, filename}` only (`endpoints.ts:202`); the bundle embeds result data + the SQL disclosure, never credentials. `SMTP_PASSWORD` reaches only `smtplib.login` and is never placed in any `SendResult`/audit/response (`sender.py:9-13`, `:79/:86`). |
| 5 | **Sanitized errors + `error_id`** | **HOLDS** | `email_report_bundle` mirrors `email_report` exactly: ok→200, rejected→400 (safe verbatim), transport→**502 with `error_id`** and a generic message (`api.py:850-864`). `send_html_bundle_email` reuses the Phase-8 `SendResult`→HTTP path (`sender.py:165`), logging full detail server-side under its own `error_id`. Frontend surfaces route through `errorMessage()` (dialog `doEmail`/`doSave`/`build`). Verified the transport-failure test asserts neither `5.7.8` nor `app-pw` leaks (`test_email_bundle_api.py:119-128`). |

## Adversarial probes (executed)

- **HTML bundle injection (P10-R6) — clean.** Enumerated every `${…}` interpolation in `renderHtml.ts`: **every** data/identifier sink is wrapped in `esc()` (5-char entity map incl. `'`/`"`) — table cells `esc(formatCell(...))`, KPI label/value/context, insight text, section path values (`sectionTitle`→`esc(p.value)`), `othersRollup.label`, per-section `error`, chart `aria-label`/eyebrow/labels/values (`esc(spec.measureName/dimensionName)`, `esc(trunc(d.label))`, `esc(formatCompact(...))`), TOC entries, column headers `esc(humanize(c))`, and `meta.{title,question,sql,when}`. The remaining interpolations are numbers, the static `STYLE`, or already-escaped composed fragments. Tried a `</pre></details>` breakout via `meta.sql`: blocked (`<`/`>` → entities). No `<script>`, no `<img>`/`<link>`, no `http(s)://` (asserted by `renderHtml.test.ts:28-31`). **No unescaped sink found.**
- **Fan-out bounds (P10-R1) — bounded in both modes.** Live: `MAX_TOTAL_QUERIES=48` caps `run` calls; on exhaustion `childRows` falls back to local filtering and sets `truncated` (`bundle.ts:114-126`). Local + post-budget recursion: `MAX_SECTIONS=256` hard-caps total sections, checked both at the depth gate (`:146`) and before each child push (`:162`), setting `truncated`. Depth is `slice(0, depth)` with `depth` clamped 1..5 and `childrenPerLevel` clamped 1..50 (`spec.ts:42-43`). A crafted result with thousands of distinct dimension values cannot explode work — it is capped to 256 sections / 48 queries. *(See S4-1: the design's predictive "estimate-then-narrow" became a reactive cap; equivalent safety, doc drift.)*
- **Email-bundle endpoint — faithful Phase-8 reuse.** Opt-in `email_enabled()` → 503; a cheap pre-check at 30 MB → 400; the mailer's own `EMAIL_MAX_ATTACHMENT_MB` byte cap → 400 (authoritative); empty/whitespace `html` → 422 (pydantic field validator); allow-list + CR/LF/control-char header-injection guard reused verbatim via `build_html_message` → `validate_address`/`enforce_allowlist`/`sanitize_subject` (`message.py:160-206`); `/v1` mount auth-gated app-wide (`api.py:77`, mounted twice `:1018-1019`). Tests cover all of these incl. `\nBcc:` injection and `/v1` 401-without-key/200-with-key (`test_email_bundle_api.py`).
- **`Report.cascade` — additive + back-compatible.** `Optional[CascadeSpec] = None` on both `Report` and `ReportCreate`; threaded through `_new_report` and **both** store `update()` paths (Json + InMemory). Validators **clamp** depth(1..5)/children(1..50)/rows(≥1), never reject. Absent → `None` through create and update. Locked by `test_reports_api.py` (round-trip+clamp, null back-compat, update-sets-cascade).
- **camelCase↔snake_case mapping.** `toPersistedSpec`/`fromPersistedSpec` round-trip; `rows_per_child` null↔undefined handled; the Zod `CascadePersistedSchema` mirrors the backend `CascadeSpec`. The dialog persists the **resolved** dimension names so a re-run reproduces the same fan-out. Locked by `bundle.test.ts:37-56`.
- **JSX-wiring class (BUG-013).** Both `<ResultScope>` call sites (`ResultsView.tsx:117`, `:146`) pass all six new props; required-prop types + `tsc --build` + the `ResultsView.cascade.test.tsx` download regression all catch a missing one. Empirically confirmed the bare gate is a no-op and the real gate is clean.

## Test adequacy
Strong and behavioral, not "renders":
- **insight.ts** — emit-vs-suppress at each threshold, AVG-not-summed, date-trend-only, coverage, max-cap, `[]` on degenerate/all-null, no-throw fuzz. Good.
- **bundle.ts** — top-N ranking, "Others" rollup math, depth=1 leaves, child-per-level cap, no-dimension flat root, live binds (never interpolated), `IS NULL` bucket, per-child error isolation. Good. *Gap (S4-2): no explicit test that drives the `MAX_TOTAL_QUERIES`/`MAX_SECTIONS` caps to set `truncated=true`; the bound is exercised only indirectly.*
- **renderHtml.ts** — single-file/script-free/no-external, escaping, source-query disclosure. *Gap (S4-3): the XSS escaping test injects the payload only as a **dimension value**; it does not assert escaping when the payload arrives via `meta.title`/`meta.sql`, KPI text, a malicious **column name** (chart `aria-label`/header), or `othersRollup`/`error`. Those paths **are** escaped in code (verified by inspection), but the test coverage is narrower than the P10-R6 claim.*
- **email-bundle (pytest)** — 503/200/400(bad-recipient, domain, newline, oversize)/422/502+error_id+sanitization/`/v1` auth. Comprehensive.
- **persistence (pytest)** — round-trip, clamp, back-compat, update. Good.

## Findings

| ID | Sev | Category | Location | Description | Recommended fix |
|----|-----|----------|----------|-------------|-----------------|
| P10-R1-F1 | **S4** | Doc drift | `web/src/lib/cascade/bundle.ts:58,113-126,146` vs `docs/cascading-reports-design.md` §3.3 step 1 | Design says "compute a conservative total-query estimate; if it exceeds the hard cap, narrow children/depth and mark truncated." Implementation instead enforces the caps **reactively** (run to budget, then fall back to local + set `truncated`). Functionally equivalent and safe; the doc overstates the algorithm. | Either add a short pre-estimate, or amend §3.3 to describe the reactive cap. No code risk. |
| P10-R1-F2 | **S4** | Test gap | `web/src/lib/cascade/renderHtml.test.ts:37` | The P10-R6 escaping test only covers a dimension-value sink; `meta.title`/`meta.sql`/KPI/`error`/column-name (chart label/header) sinks are not asserted (they are correctly escaped in code). | Add one render test feeding `<script>`/`"`/`&` through `meta.title`, `meta.sql`, and a malicious column name; assert entity-encoding. |
| P10-R1-F3 | **S4** | Test gap | `web/src/lib/cascade/bundle.test.ts` | No test forces `truncated=true` via `MAX_TOTAL_QUERIES`/`MAX_SECTIONS`; the bounds are only exercised indirectly. | Add a wide/deep fixture (or lowered caps) asserting `b.truncated === true` and a bounded section/query count. |
| P10-R1-F4 | **S4** | Minor inconsistency | `bundle.ts:72` vs `insight.ts:35` | `rankGroups` defaults a measure with no `c.agg` to `"sum"`, while `insight.ts:leadAgg` adds an AVG name-hint. A section could be *ranked* by sum but *narrated* as average for the same un-typed measure. Both deterministic; affects only child ordering, not displayed values. | Optionally share a single `leadAgg` helper across both. Non-blocking. |

No S1, S2, or S3 findings. I specifically tried and **failed** to: reach the DB with a non-SELECT through the cascade; interpolate a bind value into child SQL; get an unescaped value into the bundle; leak `SMTP_PASSWORD` or raw transport text through the email-bundle path; bypass the allow-list/opt-in/size-cap; explode the fan-out past the caps; or break back-compat for a report without a `cascade`.

## Could-not-verify
- **Live end-to-end vs XE `AOR_DEMO`** (generate → download → email a real bundle, recipient-confirmed) — out of scope for a static review (no live DB/SMTP in this environment). SMTP is fully mocked in pytest; the live leg is the author's success-criterion #6 and is recorded in the acceptance doc as done on the sample. Recommend the delivery lead confirm the live recipient check before sign-off.

## VERDICT: **PASS-WITH-FIXES**
No open blocking (S1/S2) findings. All five invariants hold; all four gates reproduce the author's claimed numbers (`tsc --build` exit 0 · vitest **158** · vite green · pytest **446**); BUG-013's no-op gate and `tsc --build` fix are independently confirmed. The four findings are all **S4** (two doc/test-gap, one inconsistency) and do **not** block closure under the gate policy — fix or backlog them, then record sign-off.

## Author remediation (2026-06-18)
All four S4 findings addressed; complete product test re-run green (**`tsc --build` 0 · vitest 160 · vite build · pytest 446**):
- **P10-R1-F1 — Fixed (doc).** `docs/cascading-reports-design.md` §3.3 step 1 reworded to describe the **reactive** cap (running `queries`/`sections` counters that stop the walk and mark `truncated`), not a predictive estimate — matching the implementation.
- **P10-R1-F2 — Fixed (test).** Added `renderHtml.test.ts` "HTML-escapes the title, SQL disclosure, and column-name/KPI sinks (P10-R6)": feeds `<script>`/`<b>`/`<i>` through `meta.title`, `meta.sql`, a malicious dimension **column name** (→ table header + chart eyebrow), and the measure name (→ KPI label); asserts no raw markup + the entity-encoded forms.
- **P10-R1-F3 — Fixed (test).** Added `bundle.test.ts` "marks truncated and caps queries when the live fan-out exceeds the budget": an 8×7 fixture at depth-2/top-8 drives past `MAX_TOTAL_QUERIES`; asserts `truncated === true` and `queries ≤ 48`.
- **P10-R1-F4 — Fixed (code).** `bundle.ts` now resolves the ranking aggregation with the **same AVG name-hint** as `insight.ts`/`kpis.ts` (`AVG_HINT`), so a section is ranked by the same aggregation it is narrated by. Existing tests (explicit-`agg` measures) unaffected.

**Outcome: exit-gate r1 PASS-WITH-FIXES → all 4 S4 findings remediated. +2 frontend tests (158 → 160).** Remaining for closure: owner sign-off + the live XE `AOR_DEMO` end-to-end leg the reviewer flagged as could-not-verify (generate → download → email, recipient-confirmed).

## Revision history
| Version | Date | Reviewer | Change |
|---------|------|----------|--------|
| r1 | 2026-06-18 | Independent (≠ author) | First exit-gate review of Phase 10 (`7e6e67f..7ded9cc`). Verdict PASS-WITH-FIXES; 4× S4; all 5 invariants HOLD; gates 0/158/green/446 reproduced. |
| r1+rem | 2026-06-18 | Author | All 4 S4 remediated (F1 design-doc reactive-cap wording; F2 escaping-sink test; F3 truncated-cap test; F4 rankGroups AVG-hint alignment). Gates 0/**160**/green/446. |
