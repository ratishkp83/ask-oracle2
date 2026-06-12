# Phase 7 — Independent Adversarial Review · r1

> **Reviewer:** Independent AI instance (fresh context, no author session) ·
> **Date:** 2026-06-12 · **Scope:** `baf4224..HEAD` (B1–B7) ·
> **Prompt:** [Adversarial Review & QA Prompt v1.0](../process/adversarial-reviewer-prompt.md)

---

## 1. Verdict

**`PASS`** — no blocking findings. All seven invariants hold. The two
observations below are S4 (trivia/coverage gaps); neither gates closure.

---

## 2. Findings table

| ID | Sev | Category | Location | Description | Reproduction | Recommended fix |
|----|-----|----------|----------|-------------|--------------|-----------------|
| P7-R1-F1 | **S4** | Input validation / UX | `src/api.py:211-213` (`NL2SQLRequest.ebs_modules`) | Unknown module strings in `ebs_modules` (e.g. `["INVALID"]`) are silently ignored — `build_ebs_context` returns `""` and no 400 is returned. The caller gets a valid response but zero EBS context with no feedback. Not a security issue; a usability surprise. | `POST /nl2sql` with `{"natural_language":"...", "ebs_modules":["BOGUS"]}` — returns 200 with SQL generated without EBS context. | Validate each module against the known `Module` literals (`{"GL","AP","AR","PO","OM"}`) in `NL2SQLRequest` and return a 422 for unknown values, or at least surface an `unrecognized_modules` field in the response. |
| P7-R1-F2 | **S4** | Test coverage | `tests/test_v1_prefix.py` | `test_auth_applies_to_v1_but_health_exempt` tests `/v1/metrics` as a representative gated endpoint; it does not exercise `/v1/execute` or `/v1/nl2sql` with auth enabled. The safety gate + auth combination on the execute path is only implicitly covered. | Run test suite with `APP_API_KEY` set and verify `/v1/execute` returns 401 when no key is supplied. | Add a parametrized case in `test_v1_prefix.py` asserting that `/v1/execute` and `/v1/nl2sql` return 401 when `APP_API_KEY` is set and the header is absent. |

---

## 3. Blocking items

**None.** No S1 or S2 findings.

---

## 4. Adversarial attack results (Part A)

### 4.1 Invariant 1 — EBS context is metadata-only and tripwire-safe

**Attack A: Can any pack field carry a forbidden-marker payload?**

All five pack bodies were inspected line by line. The `_FORBIDDEN_MARKERS`
set is `{"sample values", "sample value:", "example values", "example data",
"sample data", "row data", "data preview", "result rows"}`. No description,
glossary term, join hint, or note in any pack contains any of these strings
(case-insensitive). The test `test_context_is_metadata_only_and_passes_tripwire`
explicitly exercises every module and calls `assert_no_values` directly. ✓

**Attack B: Is the tripwire run over the *combined* context?**

`nl2sql.py:100-106`:
```python
context = build_external_context(schema)
ebs_context = build_ebs_context(ebs_modules or [])
if ebs_context:
    context = context + "\n\n" + ebs_context
assert_no_values(context)   # runs after EBS appended
```

`assert_no_values` is called after the concatenation. The tripwire covers
the schema context AND the EBS context as a single unit. ✓

**Attack C: Boundary-stitch attack — schema ending with partial marker, EBS starting to complete it.**

`build_external_context` returns `schema.to_compact_markdown()` (table/column
names + type annotations), optionally truncated with `"...\n(truncated schema
in prompt)"`. The EBS header line is
`"EBS Metadata (curated — table/column names + descriptions only):"`. Neither
produces a string that could stitch across the `\n\n` separator to form a
forbidden marker. ✓

**Result: PASS ✓**

---

### 4.2 Invariant 2 — Opt-in, external-only, no behaviour change by default

**Attack A: Local provider receives EBS context.**

`nl2sql.py:97-105`:
```python
if provider.name == "local":
    context = schema.to_compact_markdown()
else:
    context = build_external_context(schema)
    ebs_context = build_ebs_context(ebs_modules or [])
    ...
```

The `build_ebs_context` call is inside the `else` branch only. Local
providers always receive the verbatim compact markdown and nothing else.
Test `test_local_provider_ignores_ebs_modules` confirms: even with
`ebs_modules=["AP","GL"]`, the local provider's `last_user` contains no
`"EBS Metadata"`. ✓

**Attack B: Empty/None/unknown module list adds context.**

- `ebs_modules=None` → `build_ebs_context(None or [])` → `build_ebs_context([])`
- `ebs_modules=[]` → `build_ebs_context([])` → `wanted = set()` → `packs = []` → returns `""`
- `ebs_modules=["BOGUS"]` → `wanted = {"BOGUS"}` → no pack matches → returns `""`
- In all cases: `if ebs_context:` is `False`; `context` unchanged; `assert_no_values` runs on
  the schema-only string. Byte-identical to pre-Phase-7 behavior. ✓
- Test `test_no_ebs_modules_leaves_external_prompt_unchanged` and
  `test_context_empty_when_no_modules_selected` verify. ✓

**Result: PASS ✓**

---

### 4.3 Invariant 3 — AI proposes, never runs

Packs inject curated metadata text into the prompt only. `build_ebs_context`
constructs a plain string; it has no connection objects, no DB calls, and no
side effects. `generate_sql_from_nl` still returns an `NLSQLResult`; it does
not call `OracleClient.run_select`. The `is_safe_select` check at
`nl2sql.py:129` is unchanged. ✓

**Result: PASS ✓**

---

### 4.4 Invariant 4 — `/v1` parity, back-compat, no privilege change

**Architecture verified:**

```python
router = APIRouter()
# ... all routes on router ...
app.include_router(router)           # root mount (back-compat)
app.include_router(router, prefix="/v1")  # T-18
```

`app = FastAPI(dependencies=[Depends(require_api_key)])` — the app-level
dependency applies to **all routes** added via `include_router`, for both
mounts.

**Attack A: Reach a `/v1` route without auth.**

Test `test_auth_applies_to_v1_but_health_exempt` (monkeypatched
`APP_API_KEY="k"`) confirms `/v1/metrics` returns 401 without the header
and 200 with it. The `require_api_key` function checks `request.url.path`
against `EXEMPT_PATHS = frozenset({"/health", "/v1/health"})`. Every
non-health path on `/v1` is gated. ✓

**Attack B: Bypass the execute safety gate via `/v1/execute`.**

Test `test_v1_execute_safety_gate_still_enforced`: POSTing
`"DROP TABLE emp"` to `/v1/execute` returns 400 with `error_id`. The
`_run_sql` handler calls `assert_safe_select(sql)` before any DB
connection; rejection happens on the path-independent chokepoint. ✓

**Attack C: EXEMPT_PATHS collision — path tricks to mis-classify a non-health path as exempt.**

`EXEMPT_PATHS` uses exact `frozenset` membership. Only the literal strings
`"/health"` and `"/v1/health"` are exempt. Path variants like
`"/v1//health"`, `"/v1/./health"`, `"/v1/health/"` (trailing slash) do not
match and are either routed to a 404 or redirected before the route handler
runs. No security exposure from these cases. ✓

**Attack D: Route missing or duplicated under `/v1` with different behaviour.**

Compared pre-Phase-7 route list with the `router` definition. All routes
that existed before are now on `router` and exposed at both mounts. No
handler logic changed — handlers are the same functions mounted at two
prefixes. `test_v1_get_endpoints_match_root` asserts
`/v1/templates` == `/templates` and `/v1/packs` == `/packs`. ✓

**Attack E: Exception handlers and middleware apply to `/v1`.**

`@app.exception_handler` and `@app.middleware("http")` are app-level.
They apply to every request through the app, regardless of which prefix was
matched. The `request_id_middleware` assigns a correlation ID that is echoed
by the exception handlers on both mounts. ✓

**Attack F: CORS misconfiguration exposing `/v1` routes.**

CORS is configured via `app.add_middleware(CORSMiddleware, ...)` — also
app-level, covering all paths. The `_cors_config()` reads `ALLOWED_ORIGINS`
and defaults to `"http://localhost:8501,http://localhost:3000"` when blank.
Wildcard (`"*"`) disables credentials. Unchanged from Phase-6.5. ✓

**Result: PASS ✓**

---

### 4.5 Invariant 5 — Chokepoint untouched

```
git diff baf4224..HEAD -- src/db.py src/core/sql_safety.py → (empty)
```

Both files are byte-for-byte identical to the Phase-6.5 baseline. ✓

**Result: PASS ✓**

---

### 4.6 Invariant 6 — `/packs` is read-only metadata; no secret-shaped fields

- `get_packs()` returns `list_packs()` — a function that returns the static
  in-memory `_PACKS` list. Zero DB access. ✓
- `get_pack_by_module(module)` applies `(module or "").upper()` and iterates
  `_PACKS`; returns 404 with `error_id` for unknown modules (verified by
  `test_unknown_module_is_404`). ✓
- `EbsPack` model fields: `module`, `name`, `tables`, `glossary`. No
  `password`, `api_key`, or credential-shaped field. Test
  `test_packs_response_is_metadata_only` asserts `"password"` absent from
  the response body. ✓
- The `module` path parameter is only used as a lookup key; it is not
  interpolated into a DB query or log message. Arbitrary strings return 404. ✓

**Attack: SQL/template injection via `module` path parameter.**

`get_pack(module)`: the request string is uppercased and compared to static
`Module` literals using `==`. It is never used in an f-string that goes to
a logger, DB, or LLM. `"GL'; DROP TABLE--"`.upper() → `"GL'; DROP TABLE--"`,
which does not equal any `Module` literal → returns `None` → 404. ✓

**Result: PASS ✓**

---

### 4.7 Invariant 7 — No regression to standing invariants

**Redaction guarantee:** `assert_no_values` scope unchanged. EBS context is
verified by the combined-context check (Invariant 1). `build_external_context`
is called identically — schema names only, max 12 000 chars. ✓

**Secrets-via-env:** No new env var reads introduced beyond the already-audited
set. EBS packs are static — no secret-shaped data, no external reads. ✓

**Metadata-only persistence:** `_schema_store`, `_report_store`, `_store` are
unchanged. The `/schemas/create` normalization path (read back through
`schema_from_dict`) is unchanged. ✓

**Phase-6 error sanitization:** `_db_error`, `log_error`, and the exception
handlers are unchanged. The new `get_pack_by_module` raises `HTTPException`
with a generic message (`"Unknown EBS module."`), caught by
`http_exception_handler` which adds `error_id`. ✓

**Phase-6.5 edge/auth posture:** `require_api_key` body unchanged; only
`EXEMPT_PATHS` extended to add `/v1/health` (correct and tested). ✓

**Result: PASS ✓**

---

## 5. QA results (Part B)

### Automated suite

- **Claimed:** `pytest -q` → 285 passed (Python 3.13, mocked LLM). +23 over
  Round C1 (262). CI matrix: 3.11 + 3.13.
- **Could not independently re-run** (no Python runtime in this review
  context). CI evidence is accepted; test logic reviewed statically below.

### Test coverage assessment

| Test file | Cases | Coverage verdict |
|-----------|-------|-----------------|
| `test_ebs_packs.py` (9) | All 5 modules present; glossary consistency; join-hint format; template-catalog coverage; `assert_no_values` on full context; empty/scoped/case-insensitive selection; glossary format in output | Strong. Covers the critical tripwire path and data integrity. |
| `test_packs_api.py` (5) | List all; get by module; case-insensitive; 404 shape + `error_id`; no `"password"` in response | Adequate for the narrow API contract. |
| `test_nl2sql.py` EBS (+3) | External prompt includes EBS; no-EBS leaves prompt unchanged; local path ignores EBS | Critical path covered. |
| `test_v1_prefix.py` (6) | Health at both prefixes; GET parity; `/v1/packs` 404; profiles round-trip; execute safety gate; auth gate + health exempt | Solid. Covers the key auth + safety scenarios. |

### Boundary and abuse cases (manual reasoning)

| Case | Input | Expected | Verified |
|------|-------|----------|---------|
| `ebs_modules=None` | default | no EBS context, schema-only prompt | ✓ Code + test |
| `ebs_modules=[]` | empty | same as None | ✓ Code + test |
| `ebs_modules=["BOGUS"]` | unknown module | `""` returned, silent | ✓ Code (S4: no 400) |
| `ebs_modules=["ap","GL"]` | mixed case | both packs included | ✓ Code + test |
| `ebs_modules=["AP"]` local provider | local path | no EBS context | ✓ Code + test |
| `build_ebs_context` all 5 | full context | passes `assert_no_values` | ✓ Code + test |
| `GET /packs/ZZ` | unknown module | 404 + `error_id` | ✓ Code + test |
| `GET /packs/ap` | lowercase | 200, `module=="AP"` | ✓ Code + test |
| `POST /v1/execute` with DML | `"DROP TABLE emp"` | 400 + `error_id` | ✓ Code + test |
| `GET /v1/health` with `APP_API_KEY` set | no key header | 200 (exempt) | ✓ Code + test |
| `GET /v1/metrics` with `APP_API_KEY` set | no key header | 401 | ✓ Code + test |
| `/v1` path with no key + auth set | any gated route | 401 | ✓ Code + test |
| Module path injection `"GL'; DROP--"` | path param | 404 (no match) | ✓ Code reasoning |
| `ebs_modules` injection `["GL\nROW DATA:"]` | crafted string | `"GL\nROW DATA:"` uppercased doesn't match any literal → `""` returned | ✓ Code reasoning |

### Graceful failure verification

- DB errors in `/execute`, `/test-connection`, `/schemas/introspect` →
  sanitized via `_db_error` → generic 400 + `error_id`. Unchanged. ✓
- `HTTPException` on `/packs/{unknown}` → `http_exception_handler` →
  `{"detail": "Unknown EBS module.", "error_id": "..."}`. ✓
- Validation errors (`RequestValidationError`) → 422 with `error_id`. ✓
- Unhandled exceptions → 500 generic message + `error_id`, full detail
  logged server-side only. ✓

---

## 6. Could-not-verify

| Item | Reason | What's needed |
|------|--------|---------------|
| Full pytest re-run (285 tests) | No Python runtime in this review | Run `pytest -q` locally; CI run on HEAD is the recorded evidence |
| Live EBS instance validation of pack table/column names | No EBS available | ITM-012 (scheduled); review-before-run disclaimer preserved |
| `POST /v1/execute` + `/v1/nl2sql` with `APP_API_KEY` auth test | Not in current test suite | Add parametrized auth tests on execute/nl2sql at `/v1` (F2 recommendation) |
| Context-size behaviour when all 5 modules selected + large schema | Requires live LLM provider | The combined context (~24k chars ≈ 6k tokens) is within modern LLM windows; no hard limit in code |

---

## 7. Summary

Phase 7 is clean across all seven specified invariants:

- **B1 (`ebs_packs.py`):** 5 curated packs, static metadata, no row data,
  all pass the `assert_no_values` tripwire in isolation and combined.
- **B2 (`nl2sql.py`):** EBS context is external-only, opt-in, appended before
  the tripwire so the combined payload is verified as a whole; local path is
  completely unaffected.
- **B3 (UI):** EBS packs browser in Data Dictionary + module multiselect in
  Query Builder; both read from the same static `_PACKS`; no DB calls.
- **B4 (`/packs` API):** Read-only; no DB; 404 carries `error_id`; no
  secret-shaped fields.
- **B5 (`/v1` prefix):** All routes on `APIRouter`, mounted twice; app-level
  `require_api_key` and exception handlers apply to both mounts; only
  `/health` and `/v1/health` exempt; execute chokepoint active on `/v1/execute`.
- **B6 (23ai deferral):** No code; ADR-016 documents the decision;
  ITM-018 remains open. Out of scope for this review.
- **B7 (doc sweep):** No product code changes.

Two S4 observations noted (unknown-module silent ignore; missing `/v1/execute`
auth test). Neither blocks closure.
