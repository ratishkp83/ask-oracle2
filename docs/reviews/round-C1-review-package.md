# Round C1 — Review Package (input to the independent gate)

> **Prepared:** 2026-06-12 · For: owner-supplied independent reviewer · Gate: [external-review-gate](../process/external-review-gate.md)
> Hand the **filled Context block** below (plus this package) to the reviewer along with the [Adversarial Review & QA Prompt](../process/adversarial-reviewer-prompt.md). The reviewer (fresh context, **not** the author) writes findings to `docs/reviews/round-C1-review-r1.md`.

## Scope of this review
Round C1 is consolidation + testing. The **code-touching** items are **B1–B3** (ITM-007/006/008);
B4 (CI confirm) and B5 (live-Oracle pass) are verification with recorded evidence, not code to
review. Review the code of B1–B3 and the standing invariants.

## Change set
- **Code range:** `a395003..f374380` (B1 `8e3a442` ITM-007 · B2 `5f64078` ITM-006 · B3 `f374380`
  ITM-008). **B5** (`5c1444d`) adds `scripts/c1_live_smoke.py` + evidence docs only (no product
  code) and may be skimmed for the evidence claim.
- **Primary code:**
  - `src/app.py` — 14 `use_container_width=True` → `width="stretch"` (B1); manual-connection
    "Save" button + `save_connection_config` call removed, startup uses `migrate_legacy_connection()` (B2).
  - `src/storage.py` — `save_connection_config` **removed**; `migrate_legacy_connection()` added
    (read-once + delete); `atomic_write_json` import dropped (B2).
  - `src/core/llm/pii.py` (new) + its wiring in `src/nl2sql.py` — opt-in `SCRUB_PII` masking on the
    external path only (B3).

## Filled Context block (paste into the adversarial prompt)
- **Phase under review:** Round C1 — Pre-GA Consolidation & Testing (code items B1–B3).
- **Charter:** [charters/round-C1-charter.md](../charters/round-C1-charter.md) · **Design:**
  [round-C1-design.md](../round-C1-design.md) · **Live-pass evidence:**
  [round-C1-live-pass.md](round-C1-live-pass.md).
- **Change set:** `a395003..f374380`.
- **Item-specific invariants to attack:**
  1. **ITM-006 — no second credential path, no plaintext at rest.** `save_connection_config` is
     gone; confirm nothing else writes `connection.json`. `migrate_legacy_connection()` must:
     import a legacy file once into the session and **delete it** (idempotent — `None` when
     absent); never leave a plaintext password on disk (it deletes the file, incl. any pre-F5
     file that held one). The encrypted `ProfileStore` (Fernet) remains the only persistence
     path; password still never returned by the API / shown in the UI. **Attack:** a legacy file
     with a `password` field — confirm it is removed from disk after startup.
  2. **ITM-008 — scrubbing is opt-in, external-only, and safe-by-default.** With `SCRUB_PII`
     unset/false the NL question is **verbatim** (no behaviour change). When set, masking applies
     **only** on the external-provider path (local generation verbatim) and **after** the existing
     schema-name redaction, never altering the schema context. **Attack:** confirm the flag-off
     default is untouched; that ordinary numeric thresholds (e.g. "salary over 100000") are **not**
     masked (over-masking would silently degrade queries); that masking can't corrupt the prompt
     structure; that no PII or key is logged.
  3. **ITM-007 — pure deprecation swap.** `width="stretch"` ⇔ the old `use_container_width=True`
     on every `st.button`/`st.dataframe`/`st.download_button`; no `use_container_width` remain; no
     behaviour change (7-section headless smoke green).
  4. **No regression** to the standing invariants — SELECT/CTE-only chokepoint (untouched:
     `git diff a395003..f374380 -- src/db.py src/core/sql_safety.py` should be empty),
     AI-proposes-never-runs, binds-as-values (ADR-007), secrets-via-env, metadata-only
     persistence, the Phase-6.5 edge/auth posture, and Phase-6 error sanitization.

## Test status
- `pytest -q` → **260 passed** (Python 3.13; mocked DB — no live calls). New: `test_pii.py` (15),
  `test_storage.py` (+3 → migration). **CI: green on 3.11 + 3.13** (run #12 on `f374380`).
- **Live-Oracle evidence (out-of-band):** `scripts/c1_live_smoke.py` against real **XE 21c** —
  connect/introspect/bound-report/export/safety **ALL PASS** ([evidence](round-C1-live-pass.md)).
  The reviewer may re-run it given an XE + the `.env` `AOR_LIVE_*` (read-only account).

## Known limitations / not covered
- **EBS templates** (GL/AP/AR/PO/OM) not validated against a real EBS instance — ITM-012 (needs EBS).
- **PII patterns** are deliberately conservative (recall < precision by design); not a compliance-grade DLP.
- **`migrate_legacy_connection`** imports into the session for convenience; the user still re-enters
  the password to persist an encrypted profile (the password was never stored).

## Expected reviewer output
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + `file:line` + repro),
blocking list (default: open S1/S2), QA results, could-not-verify — to `docs/reviews/round-C1-review-r1.md`.
