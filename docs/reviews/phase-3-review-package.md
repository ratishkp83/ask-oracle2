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
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + exact repro), blocking list, QA results, could-not-verify — saved to `docs/reviews/phase-3-review-r<n>.md`.

---

## r2 scope (after r1 remediation)

- **r1 verdict:** FAIL — see [phase-3-review-r1.md](phase-3-review-r1.md). All 6 findings worked; triage + dispositions in [issue-log.md](../issue-log.md) (Phase-3 section).
- **Remediation change set for r2:** `b77b571..HEAD` (the remediation commit). Focus on:
  - **F1** — `confidence.py` now validates JOIN predicates vs `schema.relationships`; re-run the bad-join probe → expect not `High`.
  - **F2** — provider failure → clean `LLMError` (no `RetryError`/repr); re-run the wrong-key probe at the HTTP layer.
  - **F4** — `validate_base_url` blocks non-https + private/loopback/link-local; re-run the `169.254.169.254` probe.
  - **F5** — per-table column resolution; re-run wrong-table-column probe.
  - **F6** — `repr(LLMConfig(api_key=…))` no longer shows the key.
  - **Regression:** full suite (now **75**) green; confirm no new gaps.
- F3 scrubbing and the CORS note are **deferred** (ITM-008/009, [RISK-12](../risk-register.md)) — confirm the deferral rationale is acceptable rather than re-raising as blocking.
- Output → `docs/reviews/phase-3-review-r2.md`.
