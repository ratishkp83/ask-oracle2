# Phase 10 — author acceptance (self-assessment, B6)

- **Document:** Acceptance pass · **Status:** Complete (author self-assessment) · **Author:** Engineering
- **Date:** 2026-06-15 · **Scope:** Cascading Report Deliverables + Local Insight Narration (B3–B5) + BUG-013
- **Branch:** `v2` (local commits only, no push) · **Charter:** [charters/phase-10-cascading-reports.md](../charters/phase-10-cascading-reports.md)

> This is the **author's** acceptance pass. It does **not** replace the **independent exit-gate review**
> (reviewer ≠ author, ADR-006), which is the remaining step to close Phase 10.

## 1. Complete product test (all gates)
| Gate | Result |
|------|--------|
| `tsc --build` (the real typecheck — BUG-013) | **clean (exit 0)** |
| `vitest run` | **158 passed** |
| `vite build` | green |
| `pytest -q` | **446 passed** |
| OpenAPI | generates — **3.1.0**, 42 paths (incl. `/reports/email-bundle` + `/v1/...`) |

## 2. What shipped (B3–B5)
- **B3 — local insight narration** (ADR-027): `deriveInsights()` (total / top+concentration / date-trend /
  spread / coverage), threshold-gated, deterministic; "What stands out" band above the KPIs, per drill level.
- **B4 — cascade deliverable** (ADR-026): `cascade/{spec,bundle,renderHtml}.ts` — client-orchestrated fan-out
  (top-N + local "Others", bounded depth/queries), each child a `buildPullDetailSql` derivation of the
  **approved** parent via `/execute`; single-file, **script-free, inline-SVG, HTML-escaped** bundle.
- **B5 — delivery + persistence:** additive **`Report.cascade`** + **`POST /reports/email-bundle`** (mailer
  HTML extension, all Phase-8 guards reused); one **"Report" dialog** (Download / Email / Save); **live
  fresh-fetch fan-out** (`onRunSql` in Ask + Reports); a **saved cascading report** re-runs to a fresh bundle.
- **BUG-013:** the `tsc --noEmit -p tsconfig.json` gate was a no-op; adopted **`tsc --build`**, fixed the
  pre-existing `sql.test.ts:98`, git-ignored `*.tsbuildinfo`.

## 3. Invariants (§4) — all hold
1. **SELECT/CTE-only chokepoint** — every parent/child query is `/execute` or `/reports/{id}/run`; child SQL
   is `buildPullDetailSql` (a plain `SELECT … WHERE col=:bind`); `Report.cascade`/`email-bundle` add no SQL
   execution path. ✓
2. **AI proposes / user approves** — the user approves the parent; children are deterministic value-bound
   derivations of it (no new AI proposal); building a report is an explicit user action. ✓
3. **Schema-names-only to the LLM** — insight + fan-out + bundle are local; **no LLM call added** on any
   Phase-10 path; no rows/aggregates leave for a model. ✓
4. **No client-side DB secrets** — connections by `profile_id`; the bundle carries already-seen result data;
   the email path posts the prebuilt HTML, never credentials. ✓
5. **Sanitized errors + `error_id`** — new surfaces route through `friendlyError`/`errorMessage`; the
   email-bundle endpoint reuses the mailer's `SendResult`→HTTP (`error_id`), full detail server-side. ✓

## 4. Charter §5 success criteria
1. Cascading report from a run result **or** a saved report — parent summary + narrated KPIs + nested
   per-value sections, as a styled single-file HTML bundle; **downloadable + emailable** — ✓ (dialog).
2. Dimension order auto-derived (override-able); **bounded** (depth + top-N + "Others" + per-child + total
   caps); every child through the chokepoint as a derivation of the approved parent — ✓.
3. **Local insight narration** on live results + in the bundle, 100% local — ✓.
4. **"Save as cascading report"** persists the spec (additive, back-compatible); re-runs to a fresh bundle — ✓.
5. All five invariants hold; gates green; ADR-026/027 + governed docs current; **independent exit-gate review
   = PASS** — gates/docs ✓; **independent review still pending** (this acceptance ≠ that review).
6. Verified the dialog live on the sample (build → 19.8 KB script-free bundle → download); **no scheduling,
   no LLM-phrased insight, no native PDF/Excel** (all OUT/deferred) — ✓.

## 5. Verdict
**Acceptance-ready** against the measurable bar (all gates green; bundle is single-file/script-free/escaped;
all five invariants hold; success criteria met). Remaining to close Phase 10: the **independent adversarial
exit-gate review** (reviewer ≠ author, ADR-006) → triage/remediate → record sign-off.
