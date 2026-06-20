# Design — Cascading Report Deliverables + Local Insight Narration (Phase 10, B2)

> **Document:** Technical Design · **Version:** 1.1 · **Status:** 🟢 **Approved by owner (2026-06-15)** — §7 defaults accepted; **B3 (insight engine) next** · **Owner:** Engineering · **Last updated:** 2026-06-15
> **Charter:** [charters/phase-10-cascading-reports.md](charters/phase-10-cascading-reports.md) (🟢 approved; D-A…D-H resolved). **ADRs:** [ADR-026](adr/ADR-026-cascading-report-deliverable.md) (cascading deliverable + client-orchestrated fan-out), [ADR-027](adr/ADR-027-local-insight-narration.md) (local insight narration).

## 1. Goal & guardrails
Deliver a **cascading report** — a styled, single-file **HTML bundle** (parent summary → narrated KPIs → nested per-value child sections) that the user can **download or email** — plus **local, deterministic insight narration** on the live results view and inside the bundle. **No LLM is added on any path; no row data leaves for a model** (invariant 3). Every SQL hop is the existing `/execute` chokepoint; every cascade child is a deterministic derivation of the **approved** parent (invariants 1 & 2).

All new derivation/orchestration is **client-side TypeScript** reusing `web/src/lib/derive/*`. The server only gains an **additive** email-bundle endpoint and an **additive** `cascade` field on the Report model. Nothing else server-side changes.

## 2. Architecture
```
Ask review / saved report  →  approved parent SQL  ──/execute──▶  parent result (columns+rows)
        │
        ▼  client orchestrator  web/src/lib/cascade/bundle.ts   (bounded by the cascade spec, D-E)
   for each top-N value v of dim[0] (ranked by the lead measure):
        child SQL = buildPullDetailSql(approvedSql, [{dim0, v}])      ──/execute──▶  child result
            recurse to dim[1] … until depth reached or no splitting dim
   residual values of dim[0]  →  "Others" rollup (LOCAL aggregate, no query)
        │
        ▼  derive/* per section (kpis, chart, insight.ts)  — all LOCAL, no LLM
   renderBundleHtml(sectionTree)  →  single-file styled HTML
        ├─ download  → client Blob (no server round-trip)
        └─ email     → POST /reports/email-bundle (additive; reuse send_report_email: allow-list + audit + size cap)
```

## 3. Components

### 3.1 Insight engine — `web/src/lib/derive/insight.ts` (B3, ADR-027)
Pure/local/deterministic. Reads only the **already-fetched** result + local column/SQL metadata; **sends nothing anywhere**.
```ts
export type InsightKind = "total" | "top" | "concentration" | "trend" | "spread" | "coverage";
export interface Insight {
  kind: InsightKind;
  text: string;                 // "Engineering leads salary at $375.0K — 47% of the total."
  measure?: string;             // the measure it concerns
  basis: string;                // short, factual explanation of the math (tooltip)
  confidence: "high" | "med";
}
export function deriveInsights(
  cols: ColumnMeta[], rows: unknown[][], sqlMeta: SqlMeta | null, opts?: { max?: number },
): Insight[];   // ranked, capped (default max 4); [] when nothing clears the thresholds
```
Fact templates (each conservative; emitted only when its threshold is met):
- **total** — lead-measure fold over rows using the measure's *exact* aggregation (reuse `foldAgg`; AVG framed honestly as "Average … across N groups", per ADR-021). Always emitted when a measure exists.
- **top** — the top dimension value by the lead measure.
- **concentration** — share of top-1 (and top-3) vs the total; emitted only when share ≥ a threshold (e.g. top-1 ≥ 30%).
- **trend** — only when a **date/time dimension** is present and ordered: first→last % change, emitted only when |Δ| ≥ a threshold; never claims causation.
- **spread** — min/max group of the lead measure; emitted when the ratio is material.
- **coverage** — null/"—" share of a dimension; emitted only when notable (≥ a threshold).
Ranking by salience; thresholds tuned to avoid noise; low-confidence items dropped. **Never throws** (degrades to `[]`). Rendered as an **Insight band** in `ResultsView` (D-H) above the KPI cards, and embedded per section in the bundle.

### 3.2 Cascade spec — `web/src/lib/cascade/spec.ts` + additive `Report.cascade` (B4/B5)
```ts
export interface CascadeSpec {
  dimensionOrder: string[];   // driver-returned output column NAMES, top→down; [] = auto-derive
  depth: number;              // 1..5, default 2
  childrenPerLevel: number;   // top-N by lead measure, default 8; the rest → "Others"
  rowsPerChild?: number;      // per-child detail cap; default = server SafetyLimits default
}
```
- **Auto-derive (D-C default):** when `dimensionOrder` is empty, resolve it from `cascade.dimensionOrder(cols, sqlMeta)` (GROUP-BY order, column-order fallback) mapped to output names. An explicit order overrides.
- **Python mirror (`src/core/reports.py`):** add a `CascadeSpec` pydantic model (depth 1..5; childrenPerLevel 1..50; `dimensionOrder: List[str]`; `rowsPerChild` optional bounded) and `cascade: Optional[CascadeSpec] = None` on **both** `Report` and `ReportCreate`. **Additive & back-compatible** — absent `cascade` = a normal report; on-disk shape grows by one optional key; persisted via the existing `ReportStore` + `atomic_write_json`. The spec is **metadata only** (names + ints); it is never executed and never reaches the chokepoint as SQL.

### 3.3 Fan-out orchestrator — `web/src/lib/cascade/bundle.ts` (B4)
```ts
export interface BundleSection {
  path: { column: string; value: string }[];  // drill path ([] = root)
  columns: string[]; rows: unknown[][];
  kpis: Kpi[]; chart: ChartSpec | null; insights: Insight[];
  othersRollup?: { count: number; measureTotal: number };   // local-only summary, no query
  children: BundleSection[];
  truncated?: boolean; error?: string;                       // sanitized per-section error
}
export async function buildCascadeBundle(
  approvedSql: string,
  parent: { columns: string[]; rows: unknown[][] },
  cols: ColumnMeta[], sqlMeta: SqlMeta | null,
  spec: CascadeSpec,
  run: (sql: string, binds: Record<string, unknown>) => Promise<{ columns: string[]; rows: unknown[][] }>,
  onProgress?: (done: number, total: number) => void,
): Promise<BundleSection>;
```
Algorithm:
1. **Resolve spec** → ordered dimension *names* + depth + caps (D-E). The total-query and total-section
   caps are enforced **reactively** during the walk (a running `queries`/`sections` counter; when a cap is
   reached the walk stops descending and marks `truncated`) — not via a predictive pre-estimate. Equivalent
   safety, simpler and exact (P10-R1-F1 doc-accuracy fix).
2. **Root section** = parent result + `derive/*` (KPIs, chart, insights).
3. For `dim[level]`: bucket parent (or child) rows by `dimKey`, **rank values by the lead measure** (`foldAgg` per bucket), take **top-N** (`childrenPerLevel`). The residual values become a **local "Others" rollup** (count + measure total) — **no query** (deterministic, cheap, honest).
4. For each top-N value: `buildPullDetailSql(approvedSql, pathFilters)` → `run(...)` (the injected `/execute` client) → derive → **recurse** to the next dimension until `depth` is reached or no further splitting dimension exists.
5. **Bounds & safety:** enforce the total-query hard cap; `run` is the chokepoint (each child a re-validated SELECT, binds carry values — never interpolated; `IS NULL` for the NULL bucket, via `buildPullDetailSql`). A failed child becomes a section with a **sanitized `error`** (reuse `errorMessage`), never aborting the whole bundle. `onProgress` drives a visible progress UI.
6. **Never sends rows anywhere**; all derivation is local.

### 3.4 HTML bundle renderer — `web/src/lib/cascade/renderHtml.ts` (B4)
`renderBundleHtml(root: BundleSection, meta: BundleMeta): string` → a complete, **self-contained** `<!doctype html>` document:
- **Inlined CSS** approximating the executive tokens (warm-paper canvas, deep-petrol brand, tabular numerals) using a **system font stack** (no embedded web-font → small, offline-safe); print-friendly.
- **No `<script>`, no external assets.** The driver chart is rendered as **inline SVG** mini-bars/line (deterministic, no JS).
- Structure: title + run meta + generated timestamp → a small **table of contents** → **parent summary** (Insight band + KPI cards + SVG drivers + a capped parent table) → **nested `<section>`** per child (breadcrumb path + mini KPIs + insights + capped table), with the "Others" rollup line where present.
- **Every data value and identifier is HTML-escaped** (P10-R6); tested with adversarial cell values (`<script>`, `"`, `&`, `{{ }}`).

### 3.5 Delivery (B4 download, B5 email)
- **Download** — `new Blob([html], { type: "text/html;charset=utf-8" })` → object-URL download (`<name>-cascading.html`). Pure client; no server. Mirrors the existing client CSV export.
- **Email** — **new** `POST /reports/email-bundle` (+ `/v1`, auth-gated), additive and separate from `EmailReportRequest` (so the Phase-9 email contract is untouched — lower regression risk):
  ```python
  class EmailBundleRequest(BaseModel):
      to: str; subject: str; body: str = ""; cc: str = ""
      html: str                      # the prebuilt bundle (size-capped before send)
      filename: Optional[str] = None # default "<subject>-cascading.html"
  ```
  Handler: opt-in (`email_enabled()` → 503), size-cap the `html` string pre-build (reject oversize 400), then call an **extended** `send_report_email(..., html_document=html, html_filename=...)` which attaches the bundle as an `.html` file (and a short text/html alternative body) — **reusing every existing guard** (address validation, CRLF/header-injection, `EMAIL_ALLOWED_DOMAINS` allow-list, byte size cap, audit log, `SendResult`→HTTP mapping). **No LLM, no re-query** on this path (same data-egress boundary as today's export/email; RISK-20 applies).

### 3.6 "Save as cascading report" + run (B5)
- **Save:** from a result that has a usable cascade, a "Save as cascading report" dialog (name + a read-only preview of the resolved cascade spec — dimension order, depth, top-N) → `POST /reports` with `sql` = the **approved parent** + the `cascade` spec.
- **Run:** on the Reports screen, a cascading report exposes **Generate bundle** → run the parent via `POST /reports/{id}/run` (binds, chokepoint), then `buildCascadeBundle(...)` → download / email. A normal (non-cascade) report is unchanged.

## 4. Invariant mapping (how each is preserved)
| # | Invariant | How |
|---|-----------|-----|
| 1 | SELECT-only chokepoint | Every parent/child query is `/execute` or `/reports/{id}/run`; `buildPullDetailSql` emits a plain `SELECT … WHERE col=:bind`; no new execution path. |
| 2 | AI proposes / user approves | User approves the **parent** (Ask review, or the saved report's stored `sql`); children are deterministic value-bound derivations of it — **no new AI proposal**. |
| 3 | Schema-names-only to the LLM | Insight + all derivation are local; **no LLM call added**; no rows/aggregates leave the browser. |
| 4 | No client-side DB secrets | Connections by `profile_id`; the bundle carries already-seen result data, never credentials. |
| 5 | Sanitized errors + `error_id` | New surfaces route through `friendlyError`/`errorMessage`; the email-bundle endpoint reuses the mailer's `SendResult`→HTTP (`error_id`). |

## 5. Test plan (vitest + pytest; behavioral, not "renders")
- **insight.ts** — each fact type at/under threshold (emit vs suppress); AVG-not-summed; date-trend only with a date dim; null-coverage; ranking + cap; `[]` on degenerate input; **no-throw** fuzz.
- **bundle.ts** — auto vs explicit dimension order; top-N + "Others" rollup math; depth limit; total-query hard cap → `truncated`; per-child error isolated + sanitized; child SQL equals `buildPullDetailSql` output; `run` called with binds (never interpolated); NULL bucket → `IS NULL`.
- **renderHtml.ts** — single-file (no external refs); **HTML-escaping** of adversarial values/identifiers; no `<script>`; sections/TOC present; numbers tabular-formatted.
- **download** — Blob type/name; assembled from the section tree.
- **email-bundle (pytest)** — opt-in 503; size-cap 400; allow-list reject 400; header-injection reject; `SendResult`→HTTP (ok/rejected/error+`error_id`); `/v1` auth gate; SMTP fully mocked.
- **persistence (pytest)** — `Report.cascade` round-trips; absent = back-compat; validation bounds (depth/children); spec never executed.
- **live (manual)** — vs XE `AOR_DEMO`: generate → download → email a real bundle (recipient-confirmed); premium look @1366×768.

## 6. Build packets (each: build → gates → internal review → present → HOLD for sign-off)
- **B3** — `insight.ts` + Insight band in `ResultsView` (standalone intelligence value first).
- **B4** — `spec.ts` + `bundle.ts` fan-out + `renderHtml.ts` + **download**; D-E bounds; live-verified.
- **B5** — `email-bundle` endpoint + mailer HTML extension; **Save as cascading report** (`cascade` field) + run-a-saved-cascading-report; live send.
- **B6** — governed-doc sweep + complete product test + independent exit-gate review (reviewer ≠ author) → remediate → **CLOSE**.

## 7. Open design questions (call out at sign-off; defaults chosen)
- **Charts in the bundle:** inline SVG mini-bars (chosen) vs omit charts (tables+KPIs only). *Default: inline SVG — deterministic, no JS, no dep.*
- **Fonts in the bundle:** system stack (chosen) vs embedded web-font (bloat). *Default: system stack approximating Fraunces/Inter.*
- **"Others" depth:** local rollup line only (chosen) vs a real drilled "Others" section (extra fan-out). *Default: local rollup — honest + cheap.*
- **Email surface:** new `POST /reports/email-bundle` (chosen) vs extend `EmailReportRequest`. *Default: new endpoint — keeps the Phase-9 contract untouched.*

## 8. Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-15 | Engineering | B2 design drafted for Phase 10 (cascading deliverable + local insight). Components: `insight.ts`, `cascade/spec.ts` (+ additive `Report.cascade`), `cascade/bundle.ts` fan-out, `cascade/renderHtml.ts`, client download, `POST /reports/email-bundle` (mailer HTML extension), "Save as cascading report". Invariant mapping + test plan + B3…B6 packets. **Awaiting owner sign-off before any feature code.** |
| 1.1 | 2026-06-15 | Engineering | **Design APPROVED by owner** — §7 defaults accepted (inline-SVG charts, system fonts, local "Others" rollup, new `POST /reports/email-bundle`). ADR-026/027 Accepted. **B3 (insight engine + Insight band) next.** |
