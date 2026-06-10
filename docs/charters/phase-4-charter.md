# Phase 4 Charter — Reports, Templates & UX

> **Document:** Phase Charter · **Version:** 1.0 · **Status:** Discovery (open — decisions pending owner approval) · **Owner:** Product/Engineering · **Last updated:** 2026-06-10

## Lifecycle stage
**Discovery.** This charter frames objectives, scope, deliverables, risks, success
criteria, and the **open decisions** (§ Decisions) the owner must resolve. **No code
is written until the owner approves the charter and resolves the decisions.** Once
resolved, this section is rewritten as "Decisions (resolved YYYY-MM-DD)" and Design
proceeds, then Development.

## Context — where we are today (grounding facts)
- **Saved reports exist but are minimal.** `src/storage.py` persists a flat
  `storage/reports.json` keyed by name with value `{"sql": "..."}` only — **no
  parameters, no profile binding, no metadata** (owner/description/timestamps).
- **Reports are UI-only.** The Streamlit "Saved Reports" tab can save the current
  generated SQL, list, view, and delete. There is **no `/reports` API** — an
  asymmetry versus the profiles/execute architecture where UI and API share one core.
- **No templates exist.** EBS-oriented starter reports (GL/AP/AR/PO/OM) are net-new.
- **Export already works** (CSV/XLSX) in `_run_and_display`.
- **The executor does not bind parameters.** `OracleClient.run_select` / `/execute`
  call `cur.execute(sql)` with **no binds**. Parameterized reports therefore require
  extending the execute path to accept a binds map — a **safety-relevant** change that
  must preserve the SELECT/CTE-only chokepoint (non-negotiable).
- **UX is top tabs**, not a left-nav: `Connections · Schema Upload · Explore Schema ·
  Query Builder · Saved Reports · Settings`; the sidebar is the active-connection chooser.

## Objectives
1. **Promote saved reports** from "named SQL blob" to **first-class, parameterized,
   profile-bindable artifacts** with metadata — persisted via a core module, runnable
   end-to-end through the existing safety chokepoint, exportable.
2. **Ship a starter EBS template catalog** (GL/AP/AR/PO/OM) of curated, parameterized,
   **review-before-run** SQL that seeds the analyst rather than guessing the schema.
3. **Rework the UX** to a clearer left-nav information architecture without regressing
   existing flows.

## Scope — in (subject to Decisions)
- **Report model v2**: `id`, `name`, `description`, `sql`, typed `parameters[]`,
  optional `default_profile_id`, optional `template_id`, `created_at`/`updated_at`.
  Tolerant load + **migration of legacy `{name: {sql}}` entries**.
- **Parameterization via Oracle bind variables only** (`:name`) — **never** string
  interpolation into SQL (would bypass the SELECT-only guarantee). Typed params
  (string / number / date) with a values form at run time.
- **Execute-with-binds**: extend `/execute` + `run_select` to accept an optional
  `binds` map; the safety layer still parses the SQL **text** (binds are values, not
  identifiers) and remains SELECT/CTE-only and fail-closed.
- **Connection-profile binding**: a report may carry a default profile; user can
  override at run; missing/renamed profile warns (does not hard-fail).
- **EBS template catalog (starter set)**: curated parameterized SELECTs across
  GL/AP/AR/PO/OM, clearly labelled "standard EBS reference — review before running,"
  never auto-executed, editable, save-as-report.
- **Left-nav UX rework**: a sidebar navigation grouping the workflow
  (Connect → Schema → Ask/Build → Reports → Templates → Settings), keeping a single
  Streamlit app and shared session state; existing flows preserved.
- **Tests + governed-doc updates** in the same change set (D3/D4/D5/D6, ADR(s),
  CHANGELOG, traceability, risk/issue, tracker).

## Scope — out (explicit non-goals for Phase 4)
- **No scheduling/automation** of report runs (no cron, no email delivery).
- **No charts/visualization** — tabular results + existing CSV/XLSX export only.
- **No RBAC / report ownership / sharing** — there is no identity layer yet (per-session).
- **No list/multi-value binds** (`IN (:list)` expansion) in v1 — scalar binds only;
  deferred to a follow-up.
- **No revival of the inactive React/Vite scaffold** — Streamlit remains the UI.
- **No EBS schema auto-detection / version adaptation** — templates assume standard EBS
  table names and are presented as editable starting points, not guaranteed-runnable.
- **No live-Oracle validation of template SQL** in this phase (covered by the pre-GA
  manual/live-DB pass, RISK-04); templates are validated against the safety layer and
  by structural/unit tests, not against a real EBS instance.

## Deliverables
- `src/core/reports.py` — Report model + store (CRUD), migration of legacy reports;
  supersedes the report functions in `storage.py`.
- Bind-parameter plumbing through `run_select`/`/execute` (+ `db.py`); D5 contract update.
- Template catalog (curated parameterized EBS SQL) as a versioned data module.
- UI: left-nav rework; Reports section (param form + profile binding + run + export);
  Templates browser (preview → load into builder → save-as-report).
- **(If API parity approved)** `/reports` CRUD + `/reports/{id}/run` (run via the same
  safety chokepoint with binds).
- Tests: report CRUD + migration; **bind-safety** (binds cannot smuggle DML; SELECT-only
  still holds); template load/shape; execute-with-binds; UI smoke for the new nav.
- Governed docs: this charter (resolved), D3 Architecture, D4 Data Models (Report v2),
  D5 API Contracts, D6 Test Strategy, ADR(s), CHANGELOG, traceability (FR-8 upgrade +
  new FRs), risk/issue register, task tracker.

## Risks
| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R4-1 | Parameter interpolation → SQL injection / **SELECT-only bypass** | **Critical** | **Bind variables only**, never string-format; safety layer parses SQL text unchanged; explicit tests that binds cannot introduce DML/stacked SQL |
| R4-2 | EBS templates assume standard schema → fail/mislead on customized instances | High | Label "standard EBS reference — review before running"; editable starting points; never auto-run; documented assumption |
| R4-3 | Legacy `reports.json` (`{sql}` shape) breaks under Report v2 | Medium | Tolerant loader + one-time migration; regression test on old shape |
| R4-4 | UX refactor regresses existing flows / session-state sharing | Medium | Single-file app + shared session state; incremental; smoke tests for every section |
| R4-5 | Execute-with-binds weakens the chokepoint | **High** | Binds are values not text; SQL still fully parsed; adversarial tests; reviewed at the exit gate |
| R4-6 | Scope creep (reports × params × profiles × templates × API × UX) overloads the phase | Medium | Starter template set; scalar binds only; defer scheduling/charts/list-binds; decisions fix the scope envelope up front |
| R4-7 | Profile binding to PROD encourages unreviewed runs | Low | Read-only by construction; override + warn on run; optional PROD run confirmation |

## Success criteria (phase exit)
1. Reports support **typed parameters via bind variables** (no string interpolation),
   optional profile binding, and metadata; persisted and migrated from the legacy shape.
2. A parameterized/saved report runs **end-to-end through the `/execute` chokepoint with
   binds**, stays SELECT/CTE-only, and exports to CSV/XLSX.
3. A **starter EBS template catalog** (count/coverage per Decisions) is browsable,
   parameterized, clearly labelled, and never auto-executes.
4. **Left-nav UX** is in place; all pre-existing flows work (smoke tests green).
5. Tests green in CI; governed docs updated in the same change set.
6. **Independent adversarial review + QA returns PASS / PASS-WITH-FIXES (no open
   blocking)** per the [gate](../process/external-review-gate.md); **reviewer agent
   supplied by the owner**.

## Decisions (OPEN — to resolve at approval)
Recommended option is **bolded**; the rest are documented for an informed choice.

- **D-A — Report store format.** **Keep the flat JSON file store** (`reports.json`,
  upgraded to Report v2 shape) for consistency with current architecture / no-auth
  reality. *(Alt: move to SQLite — deferred until multi-tenant/Phase 7.)*
- **D-B — Parameter scope.** **Scalar binds only** (string/number/date) in v1.
  *(Alt: also support `IN (:list)` multi-value expansion now — more power, more
  bind-safety surface; recommend deferring.)*
- **D-C — Template approach.** **Curated parameterized SQL templates** (deterministic,
  high analyst value, labelled review-before-run). *(Alts: NL-prompt presets that feed
  NL→SQL — safer re: schema variance, less deterministic; or a hybrid.)*
- **D-D — Template catalog size (v1).** **~2–3 per module across GL/AP/AR/PO/OM
  (~10–15 total)** as a starter pack. Owner to confirm which modules are highest
  priority and the per-module count.
- **D-E — UX depth.** **Sidebar left-nav (radio) + single app + shared session state**;
  keep current flows. *(Alt: full Streamlit multipage `pages/` refactor — cleaner URLs,
  but restructures app and session/connection sharing; recommend deferring.)*
- **D-F — API parity for reports.** **Add `/reports` CRUD + `/reports/{id}/run` and put
  report storage in `src/core/reports.py`** (UI + API share one core, run via the
  chokepoint) — coherent and testable. *(Alt: keep reports UI-only this phase; smaller
  scope, but leaves the asymmetry and an untested run path.)*
- **D-G — Bind transport through `/execute`.** Extend the execute contract with an
  optional `binds: {name: value}` map; `run_select` passes it to `cur.execute(sql, binds)`;
  safety check on SQL text is unchanged. (Mechanism follows from D-B/D-F; flagged because
  it touches the non-negotiable chokepoint and will be a focus at the exit gate.)
- **D-H — Profile-binding semantics.** Store nullable `default_profile_id`; user can
  override at run; if the bound profile is missing, **warn and require selection** (no
  hard-fail). Optional confirmation when the target environment is PROD.
- **D-I — Confirm out-of-scope list.** Owner to confirm the § "Scope — out" exclusions
  (scheduling, charts, RBAC/sharing, list-binds, React revival, schema auto-detection,
  live-DB template validation).

## Open questions for the owner
1. Which EBS modules matter most, and how many templates per module for v1 (D-D)?
2. API parity now or UI-only this phase (D-F)?
3. Template style: curated SQL, NL presets, or hybrid (D-C)?
4. UX depth: sidebar nav now, or full multipage refactor (D-E)?
5. Any must-have report parameter type beyond string/number/date (D-B)?

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Discovery charter opened; decisions pending owner approval. |
