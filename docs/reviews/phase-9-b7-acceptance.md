# Phase 9 — B7 broader frontend acceptance (self-assessment)

- **Document:** Acceptance pass · **Status:** Complete (author self-assessment) · **Author:** Engineering
- **Date:** 2026-06-15 · **Scope:** the React CXO surface (`web/`) against the existing `/v1` API
- **Branch:** `v2` (local commits only, no push) · **HEAD at assessment:** `8be5283`

> This is the **author's** acceptance pass (broader testing + cross-cutting self-review against the bar).
> It does **not** replace the two remaining sign-offs in the charter §15: the **owner's CXO acceptance
> review** (§15.3) and the **independent exit-gate review** (§15.7, reviewer ≠ author).

## 1. Method
Complete product test (all gates), a test-coverage audit, a cross-cutting review against the CXO design
bar (charter §5b, B-1…B-8) and the carried invariants (§4), and a live walkthrough vs **XE 21c
(AOR_DEMO)** at **1366×768 and 1440×900** through `ask-oracle-web-verify` (port 5175).

## 2. Gates (complete product test)
| Gate | Result |
|------|--------|
| `pytest -q` | **433 passed** |
| `vitest run` | **129 passed** (23 test files) |
| `tsc --noEmit` | clean |
| `vite build` | green |
| OpenAPI | generates — **3.1.0**, 40 paths (`GET /openapi.json`) |

> Counts updated to final totals after the post-B7 NL-guard fixes (BUG-010/011/012); the original B7
> pass at `8be5283` was 428/128. (Exit-gate review F-1.)

Frontend coverage spans the client/Zod (`schemas.test`, `errorMessage.test`), all derivation
(`derive`/`edge`/`cascade`/`sql`/`pullDetail`/`paramLookup`), the results hierarchy
(`ResultsView.cascade/edge/f3`), the Ask flow + pickers, and **all four B6 screens** + dialogs +
`ConfirmDialog`. No acceptance-relevant coverage gap found.

## 3. The CXO design bar (§5b)
| # | Bar | Verdict | Evidence |
|---|-----|---------|----------|
| B-1 | Premium executive look | **PASS — owner-approved (2026-06-15)** | warm-paper canvas + deep-petrol brand + bespoke cards/elevation (tokens.css); screenshots in the packet history. |
| B-2 | Premium typography | **Pass** | Fraunces display + Inter; **tabular numerals** on every figure (`$375.0K`, `250,000`, `125,000` rendered via `.num`). |
| B-3 | No full-page scroll @ 1366×768 (+1440×900) | **Pass** | all 5 routes `scrollHeight == clientHeight` at 1366×768; Ask + Results re-checked at 1440×900; only the detail grid scrolls. |
| B-4 | Self-explanatory labels | **Pass w/ one nit** | "Run query/report", "Default schema", "Default connection", "Test" are plain. **Nit:** the Data Dictionary still says **"Introspect"** — charter B-4 suggests plainer wording (e.g. "Read from the database"). Logged as ITM-034. |
| B-5 | No-brainer first run | **Pass** | app lands on **"What would you like to know?"** (Ask), not admin. |
| B-6 | Executive hierarchy | **Pass** | live report run renders **summary band → KPI cards → driver chart → detail grid**, with the SQL disclosure + CSV/Excel/Email toolbar. |
| B-7 | Clarity over novelty | **PASS — owner-approved (2026-06-15)** | calm, decisive; no experimental UI. |
| B-8 | Beta practicality | **Pass** | runs against the real API; KPI/chart bands hide when not applicable; value-pickers + error copy degrade gracefully. |

## 4. Invariants (§4) — all hold
1. **SELECT/CTE-only chokepoint** — React runs SQL only via `POST /execute` and `POST /reports/{id}/run`
   (incl. parameter value-picker lookups). ✓
2. **AI proposes / user approves** — editable review is the gate; Auto-run (ADR-022, default-off) is the
   only sanctioned skip; the chokepoint still applies. ✓
3. **Schema-names-only to the LLM** — derivation is local/deterministic (`lib/derive/*`); no row data to
   any model. ✓
4. **No client-side DB secrets** — connections referenced by `profile_id`; the create/test password and
   the optional LLM key are sent once / in-memory, never persisted in the browser. ✓
5. **Sanitized errors with `error_id`** — one `friendlyError`/`errorMessage` policy (ADR-024); verified
   live (friendly DB-error copy + reference). ✓

## 5. §15 success criteria
- **#1 cold-run Ask→review→run→executive results→export/email without instruction** — ✓ (live).
- **#2 fits 1366×768, grid the only scroll** — ✓ (verified 1366×768 + 1440×900).
- **#3 premium typography/surfaces; owner acceptance = approved** — ✅ **owner CXO acceptance signed off 2026-06-15.**
- **#4 every invariant holds** — ✓ (§4 above; to be confirmed in the exit-gate).
- **#5 `POST /reports/email` via the same mailer; mocked-SMTP tests; backend green 3.11+3.13** — email
  path unchanged + reused; backend 428 green (CI matrix per ADR-013/016 history).
- **#6 Streamlit still runs unchanged** — admin app untouched this phase.
- **#7 ADRs + docs current; independent exit-gate = PASS** — ADR-019…024 + CHANGELOG/HANDOFF/charter/
  trackers current; **independent exit-gate review still pending** (reviewer ≠ author).

## 6. Open items (non-blocking)
- **ITM-026** — dynamic Ask example chips (needs query-history persistence).
- **ITM-031** — frontend ESLint debt (vendored shadcn-dominated; not a CI gate).
- **ITM-034 (new, S4)** — B-4 label nit: rename "Introspect" to plainer wording in the Data Dictionary.

## 7. Verdict
**Acceptance-ready** against the measurable bar (gates green; B-2/B-3/B-4*/B-5/B-6/B-8 pass; all five
invariants hold). **Owner CXO acceptance: SIGNED OFF 2026-06-15** (B-1/B-7 + overall look-and-feel
approved). Remaining to close Phase 9: the **independent exit-gate review** (reviewer ≠ author, ADR-006),
now in progress → `reviews/phase-9-b6b7-review-r1.md`. *(B-4 has one S4 wording nit, ITM-034.)*
