# Phase 7 — Review Package (input to the independent gate)

> **Prepared:** 2026-06-12 · For: owner-supplied independent reviewer · Gate: [external-review-gate](../process/external-review-gate.md)
> Hand the **filled Context block** below (plus this package) to the reviewer along with the [Adversarial Review & QA Prompt](../process/adversarial-reviewer-prompt.md). The reviewer (fresh context, **not** the author) writes findings to `docs/reviews/phase-7-review-r1.md`.

## Change set
- **Code range:** `baf4224..HEAD` (Phase-7 build). Build commits: `52a4c57` B1 (packs) · `9b6b5cd`
  B2 (NL→SQL enrichment) · `d0a1f7a` B4 (`/packs`) · `c2616d3` B3 (UI) · `e410d36` B5 (`/v1`) ·
  this B6/B7 commit (23ai deferral + doc sweep). `10dbcd6`/`4ae3962` are the charter/design docs.
- **Primary new/changed code:**
  - `src/core/ebs_packs.py` (new) — curated `EbsPack`/`TableNote`/`GlossaryTerm` for 5 modules +
    `build_ebs_context(modules)` (metadata-only markdown).
  - `src/nl2sql.py` — opt-in `ebs_modules` appends EBS context **external-path only**, before the
    `assert_no_values` tripwire (combined context verified).
  - `src/api.py` — `/packs` + `/packs/{module}`; `/nl2sql` `ebs_modules[]`; **all routes moved to an
    `APIRouter` mounted at `""` and `/v1`** (T-18); handlers/middleware/auth stay on `app`.
  - `src/core/auth.py` — `EXEMPT_PATHS` adds `/v1/health`.
  - `src/app.py` — Data Dictionary EBS-packs browser + Query Builder module multiselect.

## Filled Context block (paste into the adversarial prompt)
- **Phase under review:** Phase 7 — EBS Intelligence & 23ai (EBS metadata packs + `/v1`; 23ai
  deferred).
- **Charter:** [charters/phase-7-charter.md](../charters/phase-7-charter.md) · **Design:**
  [ebs-intelligence-design.md](../ebs-intelligence-design.md) · **ADRs:**
  [ADR-015](../adr/ADR-015-ebs-metadata-packs.md) (packs), [ADR-016](../adr/ADR-016-defer-23ai-vector-track.md) (23ai defer).
- **Change set:** `baf4224..HEAD`.
- **Invariants to attack:**
  1. **EBS context is metadata-only and tripwire-safe.** `build_ebs_context(...)` must contain no
     row data and **none** of `redaction._FORBIDDEN_MARKERS`; the *combined* schema+EBS context
     must pass `assert_no_values` on the external path. **Attack:** can any pack field carry a
     value-looking payload that trips (or evades) the guard? Is the tripwire run over the combined
     context, not just the schema part?
  2. **Opt-in, external-only, no behaviour change by default.** `ebs_modules` unset/empty →
     `/nl2sql` and `generate_sql_from_nl` are byte-identical to before. The **local** provider path
     never receives EBS context. **Attack:** confirm the local branch is untouched; confirm an
     empty/`None`/unknown-module list yields no EBS text.
  3. **AI still proposes, never runs.** Packs only enrich the prompt; nothing executes. The
     generated SQL is still verified `is_safe_select` before return.
  4. **`/v1` parity + back-compat + no privilege change.** Every route answers identically at `/x`
     and `/v1/x`; the app-level auth dependency and exception handlers apply to both; `/v1/execute`
     enforces the SELECT-only chokepoint; `/health` and `/v1/health` are the only auth-exempt paths.
     **Attack:** try to reach a route on `/v1` that bypasses auth or the safety gate; confirm no
     route was dropped or duplicated with divergent behaviour.
  5. **Chokepoint untouched.** `git diff baf4224..HEAD -- src/db.py src/core/sql_safety.py` must be
     empty.
  6. **`/packs` is read-only metadata.** No write/DB access; 404 envelope carries `error_id`; no
     secret-shaped fields in the contract.
  7. **No regression** to standing invariants — secrets-via-env, metadata-only persistence,
     Phase-6 error sanitization, Phase-6.5 edge posture, the redaction guarantee.

## Test status
- `pytest -q` → **289 passed** (Python 3.13; mocked LLM, no live DB). New: `test_ebs_packs.py` (9),
  `test_packs_api.py` (5), `test_nl2sql.py` EBS context (+3), `test_v1_prefix.py` (6),
  `test_ebs_pack_validate.py` (4) — **+27** over Round C1's 262. CI runs the 3.11 + 3.13 matrix on push.
- **ITM-012 validation tooling** (also in range): `scripts/ebs_pack_validate.py` (live-EBS diff via the
  chokepoint; offline-tested) + the confidence-flagged [self-audit](ebs-pack-self-audit.md). The
  reviewer may sanity-check the curated names against Oracle eTRM/TRMs; a live-EBS run needs an instance.

## Known limitations / not covered
- **Pack contents vs a real EBS instance** — not validated (table/column names vary by version /
  customization); **ITM-012** (review-before-run, like templates).
- **23ai vector track** — deferred by design ([ADR-016](../adr/ADR-016-defer-23ai-vector-track.md), ITM-018); no code.
- **PII scrubbing** of the NL question is the separate opt-in ITM-008 (unchanged here).

## Expected reviewer output
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + `file:line` + repro),
blocking list (default open S1/S2), QA results, could-not-verify — to `docs/reviews/phase-7-review-r1.md`.
