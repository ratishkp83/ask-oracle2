# Phase 3 — Independent Adversarial Review & QA (r2)

> **Reviewer:** Independent agent (fresh context; not the author) · **Date:** 2026-06-10
> **Phase:** Phase 3 — NL→SQL 2.0 & LLM Abstraction · **Remediation change set:** `b77b571..HEAD` (`29d956b`)
> **Prior iteration:** [phase-3-review-r1.md](phase-3-review-r1.md) (verdict: FAIL — 2 blocking). Triage/dispositions in [issue-log.md](../issue-log.md) (Phase-3 section).
> **Scope (per [package r2 scope](phase-3-review-package.md)):** re-run the F1/F2/F4/F5/F6 probes against the remediation, confirm no regression (full suite), and assess whether the F3 + CORS deferrals are acceptable rather than re-raising as blocking.
> **Method:** Read the full source diff `b77b571..HEAD`; ran the full `pytest` suite; **re-executed every r1 probe** against the patched code (mocked provider — no live LLM/DB) plus new SSRF-twist probes; reviewed the new tests for genuineness; reviewed issue-log + risk-register deferral records.

---

## 1. Verdict

**`PASS-WITH-FIXES`** — **no open blocking findings; the gate passes.**

Both r1 blockers (F1, F2) are remediated and I independently reproduced the corrected behavior, not merely trusting the new tests. The four r1 S3/S4 findings (F3–F6) are fixed or formally deferred with acceptable rationale. The full suite is green at **75 passed** (matches the package). One **new S4** hardening nit (F7) surfaced — an input-normalization gap in the `base_url` SSRF guard that is **not exploitable on the tested stack** (fails closed at DNS resolution) — recorded for backlog, non-blocking.

Per [external-review-gate §DoD #5](../process/external-review-gate.md), a verdict of `PASS-WITH-FIXES` with no open blocking findings **closes the gate** for Phase 3.

---

## 2. Remediation verification (r1 findings)

| r1 ID | Sev | Fix (commit `29d956b`) | Independent re-probe | Result |
|-------|-----|------------------------|----------------------|--------|
| **F1** | S2 | `confidence.py` validates JOIN `EQ` predicates against `schema.relationships` (both directions); caps at Medium when joins present but no relationship metadata | `… JOIN dept d ON e.salary = d.dept_id`: no-rel → **Medium**, with-rel → **Low** ("not backed by a known relationship"); good join `e.dept_id = d.dept_id` with rel → **High** | ✅ Fixed |
| **F2** | S2 | `@retry(..., reraise=True)` + `generate_sql_from_nl` wraps non-`LLMError` provider failures in a clean `LLMError`; never surfaces `RetryError`/repr/key | Failing `complete()` (raising `"401 … sk-LEAKME"`): function raises `src.core.llm.base.LLMError` "LLM request failed (RuntimeError). Check the API key, model, and provider settings."; **HTTP /nl2sql → 400** same message; no `RetryError`/`Future`/`sk-LEAKME` in body | ✅ Fixed |
| **F3** | S3 | `redaction.assert_no_values` docstring now scopes the tripwire to schema context and states the question is sent by design → `external_disabled`; scrubbing deferred to ITM-008 | Wording verified in source; behavior unchanged & documented | ✅ Fixed (wording) + deferred — **acceptable**, see §4 |
| **F4** | S3 | `validate_base_url`: requires `https`, blocks loopback/private/link-local/reserved/multicast IP literals + `localhost`/`metadata*`; called only on user-supplied URL | Blocks `https://169.254.169.254`, `http://…`, `https://metadata.google.internal`, `https://[::1]`; allows `https://api.openai.com` | ✅ Fixed (residual → F7/RISK-11) |
| **F5** | S3 | Per-table column resolution (qualified → its table; unqualified → any referenced table) | `SELECT dname, salary FROM dept` (SALARY is an EMP column) → **Medium** with `salary` reason | ✅ Fixed |
| **F6** | S4 | `field(..., repr=False)` on `LLMConfig.api_key` and `LLMSettings.api_key` | `repr(LLMConfig(api_key="sk-SECRET-123"))` and `repr(LLMSettings(...))` → key absent | ✅ Fixed |

**Regression sweep:** `external_disabled` invariant **still holds** post-patch — a `/nl2sql` request carrying an attacker `api_key`+`base_url` in the body returned 400 with `ExternalLLMProvider.__init__` **never called**. The central safety chokepoint is re-asserted by `test_execute_endpoint.py` (DROP/DELETE/UPDATE/INSERT/stacked/`FOR UPDATE` → 400), on which NL→SQL's post-generation check depends. No behavior I exercised in Phase-2 scope regressed.

---

## 3. New findings (this iteration)

| ID | Severity | Category | Location (file:line) | Description | Reproduction | Recommended fix |
|----|----------|----------|----------------------|-------------|--------------|-----------------|
| **F7** | **S4** | SSRF guard — input normalization | `src/core/llm/providers.py:17-39` (`validate_base_url`) | The guard checks `ipaddress.ip_address(host)` only against canonical literals, so **integer/hex/octal IP encodings of loopback** (`2130706433`, `0x7f000001`, `017700000001` = 127.0.0.1) fail `ip_address()`, are treated as *hostnames*, and are **allowed**. This is a different residual than the DNS-rebinding one documented in RISK-11. **Not exploitable on the tested stack:** `socket.getaddrinfo("2130706433", 443)` → `gaierror` (no resolution), so the connection fails closed before reaching loopback. Risk is platform/resolver-dependent and only matters once multi-tenant/untrusted callers exist (out of Phase-3 scope). | `validate_base_url("https://2130706433/v1")` → no error (ALLOW); but `getaddrinfo` does not resolve it on this host. | Reject hosts that parse as a bare integer / `0x…` / all-numeric, or normalize via `socket.getaddrinfo` + re-apply the private/loopback check, before constructing the client. Add to ITM-008/RISK-11 residual notes. Backlog. |

---

## 4. Deferral assessment (explicitly requested)

- **F3 / ITM-008 (NL-question PII scrubbing) — deferral ACCEPTABLE.** The user's free-text question is their own intent; the prompt carries no schema *values* by construction, and the hard control for tenants that must not export question text (`LLM_POLICY=external_disabled`) is implemented, tested, and now documented at the point of the tripwire. Reflexive scrubbing risks degrading legitimate queries (false positives on quoted nouns, dates, IDs that are part of intent). Deferring optional scrubbing as a backlog item, rather than blocking, is the right call — provided the gate-input wording no longer claims the tripwire covers the question text (it no longer does: [redaction.py](../../src/core/llm/redaction.py) docstring is corrected). **No re-raise.**
- **CORS / ITM-009 / RISK-12 — deferral ACCEPTABLE for Phase 3.** `allow_origins=["*"]` + `allow_credentials=True` + `0.0.0.0` bind is **pre-existing** (not introduced or worsened by Phase 3) and is inert for the current single-session, locally-run posture. It is logged with an owner, a concrete mitigation ("restrict origins + add auth before multi-tenant"), and tied to RISK-12 (Open) and RISK-07 (per-session, no auth — Accepted). Multi-tenant identity is explicitly **out of Phase-3 scope** (charter). Blocking Phase 3 on a pre-existing, scope-excluded hardening item would be inappropriate. **No re-raise** — but it **must** be resolved as a precondition to any networked/multi-tenant deployment (it gates Phase 7, not Phase 3).

---

## 5. QA results

| Case | Input | Expected | Observed | Outcome |
|------|-------|----------|----------|---------|
| Full suite | `PYTHONPATH=. pytest -q` | green, 75 | **75 passed**, 1 deprecation warning | ✅ matches package |
| F1 bad join (no rel) | `… ON e.salary = d.dept_id` | not High | Medium | ✅ |
| F1 bad join (with rel) | same + EMP.DEPT_ID→DEPT.DEPT_ID | Low | Low (+ reason) | ✅ |
| F1 good join (with rel) | `… ON e.dept_id = d.dept_id` | High | High | ✅ |
| F5 wrong-table column | `SELECT dname, salary FROM dept` | not High | Medium (+ `salary` reason) | ✅ |
| F2 provider failure (unit) | `complete()` raises `RuntimeError("401 … sk-LEAKME")` | clean `LLMError`, no leak | `LLMError`, no `RetryError`/`Future`/key | ✅ |
| F2 provider failure (HTTP) | `POST /nl2sql` same | 400 clean message | 400, clean; no leak | ✅ |
| F4 base_url guard | private IP / http / metadata / public https / `[::1]` | block / block / block / allow / block | as expected | ✅ |
| F7 base_url guard twist | `https://2130706433/v1`, `0x7f000001` | block (ideal) | **allowed by guard**, but DNS fails closed | ⚠️ S4 |
| F6 repr | `repr(LLMConfig/LLMSettings(api_key=…))` | redacted | key absent | ✅ |
| Invariant: `external_disabled` | `/nl2sql` with attacker key+base_url in body | no External built, 400 | External `__init__` not called, 400 | ✅ holds |
| Chokepoint regression | DROP/DELETE/UPDATE/INSERT/stacked/FOR UPDATE → `/execute` | 400 each | 400 each | ✅ |

**Test genuineness:** the new tests assert real behavior (e.g., `test_bad_join_with_relationships_is_low` checks the reason text; `test_nl2sql_provider_failure_is_clean` asserts `"RetryError" not in detail` and the key is absent). No test was weakened or made tautological to pass.

---

## 6. Could-not-verify

- **Live LLM error shapes** — still no live provider in CI. F2's fix is now resolver-agnostic (it maps *any* non-`LLMError` to a fixed message and never echoes the original), so a real Groq/OpenAI `AuthenticationError` cannot leak its body or the key through this path; this closes the r1 could-not-verify concern by construction.
- **F7 cross-platform exploitability** — confirmed non-resolving on this Windows host; **not** verified on a glibc/musl Linux container (the Docker deploy target), where resolver handling of integer IP literals can differ. Treated conservatively as S4 pending that check.
- **Live Oracle execution & browser/visual UI** — unchanged and out of scope this iteration (RISK-04).

---

## 7. Recommendation

Close the Phase-3 external-review gate. Record verdict `PASS-WITH-FIXES` (no open blocking) in the tracker + CHANGELOG and capture sign-off ([gate](../process/external-review-gate.md) DoD #5–6). Backlog **F7** under ITM-008/RISK-11. The two deferrals (ITM-008, ITM-009/RISK-12) are acceptable as logged; ITM-009 should be treated as a hard precondition for any multi-tenant/networked deployment.
