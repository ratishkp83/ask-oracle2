# Resume Prompt — Phase 9: React CXO-grade executive UI

> Paste the block below into a new Claude Code session to resume. It is self-contained.
> Saved 2026-06-14 after the no-scroll Streamlit redesign (ITM-024, commit `513aa74`) was
> judged **Not approved** against the CXO design bar: Streamlit's default theme cannot deliver
> premium executive typography/visual identity, and there is no summary-first hierarchy. Decision:
> build a bespoke **React** front-end for the executive surface against the existing `/v1` FastAPI.

---

## RESUME PROMPT (copy from here)

Resume **Ask Oracle Reports v2 — Phase 9: React CXO executive UI**.

### Workspace & state
- Repo: `D:\Ratish\Personal\Project\ask-oracle-reports-main v2` (note the space in the path).
- Branch `v2`, HEAD `513aa74`. **LOCAL COMMITS ONLY — do NOT push until the July GitHub-Actions
  limit reset.** Commit at green checkpoints; flag (don't gate) irreversible ops.
- Python backend test gate: `.venv\Scripts\python.exe -m pytest -q` (currently **401 passing**).
- Junction `D:\Ratish\Personal\Project\aor-v2` → this repo exists to dodge the space-in-path issue
  for tools that choke on it (preview server, cmd.exe). Reuse it.

### Why we're here (read first)
The Streamlit UI was redesigned to a no-scroll two-panel layout (ITM-024). A strict CXO acceptance
review **failed** it on the non-negotiables: premium executive look, premium typography, and
summary-first executive hierarchy. Streamlit's default theme reads as a generic dev/data tool and
its visual ceiling is too low for a CXO-only product. **Decision: build the executive-facing surface
in React**, consuming the existing FastAPI. The Streamlit app stays as the internal/admin + power-user
tool during beta (do not delete it). The review and rationale are in `docs/issue-log.md` (ITM-024)
and the conversation that produced this file.

### The backend you're building against (already exists — do NOT rebuild)
FastAPI in `src/api.py`. Every route is mounted **twice**: at root (back-compat) and under `/v1`
(use `/v1`). Auth is opt-in `X-API-Key` via `require_api_key` (enforced app-wide when `APP_API_KEY`
is set; `GET /health` exempt). CORS via `ALLOWED_ORIGINS` env (localhost default; a literal `*`
forfeits credentials). Every response echoes `X-Request-ID`; error bodies carry an `error_id`.

Endpoints (prefix each with `/v1`):
- `GET /health`, `GET /metrics`
- `POST /profiles`, `GET /profiles`, `GET /profiles/{id}`, `DELETE /profiles/{id}`,
  `POST /profiles/{id}/test`
- `POST /test-connection`
- `POST /nl2sql` → `{ sql, explanation, confidence: {level, reasons} }` (AI **proposes** SQL)
- `POST /execute` — **the single SELECT-only chokepoint that runs SQL** (user-approved)
- `POST /reports`, `GET /reports`, `GET /reports/{id}`, `PUT /reports/{id}`,
  `DELETE /reports/{id}`, `POST /reports/{id}/run`
- `GET /templates`, `GET /templates/{id}`
- `GET /packs`, `GET /packs/{module}` (curated EBS metadata packs GL/AP/AR/PO/OM)
- `POST /schemas`, `GET /schemas`, `GET /schemas/{id}`, `DELETE /schemas/{id}`,
  `POST /schemas/introspect`

**Known backend gap:** email (the Phase-8 "email a report" follow-up) lives only in the Streamlit
app's `src/core/mailer/` — it is **NOT exposed via the API**. Add a small endpoint
(`POST /reports/email` or `POST /execute/email`, opt-in via `email_enabled()`, reusing
`send_report_email`) before wiring the React export/share flow. Keep "schema-names-only to the LLM"
intact — email must NOT route row data through any LLM; the body stays user-typed (ADR-017,
ITM-021). Email sends are **REAL** — the UI must confirm the recipient before sending.

### Non-negotiable invariants (carry from the whole project)
1. **SELECT-only chokepoint** (`src/db.py`, `src/core/sql_safety.py`, `POST /execute`) is sacred —
   never weaken or bypass it. React calls `/execute`; it cannot and must not run SQL any other way.
2. **AI proposes, user approves** — NL→SQL returns SQL for review; the human triggers execution.
3. **Schema-names-only to the LLM** — never send row/cell data to an external model.
4. **Secrets via env**, never committed. Passwords encrypted at rest server-side; the React app
   never stores DB passwords client-side.
5. Sanitized errors with `error_id` — surface the ref id, not raw driver/DSN text.

### The design bar (this is the actual job — all are non-negotiable for CXO-only)
1. **Premium executive look** — polished, elegant, CXO-grade; not a generic SaaS template. Custom
   card/surface system, elevation discipline, restrained palette.
2. **Premium typography** — a refined, licensed/credible font (e.g. Inter, or a premium face);
   deliberate heading/label/metric/table/body scale. No defaults.
3. **No full-page scroll** — the primary workflow fits one viewport (target 1366×768 and up). The
   **only** allowed scroll is a single internal region: the results data grid (fixed-height, virtualized).
4. **Self-explanatory labels** — every tab/button/field/filter says exactly what happens next. No
   jargon ("Introspect"→"Read from database", "Bind to profile"→"Default connection", etc.).
5. **No-brainer usability** — first-run lands on the value (ask a question), not admin setup; the
   next action is always obvious; query → results → refine → save → export flows naturally.
6. **Executive hierarchy** — results render **summary first**, then **key metrics (KPIs)**, then
   **drivers/supporting insight**, then **detailed table last**. This needs real components
   (a result summary band + auto-derived KPIs + a chart), not just styling. Build it.
7. **Clarity over novelty** — intelligent and modern, never experimental at usability's expense;
   favor calm, trust, decisiveness.
8. **Beta practicality** — realistic, implementation-friendly, actually shippable.

### Recommended stack (confirm with me, then proceed)
- **Vite + React + TypeScript.**
- **Tailwind CSS + Radix UI primitives + shadcn/ui** (best control over a bespoke premium look),
  or **Mantine** if you want batteries-included. Recommend Tailwind+Radix for design control.
- **TanStack Query** for `/v1` data fetching; **TanStack Table** for the fixed-height virtualized
  results grid (satisfies the single-allowed-scroll rule).
- **Recharts** (or visx) for the executive summary/KPI charts.
- **Inter** (or a premium licensed face) self-hosted; a deliberate type scale + design tokens.
- Place the app under `web/` (or `frontend/`) in the repo; dev-proxy `/v1` → the FastAPI
  (`uvicorn src.api:app --reload`). Register a preview-server entry the way the Streamlit one is
  registered in `C:\Users\ratis\.claude\launch.json` (use the junction path to avoid the space).

### Suggested first-session plan (discovery before build — the user prefers this)
1. **Charter** `docs/charters/phase-9-react-cxo-ui.md`: scope, the design system (tokens, type
   scale, color, spacing, card spec), screen inventory, and the executive-hierarchy spec for the
   results view (summary band + KPI cards + driver chart + detail grid). Get sign-off before coding.
2. **Backend gap:** add the email endpoint + tests (keep the LLM-free email invariant).
3. Scaffold `web/` (Vite+TS+Tailwind+Radix), design tokens, the app shell (premium nav + top bar),
   and a typed `/v1` API client.
4. Build the **Query Builder → Results** flow first (the core value): NL question → proposed SQL
   (review/edit) → Run → **executive results view** (summary → KPIs → chart → grid) → export/email.
5. Then Reports, Templates, Schema/Data-Dictionary, Connections, Settings as supporting screens.
6. Keep the FastAPI test suite green; add frontend tests (Vitest/RTL) for the API client and the
   results-hierarchy components. Commit at green checkpoints (no push).

Start by confirming the stack choice and whether the Streamlit app stays (recommended: keep as the
admin/power-user tool during beta), then write the Phase-9 charter for my review before any code.

## (end of prompt)
