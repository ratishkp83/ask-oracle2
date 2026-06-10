# Phase 3 — Independent Adversarial Review & QA (r1)

> **Reviewer:** Independent agent (fresh context; not the author) · **Date:** 2026-06-10
> **Phase:** Phase 3 — NL→SQL 2.0 & LLM Abstraction · **Change set:** `9e96017..HEAD` (`b77b571`)
> **Inputs:** [phase-3-review-package.md](phase-3-review-package.md) · [adversarial-reviewer-prompt.md](../process/adversarial-reviewer-prompt.md) · [phase-3-charter.md](../charters/phase-3-charter.md) · [oracle-llm-design.md](../oracle-llm-design.md)
> **Method:** Static review of `src/core/llm/*`, `src/nl2sql.py`, `src/api.py`, `src/app.py`, `src/core/sql_safety.py`; full `pytest` run; six executed adversarial probes (confidence miscalibration, redaction vector, policy bypass, base_url/SSRF, error propagation, secret repr). All probes ran against a mocked provider — **no live LLM/DB calls**.

---

## 1. Verdict

**`FAIL — second iteration required`**

Two blocking (S2) findings. No S1 found: the headline safety/secrecy invariants hold — `external_disabled` never instantiates or calls an external provider (probe 4), redaction-by-construction keeps row values out of the schema context, generated SQL is re-validated by the central safety layer and never auto-executes, and no secret is written to logs or responses on any path I exercised. The two blockers are correctness/robustness defects where the **code is narrower than its own approved design**: the confidence heuristic omits the documented join signal (misleading `High`), and provider-call failures surface as an internal `RetryError[...]` repr instead of a clear message (the "graceful degradation on misconfiguration" success criterion is only partly met and partly mis-tested).

---

## 2. Findings table

| ID | Severity | Category | Location (file:line) | Description | Reproduction / exploit (exact input) | Recommended fix |
|----|----------|----------|----------------------|-------------|---------------------------------------|-----------------|
| **F1** | **S2** | Confidence / design-impl drift | `src/core/llm/confidence.py:21-60` (High at `:56-57`); design [oracle-llm-design.md §6](../oracle-llm-design.md) "joins known" | Heuristic reports **`High`** for SQL whose tables/columns all resolve **even when JOINs are nonsensical**. Design §6 promises `High = … joins known` and `Low = … unknown joins`, but the code never inspects join conditions against `schema.relationships`. A green "High" chip overstates correctness exactly as the invariant warned. | `assess_confidence("SELECT e.salary, d.dname FROM emp e JOIN dept d ON e.salary = d.dept_id", schema)` with EMP(EMP_ID,SALARY,DEPT_ID)+DEPT(DEPT_ID,DNAME) → **`High`**, reason "All referenced tables and columns resolve." Joining `salary = dept_id` is meaningless. | Implement the join-relationship signal (demote to `Medium`/`Low` when a join predicate is not backed by a known FK/relationship), **or** amend design §6 to drop the join claim and accept current behavior (then re-classify as S3). Update `test_llm_confidence.py` accordingly. |
| **F2** | **S2** | Error handling / graceful degradation | `src/nl2sql.py:61-63` (retry) → `src/api.py:215-216` (broad `except`) | On a **persistent provider call failure** (the common "invalid API key" / 401 case, where a key string *is* present so `is_available()` is `True`), `tenacity`'s default `reraise=False` raises `RetryError`, which the API returns verbatim as the 400 detail: `RetryError[<Future at 0x… state=finished raised RuntimeError>]`. The real cause (401) is swallowed; the message is non-actionable and leaks an internal object repr. Also retries 3× (~3 s backoff) on a non-transient auth error. Charter success criterion #3 ("graceful degradation on misconfiguration, **tested**") is only met for *missing* key, not *invalid* key — that path is untested. | `POST /nl2sql {natural_language, schema_csv}` where the selected provider's `complete()` raises (e.g. wrong `GROQ_API_KEY`). Confirmed via TestClient: `status 400 | detail: RetryError[<Future at 0x… raised RuntimeError>]`. | Add `reraise=True` to the `@retry` (and/or retry only transient errors); wrap provider failures in `LLMError` with a clear message ("LLM call failed: <provider> rejected the request — check the API key/model"). Add a test that a failing `complete()` yields a clean message, not `RetryError`. |
| **F3** | S3 | Redaction / assurance gap | `src/nl2sql.py:91-97`; `src/core/llm/redaction.py:16-46` | The `assert_no_values` tripwire scans **only the schema context** (which, by construction, already contains no values), and its markers ("sample values", "row data", …) essentially never appear in schema markdown — so it is close to a no-op. Meanwhile the **user's free-text NL question is appended verbatim** to the external prompt and is **never** scanned. The review-package invariant states external prompts carry "schema names only — never row/sample values or raw identifiers"; in reality a user question can carry both. Design §4 *does* document this nuance (mitigation = `external_disabled`), so behavior is as-designed — but the package's "by construction + tripwire" framing oversells the guarantee. | `generate_sql_from_nl("list employees where ssn = '123-45-6789' and email = 'jane.doe@acme.com'", schema)` → captured provider prompt contains the raw SSN/email; `assert_no_values(prompt)` passes clean. | Correct the invariant wording to scope it to *schema*-derived content; either scan/redact the question for obvious value patterns (quoted literals, digit runs) before external send, or surface a UI/API warning that question text leaves the tenant unless `external_disabled`. Extend `test_llm_redaction.py` to assert the question-text path. |
| **F4** | S3 | SSRF surface | `src/api.py:74` (`LLMSettings.base_url`) → `src/core/llm/providers.py:31-36` | A per-request `llm.base_url` is honored unvalidated, so the server builds an OpenAI client pointed at an **arbitrary caller-controlled host** and issues an outbound POST to it. With CORS `allow_origins=["*"]` (`src/api.py:35-41`) and the API bound to `0.0.0.0`, an exposed instance becomes an SSRF egress. Exploitability is limited (POST `/chat/completions` shape, Bearer auth, errors wrapped in `RetryError`), and multi-tenant is explicitly out of Phase 3 scope — hence S3, flagged before that scope lands. | `ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url="http://169.254.169.254/latest/v1"))` → client base_url = `http://169.254.169.254/latest/v1/`, `is_available()` True; a generate call POSTs there. | Allowlist scheme (`https`) and host (known provider domains, or an env-configured set) for `base_url`; reject otherwise with a clean 400. |
| **F5** | S3 | Confidence coarseness | `src/core/llm/confidence.py:12-18,42-48` | Column resolution uses a **global** column set, not the referenced table's columns, so a column that exists on a *different* table still counts as "resolved" → `High`. Compounds F1's over-confidence. | `assess_confidence("SELECT dname, salary FROM dept", schema)` where `SALARY` belongs to EMP, not DEPT → **`High`**. | Resolve each column against the column set of its (aliased) table where the AST permits; fall back to global only for unqualified columns with a single candidate table. |
| **F6** | S4 | Secret hygiene (defensive) | `src/core/llm/base.py:11-24` | `LLMConfig` is a plain dataclass, so its default `repr()` prints `api_key` in plaintext: `LLMConfig(provider='openai', …, api_key='sk-SECRET-123', …)`. No current code logs the config, but a single stray `logger.debug(cfg)` or a framework that reprs locals in a traceback would leak the transient key. | `repr(LLMConfig(api_key="sk-SECRET-123"))` → key visible. | Mark the field `api_key: Optional[str] = field(default=None, repr=False)` (and the same on `api.py:73`'s model if it gets logged). |

---

## 3. Blocking items (must be fixed before Phase 3 can close)

- **F1 (S2)** — confidence `High` on wrong-but-resolvable SQL; implement the documented join signal **or** amend design §6 and re-classify.
- **F2 (S2)** — `RetryError[...]` leaked as the user-facing error on provider-call failure; return a clean message and add the missing test.

S3 items (F3, F4, F5) should be fixed or **formally deferred** with rationale in the issue log per the [gate](../process/external-review-gate.md) DoD #4. F6 (S4) → backlog.

---

## 4. QA results

| Case | Input | Expected | Observed | Outcome |
|------|-------|----------|----------|---------|
| Automated suite | `pytest -q` (mocked provider) | green | **65 passed**, 1 deprecation warning | ✅ matches package |
| Confidence — bad join | `SELECT … FROM emp e JOIN dept d ON e.salary = d.dept_id` | not `High` (design §6) | `High` | ❌ → F1 |
| Confidence — wrong-table column | `SELECT dname, salary FROM dept` | not `High` | `High` | ❌ → F5 |
| Redaction — PII in question | NL question with SSN + email | value blocked or flagged | value sent; tripwire passes clean | ❌ → F3 |
| Policy — `external_disabled` + key + base_url | `select_provider(LLMConfig(api_key=…, base_url=…))` | `LLMError`, no External built | `LLMError`; `ExternalLLMProvider.__init__` **not** called | ✅ invariant holds |
| Policy — API path | `POST /nl2sql` under `external_disabled` | clean 400 message | `400` "External LLMs are disabled … NL→SQL is unavailable." | ✅ |
| base_url honored | external provider with `base_url=169.254.169.254` | (surface) | client points there; outbound on call | ⚠️ → F4 |
| Error — failing `complete()` | provider raises `RuntimeError("401 …")` | clear message, ≤ ? retries | `RetryError[<Future …>]`, 3 retries (~3 s) | ❌ → F2 |
| Secret — config repr | `repr(LLMConfig(api_key=…))` | redacted | key in plaintext | ⚠️ → F6 |
| Safety regression (NL→SQL) | model returns `DELETE FROM emp` | rejected | `ValueError` "not a SELECT/CTE" | ✅ |

**Contract integrity:** `/nl2sql` response `{ sql, explanation, confidence:{level, reasons[]} }` matches [05-api-contracts.md:37-42](../05-api-contracts.md). Governed docs (03/04/05/06, CHANGELOG, tracker) are in the same change set — DoD #2 satisfied. No drift between the endpoint and the contract doc; the only doc/impl drift is F1 (design §6 join claim).

**Graceful-failure spot check:** `external_disabled`, missing key, empty NL, and empty schema all produce clean 400s / `ValueError`s with no stack trace to the user. The exception is the provider-call-failure path (F2).

---

## 5. Could-not-verify

- **Live generation quality & real provider error shapes** — no live LLM in CI. Whether a real Groq/OpenAI `AuthenticationError` string ever embeds the `api_key` (it normally does not) is unverified; F2's fix should map provider errors to a fixed message regardless, closing this.
- **Live Oracle execution** — `/execute` and `run_select` against a real DB (timeout enforcement, truncation honesty) were not exercised; out of Phase 3 scope and unchanged here.
- **Browser/visual UI** — Query Builder verified only by reading `src/app.py`; confidence chip / explanation rendering and widget-key collisions were not exercised in a live Streamlit session.
- **Pre-existing, out-of-Phase-3 observations (not scored here):** CORS `allow_origins=["*"]` with `allow_credentials=True` and `0.0.0.0` binding (`src/api.py:33-41`) predate this phase but amplify F4 once multi-tenant lands — recommend tracking separately.
