# ADR-019 — Bespoke React CXO executive surface (against the existing /v1 API)

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Product/Engineering (owner — CXO-only product, design non-negotiable)
- **Phase:** v2 / Phase 9

## Context
The product's audience is executives. A strict CXO acceptance review **failed** the Streamlit
front-end even after the no-scroll two-panel redesign ([ITM-024](../issue-log.md)): Streamlit's
default theme reads as a generic dev tool, has no premium typography, and renders results as a raw
grid with **no summary-first executive hierarchy**. The eight non-negotiable design requirements
(premium look + premium type + no full-page scroll + self-explanatory labels + no-brainer first-run
+ executive hierarchy summary→KPIs→drivers→detail + clarity over novelty + beta practicality) could
not be met inside Streamlit's component model. Every `/v1` API needed already existed (NL→SQL,
execute, profiles, schemas, packs), with the one gap closed in [ADR-020](ADR-020-result-export-and-email-api.md).

## Decision
Build a **bespoke React executive front-end** under `web/`, served against the existing `/v1`
FastAPI; keep **Streamlit as the admin/power-user tool** during beta.

- **Stack:** Vite + React + TypeScript; Tailwind with vendored shadcn/Radix primitives in
  `web/src/components/ui`; **TanStack Query** (server state) + **TanStack Table + Virtual** (the
  detail grid is the **only** scroll region); **Recharts** for KPI/driver charts; **Inter** body +
  **Fraunces** display; warm-paper canvas `#F7F6F3` + deep-petrol brand `#0E5C63`; **light-only** beta.
- **Boundary:** a typed `/v1` client with **Zod** schemas validates every response shape; a dev proxy
  maps `/v1 → 127.0.0.1:8000`. Connections are chosen by **`profile_id`** — the React app never holds
  a DB password (invariant 4). All result derivation (KPIs, charts, summary, cascade) is **local and
  deterministic** ([ADR-021](ADR-021-sql-aware-derivation-and-cascade.md)) — no row data to any LLM.
- **Single viewport:** `h-screen + overflow-hidden` shell; only the grid scrolls. Verified at 1366×768.

## Consequences
- A premium executive surface that meets the CXO bar; first-run lands on *ask a question*, not admin.
- The React app holds **no secrets** and runs **no SQL except via `/execute`** (the chokepoint, ADR-005).
- **Two front-ends** to maintain during beta (React for users, Streamlit for admin) — accepted tradeoff;
  the API is the shared contract so neither duplicates business logic.
- Result data now traverses the API to a browser client (vs Streamlit's server-side render) — tracked
  as [RISK-22](../risk-register.md).

## Security
- Invariant 4 (no DB secrets client-side): connections by `profile_id`, resolved server-side.
- Invariant 1 (SELECT-only chokepoint, ADR-005) unchanged — React executes only via `/execute`.
- Networked deployments use the opt-in `X-API-Key` auth + explicit CORS allow-list ([ADR-013](ADR-013-network-edge-hardening.md)).

## Alternatives considered
- **Keep iterating Streamlit:** rejected — its theme/component model cannot reach the premium,
  summary-first executive bar (the redesign already failed the CXO review).
- **A different SPA framework:** React chosen because a shadcn/React scaffold already sat in the repo
  and the team had the primitives; the decision is the *bespoke executive surface*, not the framework.
