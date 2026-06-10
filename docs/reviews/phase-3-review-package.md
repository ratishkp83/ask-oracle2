# Phase 3 — Review Package (input to the independent gate)

> **Prepared:** 2026-06-10 · For: owner-supplied independent reviewer · Gate: [external-review-gate](../process/external-review-gate.md)
> Hand the **filled Context block** below (plus this package) to the reviewer along with the [Adversarial Review & QA Prompt](../process/adversarial-reviewer-prompt.md). The reviewer writes findings to `docs/reviews/phase-3-review-r1.md`.

## Change set
- Phase 3 commit: `4949525` (range `9e96017..HEAD`).
- Diff: `git diff 9e96017..HEAD` · primary new code: `src/core/llm/*`, `src/nl2sql.py`, `src/api.py` (`/nl2sql`), `src/app.py` (Query Builder).

## Filled Context block (paste into the adversarial prompt)
- **Phase under review:** Phase 3 — NL→SQL 2.0 & LLM Abstraction.
- **Charter:** [charters/phase-3-charter.md](../charters/phase-3-charter.md) · **Design:** [oracle-llm-design.md](../oracle-llm-design.md).
- **Change set:** `9e96017..HEAD`.
- **Phase-specific invariants to attack (in addition to the standing list):**
  - External LLM prompts contain **schema names only** — never row/sample values or raw identifiers (redaction is by construction + `assert_no_values` tripwire). Try to get data into an external prompt.
  - `LLM_POLICY=external_disabled` must **never** instantiate/call an external provider.
  - A per-user `api_key` is used transiently and must not be logged or persisted.
  - Confidence is a **heuristic, not a guarantee** — check it cannot be read as correctness; probe for misleading High on wrong SQL.
  - NL→SQL still routes generated SQL through the central safety layer and never auto-executes.

## Test status
- `pytest -q` → **65 passed** locally (mocked provider; no live LLM/DB calls). New: `test_llm_redaction`, `test_llm_providers`, `test_llm_policy`, `test_llm_confidence`, `test_nl2sql`.
- Run: `pip install -r requirements-dev.txt` then `APP_SECRET_KEY=… PYTHONPATH=. pytest -q`.

## Known limitations / not covered (verify or flag)
- No live Oracle DB and no live LLM call in CI — generation quality and real connection/query success are **not** automatically tested.
- Confidence heuristic is coarse (AST identifier resolution); CTE/alias edge cases may mis-bucket.
- UI verified via headless `AppTest` only (no browser/visual pass).

## Expected reviewer output
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + exact repro), blocking list, QA results, could-not-verify — saved to `docs/reviews/phase-3-review-r1.md`.
