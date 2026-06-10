# Phase 6 — Independent Adversarial Review & QA (R2, re-review after remediation)

> **Reviewer:** Independent fresh-context agent (not the original author) · **Date:** 2026-06-10
> **Phase:** Phase 6 — Observability & Error Handling
> **Re-review scope:** the R6.3 remediation of the r1 findings (F-1…F-7). r1 verdict was **PASS-WITH-FIXES** with 2 blocking S2 (dependency/CI hygiene). See [phase-6-review-r1.md](phase-6-review-r1.md).
> **Environment:** Windows, CPython **3.13.2**. Validation was run against a **fresh, clean venv** (not the resident dev venv), installed strictly from `requirements-dev.txt`.

---

## Verdict: **PASS** (no open blocking)

The two blocking S2 findings are **fixed and re-verified by clean-room install**; the three
minor code findings (F-3/F-4/F-5) are fixed with regression tests; F-6 (doc) is corrected;
F-7 is formally deferred. The Phase-6 observability/error-handling core — already verified
in r1 — is unchanged in substance; the remediation touched only dependency pins and two small
correctness/hardening edits, with the full suite re-confirmed green.

**One honest residual, not blocking the code:** the "CI green on 3.11 **and** 3.13" claim is
now *installable and locally proven on 3.13*, but the GitHub workflow still has **never run**
(branch unpushed). The 3.11 leg is wheel-availability-confirmed + interpreter-agnostic, so the
risk is negligible, but it is **demonstrated only when the owner pushes**. Tracked as
[ITM-016](../issue-log.md) (Mitigating). I record PASS because every defect is fixed and the
sole outstanding item is a process step (push) the author cannot perform, not a code or test
gap.

---

## Re-verification of r1 findings

| ID | Sev | r1 issue | Re-verification (executed) | Status |
|----|-----|----------|----------------------------|--------|
| **F-1** | S2 | Pinned numpy/pandas had no cp313 wheels → 3.13 leg uninstallable | `requirements.txt` re-pinned: `numpy==2.2.6`, `pandas==2.2.3`, `streamlit==1.58.0`, `fastapi==0.136.3`, `uvicorn==0.49.0`, `Pillow==11.0.0`. **Clean `py -3.13 -m venv` + `pip install -r requirements-dev.txt` → all cp313 wheels, no source build.** Safety-critical `sqlglot==30.10.0` unchanged. | ✅ Fixed |
| **F-2** | S2 | `httpx` floor floated to 0.28 → `openai==1.43.0` `proxies` TypeError on both legs | `requirements-dev.txt` pins `httpx>=0.27,<0.28` (resolved `0.27.2`), `openai==1.43.0` retained. **Clean install + `pytest -q` → 185 passed** (the 5 previously-failing LLM tests now green). | ✅ Fixed |
| **F-3** | S3 | `TextFormatter` interpolated correlation id raw (CR/LF log-forge under text format) | Fixed **at ingress**: `sanitize_correlation_id` ([`errors.py`](../../src/core/errors.py)) strips to `[A-Za-z0-9_.-]`, bounds ≤128; applied in `request_id_middleware` so the header echo, body, and logs are all protected. Live test: inbound `X-Request-ID: "ok-1\r\nSet-Cookie: x=y"` → echoed token has no CR/LF/`:`/space and **no `Set-Cookie` header injected**. | ✅ Fixed |
| **F-4** | S4 | Logged `error_id` and body `error_id` could diverge off the happy path | `_db_error` now `set_request_id`s the id it uses; handlers fall back to `new_error_id()` so the body id is never null and matches the logged id. | ✅ Fixed |
| **F-5** | S4 | Leak test missed `/schemas/introspect` and didn't assert headers | Added `test_introspect_db_error_is_sanitized` + header-cleanliness assertions on the existing leak tests; +3 tests → **185**. | ✅ Fixed |
| **F-6** | Info | Package said "9 commits" for a 10-commit `d059295..HEAD` | Package now states the **code range** `d059295..fc55a46` (9 commits) explicitly + notes the +1 package commit. | ✅ Fixed |
| **F-7** | Info | Non-DB `str(exc)` surfaces (config 500, LLM 400, UI config) out of ITM-015 scope | Deferred → [ITM-017](../issue-log.md) (Phase-7 hardening); pre-existing, non-DB, no DSN/credential content. | ⏳ Deferred (accepted) |

## QA re-run (executed)

| Check | Method | Result |
|---|---|---|
| **Clean-room reproducibility (F-1/F-2)** | Fresh 3.13 venv ← `pip install -r requirements-dev.txt`; `pytest -q` | **185 passed.** All wheels cp313; no source builds; no `proxies` error. |
| **dev == shipped** | Re-synced the repo `.venv` to the pins; ran the documented command | **185 passed** — the documented run now reproduces the validated set. |
| **No regression from the F-3/F-4 edits** | Full suite incl. the ITM-015 leak/correlation/metrics probes | **PASS** — DB-error sanitization, `error_id` correlation, secret-free logs, idempotent logging, `/metrics` counts-only all still hold. |
| **Chokepoint still untouched** | `git diff d059295..HEAD -- src/db.py src/core/sql_safety.py` | **empty** — the remediation did not touch the SELECT-only path (one `oracledb.connect`, one `cur.execute`). |
| **F-3 ingress sanitization** | `test_inbound_request_id_is_sanitized_in_echo_header`, `test_sanitize_correlation_id_*` | **PASS** — CR/LF/space/colon stripped; bounded ≤128; empty→regenerate. |
| **F-5 introspect leak** | `test_introspect_db_error_is_sanitized` | **PASS** — generic body + `error_id`; host/user absent from body **and** headers; full detail server-side. |

## Could-not-verify (carried)

- **Real CI run on 3.11 + 3.13.** Not executable without a push (GitHub-only). F-1/F-2 are proven
  by a local clean install on 3.13 + cp311 wheel availability; the workflow run is demonstrated
  only on the owner's push ([ITM-016](../issue-log.md)).
- **Live Oracle / browser UI** — unchanged from r1 (synthetic driver exceptions; headless AppTest).

## Gate decision

**PASS.** r1's blocking items (F-1/F-2) are fixed and clean-install-verified; all minor findings
are fixed or formally deferred; 185 tests green; governed docs current. Phase 6 clears the exit
gate. The only follow-up is the owner pushing so CI demonstrates both interpreter legs (ITM-016,
non-blocking process step).
