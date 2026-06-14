# Phase 9 Charter — React CXO Executive UI (v2)

> **Document:** Phase Charter · **Version:** 1.1 · **Status:** 🟢 Approved (owner, 2026-06-14) — Build in progress · **Owner:** Product/Engineering · **Last updated:** 2026-06-14

> **One-line scope:** A bespoke, premium **React** executive surface for the CXO user, built against the existing `/v1` FastAPI — replacing Streamlit *as the executive face* while keeping Streamlit as the internal admin/power-user tool through beta. **No code until this charter is approved.**

---

## 1. Lifecycle stage

**Discovery OPENED 2026-06-14** on the **v2 branch** (`D:\Ratish\Personal\Project\ask-oracle-reports-main v2`, branch `v2`; junction `D:\Ratish\Personal\Project\aor-v2` to dodge the space-in-path issue; **local commits only — no push until the July GitHub-Actions reset**). Phases 1–8 are closed; the read-only reporting core is GA-ready and the Phase-8 email-a-report follow-up exists in the Streamlit app. Phase 9 is a **presentation-layer phase**: it adds *no new data capability* and *must not* weaken any existing invariant — it re-skins and re-sequences the existing flow to a CXO standard, plus closes one backend gap (email is not yet API-exposed).

## 2. Why we're here (the trigger — read first)

The Streamlit UI was redesigned to a no-scroll two-panel layout (**ITM-024**, commit `513aa74`) and then failed a strict CXO acceptance review (closed 2026-06-14): every screen still required vertical page scroll, Streamlit's default theme reads as a generic dev/data tool, there is no premium typography, and there is no summary-first executive hierarchy. **Streamlit's visual ceiling is structurally too low for a CXO-only product.** The decision (owner, 2026-06-14) is to build the executive-facing surface in **React** against the FastAPI, and keep Streamlit as the admin/power-user tool during beta.

This is not a theming exercise. The bar (Section 5b) treats *summary-first hierarchy* and *single-viewport workflow* as **components to build**, not CSS to apply.

## 3. Decisions already made (owner, 2026-06-14)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| **D-0a** | Build vs. reuse the existing scaffold | **Reuse the stack + vendored shadcn primitives; rebuild design cleanly under `web/`** | A Lovable export (`vite_react_shadcn_ts`, 49 shadcn/ui primitives) already sits in `src/` mixed with the Python backend. The *primitives* are accessible unstyled Radix wrappers (not the source of the generic look); the *default tokens + mock components* are, and those we discard. Reusing the primitives costs nothing on the design ceiling and skips re-installing/re-plumbing accessibility. Moving to `web/` ends the React/Python `src/` collision. |
| **D-0b** | Streamlit's fate | **Keep as the admin/power-user tool through beta** | Lets React focus on the executive flow instead of rebuilding admin plumbing (profile CRUD, schema introspection, packs) before any executive value ships. React reaching parity on admin flows is the eventual decommission trigger (tracked, not now). |
| **D-0c** | Stack | **Vite + React + TypeScript · Tailwind + Radix + shadcn/ui · TanStack Query + TanStack Table · Recharts** | Already the recommended stack and already vendored. Maximum control over a bespoke premium look; Table gives the fixed-height virtualized grid that satisfies the single-scroll rule. |

## 4. Non-negotiable invariants (carry from the whole project — must not regress)

1. **SELECT/CTE-only chokepoint** (`src/db.py`, `src/core/sql_safety.py`, `POST /execute`) is sacred. React runs SQL **only** by calling `/execute`; it cannot and must not run SQL any other way.
2. **AI proposes, user approves.** `/nl2sql` returns SQL for review; the human triggers `/execute`. The React review-and-run step is an explicit, deliberate gate — never auto-run a proposed query.
3. **Schema-names-only to the LLM.** No row/cell value is ever sent to an external model. **This is load-bearing for Phase 9:** all KPI/summary/chart derivation in the executive results view is **local, deterministic client-side math** — never an LLM round-trip over the result set.
4. **Secrets via env, server-side only.** The React app never stores or transmits DB passwords client-side; profiles are referenced by id. The SMTP credential never leaves the server.
5. **Sanitized errors with `error_id`.** Surface the reference id and a friendly message, never raw driver/DSN/SMTP text.

## 5. The bar

### 5a. Backend invariants → see Section 4.

### 5b. The CXO design bar (all non-negotiable)

| # | Bar | What "done" means (acceptance) |
|---|-----|--------------------------------|
| B-1 | **Premium executive look** | Bespoke card/surface system, elevation discipline, restrained palette; reads as a CXO instrument, not a SaaS template. |
| B-2 | **Premium typography** | A deliberate type scale (Section 7b); **tabular lining numerals for every financial figure**; a display face with character for headlines/KPIs — no all-default Inter. |
| B-3 | **No full-page scroll** | The core workflow fits one viewport at **1366×768 and up**. The *only* scroll region is the results detail grid (fixed height, virtualized). Verified by `preview_resize` at 1366×768 and 1440×900. |
| B-4 | **Self-explanatory labels** | Every tab/button/field says what happens next. "Introspect" → "Read from database"; "Bind to profile" → "Default connection"; "Execute" → "Run query". No jargon. |
| B-5 | **No-brainer first run** | App lands on **Ask a question**, not admin setup. The next action is always the obvious one. Ask → review → run → refine → save → export/email flows without instruction. |
| B-6 | **Executive hierarchy** | Results render **summary band → KPI cards → driver chart → detail grid (last)**. Real components (Section 8), not styling. |
| B-7 | **Clarity over novelty** | Calm, trustworthy, decisive. Intelligent and modern, never experimental at usability's expense. |
| B-8 | **Beta practicality** | Shippable against the real API; degrades gracefully when a derivation (KPI/chart) isn't applicable. |

## 6. Architecture & repository layout

```
web/                          # NEW — the React executive surface (Vite root)
  index.html
  vite.config.ts              # dev-proxy /v1 (+ root routes) → http://127.0.0.1:8000
  src/
    main.tsx, App.tsx, router.tsx
    app/                      # shell: AppShell, LeftRail, TopBar, providers (QueryClient)
    styles/tokens.css         # the design system (Section 7) — single source of truth
    lib/api/                  # typed /v1 client (Section 9) + Zod response schemas
    lib/derive/               # LOCAL KPI/chart/summary derivation (no LLM) — Section 8
    components/ui/            # shadcn primitives (copied from the old scaffold, re-tokenised)
    components/exec/          # bespoke executive components (KpiCard, SummaryBand, DriverChart, ResultGrid…)
    features/ask/  reports/  dictionary/  connections/  settings/
    test/                     # Vitest + RTL
src/                          # UNCHANGED Python backend (api.py, app.py, core/, db.py…)
```

- The old root-level React files (`src/App.tsx`, `src/main.tsx`, `src/pages/`, `src/components/{QueryInterface,ResultsDisplay,ReportBuilder,DatabaseConnection,SchemaUpload}.tsx`, `index.html`, `vite.config.ts`, `tailwind.config.ts`, `components.json`) are **removed from the repo root** and the reusable `components/ui/*` primitives are relocated under `web/`. (The package manifests move with them.) This is the "rebuild cleanly in `web/`" of D-0a.
- **Dev:** `uvicorn src.api:app --reload` on `:8000` + `vite` on `:5173`; Vite proxies `/v1` and the root API routes to `:8000`. A **web preview entry** is registered in `C:\Users\ratis\.claude\launch.json` alongside the Streamlit one, using the junction path.
- **No API change beyond the new email endpoint (Section 10).** React consumes the `/v1` contracts exactly as they are.

## 7. The design system (the heart of B-1/B-2)

> These tokens live in `web/src/styles/tokens.css` and `tailwind.config.ts` as the single source of truth. Values below are the **proposed defaults**; the display typeface and brand accent are flagged for owner sign-off (Section 12, D-1/D-2).

### 7a. Color — restrained, executive

Calm warm-neutral canvas, near-black ink, **one** confident brand accent, financial semantics reserved strictly for deltas. (Stock shadcn blue is removed.)

| Token | Default | Use |
|-------|---------|-----|
| `--canvas` | `#F7F6F3` (warm paper) | App background |
| `--surface` | `#FFFFFF` | Cards / panels |
| `--surface-sunken` | `#F1EFEA` | Wells, code blocks, table zebra |
| `--ink` | `#16191F` | Primary text / KPI figures |
| `--ink-muted` | `#5A6068` | Secondary text, labels |
| `--ink-faint` | `#8A9099` | Meta, placeholders |
| `--hairline` | `#E5E2DB` | 1px borders, dividers |
| `--brand` | `#0E5C63` *(deep petrol — sign-off D-2)* | Primary actions, active nav, focus ring |
| `--brand-weak` | `#E4EEEE` | Brand-tinted fills, selected rows |
| `--gain` | `#1A7F55` | Positive financial delta **only** |
| `--loss` | `#B42318` | Negative financial delta **only** |
| `--warn` | `#B25E09` | Warnings (truncation, caps) |

Dark mode is **out of scope for beta** (D-4): light-first, ship one impeccable theme rather than two mediocre ones.

### 7b. Typography — the type scale

- **UI/body:** **Inter** (variable, self-hosted) with `font-feature-settings: "tnum" 1, "cv05" 1` so every numeral is tabular and aligned.
- **Display (masthead, section titles, KPI figures):** a higher-character face — **recommend "Fraunces"** (variable optical-size serif, OFL) used *sparingly* for editorial-premium lift; all-sans "Geist" is the conservative alternative (sign-off D-1).

| Role | Size / line | Weight | Face | Notes |
|------|-------------|--------|------|-------|
| Display / page title | 28 / 34 | 600 | Display | One per screen |
| KPI figure | 34 / 38 | 600 | Display | **Tabular**, `tnum` |
| Section title | 18 / 26 | 600 | Inter | |
| Eyebrow / label | 11 / 14 | 600 | Inter | UPPERCASE, `+0.08em` tracking, `--ink-muted` |
| Body | 14 / 22 | 400 | Inter | |
| Table cell | 13 / 20 | 400 | Inter | numerics right-aligned, tabular |
| Caption / meta | 12 / 16 | 400/500 | Inter | `--ink-faint` |

### 7c. Spacing, radius, elevation, motion

- **Spacing:** 4px base; scale `4 · 8 · 12 · 16 · 24 · 32 · 48`. Cards pad `24`. Generous whitespace is part of the premium read.
- **Radius:** `--r-card: 12px`, `--r-control: 8px`, `--r-chip: 999px`. Calm, not pill-heavy.
- **Elevation (2 levels max):** `--e-1: 0 1px 2px rgba(20,25,31,.04), 0 1px 1px rgba(20,25,31,.03)` (resting card); `--e-2: 0 8px 24px -12px rgba(20,25,31,.18)` (popover/menu). Hairline borders do most of the work; shadows are a whisper.
- **Motion:** 120–180ms ease-out for hovers/menus; respect `prefers-reduced-motion`. No decorative animation.

### 7d. Card spec

Base card: `--surface`, `1px solid --hairline`, `--r-card`, padding `24`, optional **eyebrow** (label) → **title** → content. Resting `--e-1`; hover raises only interactive cards. **KPI card variant:** eyebrow label · big tabular figure (`--ink`) · optional delta chip (`--gain`/`--loss` + ▲/▼) · optional inline sparkline. No card invents data it doesn't have (no `Math.random()` execution times — the anti-pattern from the old prototype).

## 8. Executive results-hierarchy spec (B-6 — the core component contract)

Rendered top-to-bottom after `/execute` returns `{columns, rows, elapsed_seconds, row_count, truncated}`. **All derivation is local/deterministic in `lib/derive/` — no row data leaves the browser, no LLM.** The four bands compress to fit one viewport; only band 4 scrolls.

1. **Summary band** — the question as the headline (the user's NL text, or the report name) + a deterministic meta line: `row_count` rows · `columns.length` columns · `elapsed_seconds` · a `--warn` "Showing first N (truncated)" chip when `truncated`. A disclosure reveals the **exact SQL that ran** (trust). If the result is a single value (1×1), it is promoted to a hero figure here. No LLM-written prose.
2. **KPI cards (auto-derived)** — `deriveKpis(columns, rows)`: classify each column (numeric / date / categorical / id) by sampling values; for the top numeric "measure" columns compute `sum, avg, min, max` and pick the most meaningful (prefer `sum` for additive measures, `avg` for rates) into **3–4 KPI cards** with tabular figures. Currency/percent formatting inferred from column-name hints (`amount`, `total`, `pct`, `rate`). Zero numeric columns → band hides gracefully.
3. **Driver chart (auto-picked)** — `pickChart(columns, rows)`: a **date/time dimension + measure → line/area** (trend); a **categorical dimension + measure → horizontal bar of top-N** (drivers); else hide. Recharts, themed to the tokens, ≤ ~12 series/bars, "+N more" folded. Never forces a chart onto unchartable data.
4. **Detail grid (last, the only scroll)** — TanStack Table, **fixed height, virtualized**, sticky header, numeric columns right-aligned + tabular, inferred types, zebra via `--surface-sunken`. Toolbar: **Export CSV · Export Excel · Send as email** (Section 10). This is the single region permitted to scroll (B-3).

Empty/again states: 0 rows → a calm "No rows matched" with the SQL disclosure and a "Refine the question" affordance, not an error.

## 9. API / data layer

- **TanStack Query** for all reads/mutations; **Zod** schemas mirror the `/v1` contracts and validate at the boundary.
- Typed client wraps `fetch` with: base `/v1`, optional `X-API-Key` (from runtime config, never hard-coded), surfaces `X-Request-ID`/`error_id` from responses into a uniform `ApiError { status, message, errorId }` so the UI can show the friendly message + ref id (invariant 5).
- Confirmed contracts the client targets:
  - `POST /nl2sql` → `{ sql, explanation, confidence: { level, reasons } | null }`
  - `POST /execute` → `{ columns, rows, elapsed_seconds, row_count, truncated }` *(the chokepoint)*
  - `GET/POST/PUT/DELETE /reports`, `POST /reports/{id}/run`, `GET /templates`, `GET /packs(+/{module})`, `GET/POST/DELETE /schemas`, `POST /schemas/introspect`, `GET/POST/DELETE /profiles`, `POST /profiles/{id}/test`, `POST /test-connection`, `GET /health`, `GET /metrics`.
  - `POST /reports/email` → **new** (Section 10).
- The client **never** holds DB passwords; connections are chosen by `profile_id` (invariant 4).

## 10. Backend gap to close — `POST /reports/email`

Email exists only in `src/core/mailer/` (Streamlit-wired). Phase 9 exposes it so the React grid can "Send".

- **Route:** `POST /reports/email` (mounted at root **and** `/v1`, auth-gated like every other route; `email_enabled`/config check → a clear "not configured" rejection when SMTP env is unset).
- **Request:** `{ to, cc?, subject, body, attachment_format: "csv"|"xlsx", columns: string[], rows: any[][], filename? }`. The UI passes back **the exact result already shown** (no re-query, no extra DB hit); the handler reconstructs `df = pd.DataFrame(rows, columns=columns)` and calls **`send_report_email(...)`** unchanged.
- **Invariants on this path (load-bearing):** **no LLM call** — `body` is user-typed (ADR-017/ITM-021); the existing **header-injection guard, allow-list (`EMAIL_ALLOWED_DOMAINS`), size cap, and audit log** in the mailer all apply unchanged; the UI **confirms the recipient** before calling (sends are real).
- **Response mapping** from `SendResult.kind`: `ok` → `200 { status, message, recipients, attachment_bytes }`; `rejected` → `400 { status, message }` (user-actionable, safe verbatim); `error` → `502 { status, message, error_id }` (generic + ref id). `X-Request-ID` echoed as everywhere.
- **Tests (mocked SMTP, no real send in CI):** happy path; not-configured rejection; allow-list rejection; header-injection rejection; oversize rejection; auth required on `/v1` variant; parity with the Streamlit service path. Backend suite must stay green (**401 → grows**).

## 11. Scope

### IN
- `web/` React app: app shell (left rail + top context bar with the active-connection selector), the **Ask → executive Results** flow end-to-end, **Reports** (list/run/save), **export (CSV/Excel) + Send-email**, and a **Data Dictionary** read view (schemas + EBS packs) — all to the design bar.
- The design system (Section 7) as shipped tokens; the four executive results components (Section 8); the typed `/v1` client + Zod schemas (Section 9).
- `POST /reports/email` + tests (Section 10).
- Connections (profiles) and Settings as **light** screens (enough to pick/test a connection and set the API key); deeper admin stays in Streamlit during beta.
- Vitest/RTL tests for the API client and the derivation/results components; a web preview entry; docs in lockstep (ADR-019 React surface + stack; ADR-020 email API endpoint; RISK-22; tracker/CHANGELOG/HANDOFF); independent exit-gate review (reviewer ≠ author).

### OUT
- **No change to the SELECT-only chokepoint, the NL→SQL engine, or the Phase-6.5 security posture.**
- **No new data capability** — Phase 9 is presentation + the one email endpoint.
- **No dark mode** this phase (D-4); **no mobile/responsive-below-1366** beyond graceful degradation.
- **No AI-drafted email body** (would route rows to the LLM — stays OUT, per Phase 8).
- **No multi-tenant auth/SSO**, no in-browser SQL execution of any kind, no client-side DB credentials.
- **Streamlit not deleted or reworked** (D-0b).
- Full admin parity in React (profile/schema/template management depth) — **deferred** to a later increment; Streamlit covers it during beta.

## 12. Decisions for owner sign-off

> **RESOLVED 2026-06-14 (owner):** all five taken **as recommended** — D-1 **Fraunces**, D-2 **deep petrol `#0E5C63`**, D-3 **`POST /reports/email`** (result-passing), D-4 **light-only beta**, D-5 **core-first phasing** (admin stays in Streamlit). Sign-off given against the rendered executive-results mockup.

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| **D-1** | Display typeface | (a) **Fraunces** (variable serif, editorial-premium) · (b) **Geist** (all-sans, conservative) · (c) Inter-only | **(a)** for genuine premium lift; (b) if you prefer all-sans. Body stays Inter regardless. |
| **D-2** | Brand accent hue | (a) **Deep petrol `#0E5C63`** · (b) Deep indigo `#27306B` · (c) Graphite + brass `#B08400` accent | **(a)** — confident, trustworthy, distinctly not stock-SaaS-blue. |
| **D-3** | Email endpoint shape | (a) **`POST /reports/email` taking the shown result (columns+rows)** · (b) `POST /reports/{id}/email` that re-runs server-side | **(a)** — mirrors "attach exactly what's shown," no second DB hit. |
| **D-4** | Theme | (a) **Light-only for beta** · (b) Light + dark | **(a)** — one impeccable theme over two mediocre ones; dark is a fast-follow. |
| **D-5** | Build phasing | (a) **Core flow (Ask→Results) + email first; admin screens light, Streamlit covers depth** · (b) Full parity before ship | **(a)** — ships executive value fastest; matches D-0b. |

## 13. Risks

| ID | Risk | Sev | Mitigation |
|----|------|-----|------------|
| P9-R1 | **Invariant regression via a new surface** — React finds a non-`/execute` path to run SQL, or sends rows to the LLM for "smart" summaries | High | Architectural rule: SQL runs *only* through `/execute`; all derivation is local/deterministic (Section 8); exit-gate review checks both explicitly. |
| **RISK-22** (P9-R2) | **API email egress** — the new `POST /reports/email` is an exfil primitive on a networked deploy | Med-High | Auth-gated; reuses the mailer's allow-list + audit + size cap; opt-in/off when unconfigured; documented in the risk register building on RISK-20. |
| P9-R3 | **Design bar not actually met** — ships "nicer Streamlit," not CXO-grade | High | The bar is encoded as acceptance criteria (5b) verified with `preview_resize`/`preview_screenshot`; owner acceptance review before close, same rigor that failed ITM-024. |
| P9-R4 | **Single-viewport breaks** when KPIs/chart/grid all present at 1366×768 | Med | Fixed-height grid + compressed bands by design; verified at 1366×768 and 1440×900; bands hide gracefully when not derivable. |
| P9-R5 | **Two front-ends drift** (Streamlit vs React behaviour diverges) | Low-Med | Both consume the same API/service functions; email goes through the *same* `send_report_email`; React adds no business logic server-side. |
| P9-R6 | **Scaffold-move breakage** (relocating files into `web/` breaks build/tooling) | Low | Clean move with a green `vite build` + `pytest` checkpoint before feature work; old root React files removed in one reviewed commit. |

## 14. Build plan (B1…Bn — each ends at a green checkpoint, local commit, no push)

1. **B1 — Charter sign-off** (this doc; resolve D-1…D-5).
2. **B2 — Email endpoint + tests** (Section 10); backend suite green.
3. **B3 — `web/` scaffold**: clean Vite+TS+Tailwind+Radix under `web/`, design tokens (Section 7), relocate shadcn primitives, remove old root React files, dev-proxy, preview entry; `vite build` + `pytest` green.
4. **B4 — App shell + typed `/v1` client + Zod schemas** (Sections 6, 9); `/health` wired end-to-end through the proxy.
5. **B5 — Ask → Results (core value):** Query Builder (NL → proposed SQL review/edit → Run) + the four executive results components (Section 8) + export + Send-email. Verified at 1366×768.
6. **B6 — Reports + Data Dictionary** read views; light **Connections + Settings**.
7. **B7 — Frontend tests** (Vitest/RTL: client, KPI/chart derivation, results hierarchy) + **owner acceptance review** against the bar.
8. **B8 — Docs + exit-gate:** ADR-019/020, RISK-22, tracker/CHANGELOG/HANDOFF; independent exit-gate review (reviewer ≠ author).

## 15. Success criteria (phase exit)

1. A CXO can, from a cold first run, land on **Ask**, type a question, review the proposed SQL, run it, and read an **executive results view (summary → KPIs → driver chart → detail grid)** — then export or **email** the result — without instruction.
2. The core workflow **fits 1366×768 with no full-page scroll**; the detail grid is the only scroll region (verified by `preview_resize` + `preview_screenshot`).
3. **Typography and surfaces meet the premium bar** (type scale + tabular numerals + bespoke cards/palette); owner acceptance review = **approved** (the review that ITM-024 failed).
4. **Every invariant holds:** SQL runs only via `/execute`; no row data reaches any LLM; no client-side DB secrets; sanitized errors carry `error_id`. Verified in the exit-gate review.
5. `POST /reports/email` sends through the **same** `send_report_email` with the UI confirming the recipient; mocked-SMTP tests pass; backend suite green on 3.11 + 3.13.
6. **Streamlit still runs** unchanged as the admin/power-user tool.
7. ADR-019/020 + RISK-22 + governed docs current; **independent exit-gate review = PASS** (reviewer ≠ author).

## 16. Doc-governance IDs introduced by this phase

- **ADR-019** — React executive surface & front-end stack (Vite/React/TS/Tailwind/Radix/shadcn/TanStack/Recharts; reuse-and-rebuild-in-`web/`; light-only beta).
- **ADR-020** — Email exposed via `POST /reports/email` (result-passing shape; no-LLM; reuse `send_report_email`).
- **RISK-22** — API email egress (registered, building on RISK-20/21).
- **ITM-025** — Backend gap: email not API-exposed (closed by B2).

## 17. Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-14 | Product/Eng | Discovery charter opened (v2 / Phase 9) — React CXO executive UI vs the `/v1` API. D-0a/b/c resolved by owner (reuse stack + rebuild in `web/`; keep Streamlit; Vite/React/TS/Tailwind/Radix/shadcn/TanStack/Recharts). Design system, executive results-hierarchy spec, email-endpoint spec, scope, risks, and build plan defined. **D-1…D-5 pending owner sign-off. No code until approved.** |
| 1.1 | 2026-06-14 | Product/Eng | **Approved by owner** against a rendered executive-results mockup; D-1…D-5 resolved as recommended (Fraunces · deep petrol · `POST /reports/email` · light-only beta · core-first). **B2 delivered:** `POST /reports/email` (root + `/v1`) reusing `send_report_email` — opt-in 503, SendResult→HTTP mapping, allow-list/newline/bad-format → 400, transport failure → 502 + mailer `error_id`; `tests/test_email_api.py` (12 tests); suite **401 → 413 green**. Build continues at B3 (`web/` scaffold). |
