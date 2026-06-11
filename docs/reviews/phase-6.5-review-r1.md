# Phase 6.5 — Independent Adversarial Review R1

> **Reviewer:** Independent agent (fresh context, not the commit author) ·
> **Date:** 2026-06-11 · **Range:** `2ba0a56..d34658c` (9 commits, 31 files,
> +1574/−118) · **Suite:** 236 tests, Python 3.13

---

## 1. Verdict

**PASS-WITH-FIXES**

No S1 or S2 findings. Two S3 findings (defense gap + resource leak) and two S4
findings (operator footguns). Nothing blocks phase closure under the default
S1/S2 threshold, but the S3 SSRF defense gap should be fixed before any
networked deployment.

---

## 2. Findings table

| ID | Sev | Category | Location (file:line) | Description | Reproduction / exact input | Recommended fix |
|----|-----|----------|----------------------|-------------|---------------------------|-----------------|
| R1 | **S3** | SSRF first-line defense gap | `src/core/llm/providers.py:52-100` (`_numeric_host_to_ipv4` + `validate_base_url`) | Unicode fullwidth-digit hostnames (e.g. `１２７.0.0.1` = U+FF11 U+FF12 U+FF17) pass `validate_base_url` without rejection. `_numeric_host_to_ipv4` guards `g[0] in string.digits` (ASCII `0-9` only), so `"１"` fails the digit check → returns `None` → treated as hostname. `ipaddress.ip_address("１２７.0.0.1")` raises `ValueError` → the `except ValueError: return` branch fires → the URL is **allowed**. Python's IDNA codec maps `"１２７".encode("idna") → b"127"`, and httpx currently rejects the URL as "Invalid IDNA hostname", so no live SSRF is possible with the present stack. However, `validate_base_url`'s own stated invariant ("reject in **every** encoding") is violated; the defense relies on a downstream layer (httpx) rather than the intended first-line guard. | `ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url="https://１２７.0.0.1/v1"))` — **no LLMError raised** (verified on Python 3.13 + httpx). Compare: `"https://127.0.0.1/v1"` correctly raises. | In `validate_base_url`, after computing `host`, add: `try: host.encode("ascii") except UnicodeEncodeError: raise LLMError("Custom LLM base_url host is not allowed.")` — this closes the gap before any numeric/IP check runs, making defense explicit and layer-independent. |
| R2 | S3 | File descriptor leak (error path) | `src/core/fileio.py:36-44` (`atomic_write_json`) | If `os.fdopen(fd, "w", encoding="utf-8")` raises after `tempfile.mkstemp` succeeds, the raw file descriptor `fd` is never closed. The `except BaseException` block calls `os.unlink(tmp_path)` but has no reference to `fd`. On Windows, the open fd also prevents the `os.unlink` from succeeding, leaving a temp file behind. In practice `os.fdopen` almost never fails given a fresh `mkstemp` fd, so this is theoretical. | Force `os.fdopen` to fail by monkey-patching it to raise `OSError`; verify `fd` is leaked by checking `/proc/<pid>/fd`. | Add explicit `os.close(fd)` in the exception handler before `os.unlink`: `except BaseException: os.close(fd); try: os.unlink(tmp_path) except OSError: pass; raise`. |
| R3 | S4 | Operator footgun — whitespace ALLOWED_ORIGINS | `src/api.py:82-84` (`_cors_config`) | `ALLOWED_ORIGINS` set to whitespace-only (e.g. `"   "`) is truthy, so the default-localhost fallback is skipped. After `split(",")` + strip + filter, origins becomes `[]`. The middleware receives `allow_origins=[], allow_credentials=True` — every CORS request is silently denied rather than falling back to `["http://localhost:8501","http://localhost:3000"]`. No security bypass (more restrictive), but the behaviour is surprising and not documented. | `ALLOWED_ORIGINS="   " _cors_config()` → `([], True)`. | Change the falsy check to `raw = raw.strip()` before the `or` default: `raw = (os.environ.get("ALLOWED_ORIGINS") or "").strip() or "http://localhost:8501,http://localhost:3000"`. |
| R4 | S4 | Config asymmetry (undocumented) | `src/api.py:87-94` | `APP_API_KEY` (auth) is re-read from `os.environ` on **every request** (supports live key rotation without restart). `ALLOWED_ORIGINS` (CORS) is evaluated once at **module import** and baked into the middleware. An operator who rotates allowed origins without restarting the process will see stale CORS behaviour with no error. The asymmetry is not documented in D7. | Observation — no code repro. | Document in `docs/07-deployment-plan.md`: "CORS origins (`ALLOWED_ORIGINS`) require a process restart to take effect; the API key (`APP_API_KEY`) does not." |

---

## 3. Blocking items

**None.** No open S1 or S2 findings. R1 (S3) is strongly recommended before networked deployment but does not block phase closure under the default gate rules.

---

## 4. QA results

### 4.1 Automated suite

```
236 passed, 0 failed, 1 warning  (Python 3.13, 18.69 s)
```

All new suites green: `test_auth.py` (16), `test_llm_providers.py` (encoding
matrix +17), `test_fileio.py` (7), `test_store_robustness.py` (6),
`test_error_handling.py` (+5 ITM-017). No regressions in the prior 185.

### 4.2 Adversarial cases executed

#### Invariant 1 — Chokepoint untouched

```
git diff 2ba0a56..d34658c -- src/db.py src/core/sql_safety.py
```
Output: **empty** — zero changes. ✓  
`src/db.py` has exactly one `oracledb.connect` (line 113) and one `cur.execute`
(line 141). ✓

#### Invariant 2 — Auth default-off

- `APP_API_KEY` unset: `GET /metrics`, `GET /profiles`, `GET /reports` all
  return 200 without a key (identical to Phase 6 posture). ✓
- `APP_API_KEY=""` (empty string): `os.environ.get(...) or ""` → falsy → auth
  disabled. Correct. ✓
- `APP_API_KEY="   "` (whitespace): `"   " or ""` → truthy → auth enforced with
  `"   "` as the expected key. Correct (weak key but operator's choice). ✓

#### Invariant 3 — Auth enabled, bypass attempts

All checked with `APP_API_KEY=test-api-key-123`:

| Path / trick | Result | Expected |
|---|---|---|
| `GET /health` (no key) | 200 | 200 ✓ |
| `GET /health/` (trailing slash) | 401 (not in EXEMPT_PATHS) | 401 ✓ |
| `GET //health` (double slash) | 401 (not in EXEMPT_PATHS) | 401 ✓ |
| `GET /HEALTH` (upper case) | 404 or 401 (not exempt) | 401/404 ✓ |
| `GET /metrics` (no key) | 401 | 401 ✓ |
| `GET /metrics` (wrong key) | 401 | 401 ✓ |
| `GET /metrics` (correct key) | 200 | 200 ✓ |
| `OPTIONS /profiles` (CORS preflight, allowed origin) | 200 (CORSMiddleware fires before dependency) | 200 ✓ |
| 401 body | `{"detail":"Not authenticated.","error_id":"<uuid>"}` | uniform envelope ✓ |
| Key material in logs | absent (verified by `test_auth_failure_never_logs_key_material`) | absent ✓ |

`EXEMPT_PATHS = frozenset({"/health"})` — exact string match; path tricks don't
bypass it. CORS OPTIONS preflights are answered by the middleware layer before
`require_api_key` runs.

#### Invariant 4 — CORS wildcard+credentials

| Input | origins | allow_credentials | Safe? |
|---|---|---|---|
| unset | `["http://localhost:8501","http://localhost:3000"]` | True | ✓ |
| `"*"` | `["*"]` | False | ✓ |
| `"*, https://x"` | `["*","https://x"]` | False (`"*" in origins`) | ✓ |
| `" https://a , https://b "` | `["https://a","https://b"]` | True | ✓ |
| `","` | `[]` | True | S4 operator footgun (R3 above) |
| `"   "` | `[]` | True | S4 operator footgun (R3 above) |

`*`+credentials combo is unrepresentable through any value. ✓

#### Invariant 5 — SSRF encoding matrix

All from the test suite pass. Additionally tested manually:

| Input | Outcome |
|---|---|
| `"127.0.0.1"` | Rejected (loopback) ✓ |
| `"2130706433"` (decimal int) | Rejected (loopback) ✓ |
| `"0x7f000001"` (hex int) | Rejected (loopback) ✓ |
| `"0177.0.0.1"` (dotted octal) | Rejected (loopback) ✓ |
| `"127.1"` (2-group) | Rejected (loopback) ✓ |
| `"1_0.0.0.1"` (underscore) | Rejected (malformed numeric group) ✓ |
| `"1password.com"` | Passed (hostname, non-numeric label) ✓ |
| `"4294967296"` (>2³²) | Rejected (out of range) ✓ |
| `"09.0.0.1"` (invalid octal) | Rejected (malformed) ✓ |
| **`"１２７.0.0.1"` (Unicode fullwidth)** | **Passed — bypass (R1, S3)** |

Unicode fullwidth digit variant passes `validate_base_url`. Currently blocked by
httpx at the HTTP-client layer ("Invalid IDNA hostname"), but the first-line
defence is incomplete for this encoding class.

#### Invariant 6 — Atomic writes

Grep confirms zero surviving `open(..., "w") + json.dump` patterns in store
files — only `atomic_write_json` calls in `profiles.py`, `reports.py`,
`schema_store.py`, `storage.py`. The `fileio.py` instance is the implementation
itself (correct). ✓

Torn-write test (`test_failed_write_leaves_old_content_intact`): unserializable
payload raises `TypeError`, target file retains old content, no temp files left.
✓

#### Invariant 7 — Quarantine semantics

Manually crafted cases beyond the test suite:

1. **Dict with `id`/`name` but invalid field** — quarantined, not served, preserved
   verbatim on subsequent saves. ✓
2. **Non-dict record (e.g. `"junk string"`)** — legacy path attempts
   `rec.get("sql", "")` which raises `AttributeError` (a `TypeError` subclass);
   quarantined. ✓
3. **Create → corrupt → list → create again** — quarantine key survives the second
   save via `setdefault`. ✓
4. **Log-once across repeated loads** — confirmed by
   `test_corrupt_record_logged_once_per_instance`. ✓
5. **Migration save with corrupt record** — corrupt record preserved through in-place
   migration rewrite (`test_corrupt_legacy_report_is_quarantined_and_survives_migration`). ✓

Quarantine log records: contain record key + exception type only — no record
body, no SQL, no credentials. ✓

#### Invariant 8 — ITM-017 error classification

| Scenario | Response body | Server log |
|---|---|---|
| `generate_sql_from_nl` raises `ValueError("Schema is empty…")` | verbatim text | logged via normal request record |
| `generate_sql_from_nl` raises `LLMError("External LLM call failed…")` | verbatim text | — |
| `generate_sql_from_nl` raises `RuntimeError("host=dbhost.internal …")` | `"Could not generate SQL — see server logs."` + `error_id` | full text keyed by same `error_id` |
| `SecretConfigError` in profiles API | verbatim guidance + `error_id` | breadcrumb keyed by same `error_id` |
| UI `SecretConfigError` (4 arms) | `f"{e} (ref: {error_id})"` | full exc logged |

No infrastructure detail (host, DSN, key text) leaks in body or headers on any
unexpected exception path. ✓

#### Invariant 9 — Standing invariants unregressed

- `assert_safe_select` tests all pass (existing 185 include SQL safety matrix). ✓
- Bind validation tests pass; no new `cur.execute` calls outside `db.py`. ✓
- `audit.audit_execution` still receives SQL hash/metadata only. ✓
- Profile passwords never appear in `ProfilePublic` or API responses. ✓
- `sanitize_correlation_id` strips CR/LF/space/colon; length-capped at 128. ✓
- `APP_SECRET_KEY` missing: `SecretConfigError` raised, handled by ITM-017
  arms — no stack trace to client, no key in response. ✓

---

## 5. Could-not-verify

| Item | Reason |
|---|---|
| Live Oracle DB execution | RISK-04 — pre-GA standing; no Oracle instance in test environment. SQL safety, bind, and limit logic verified by mock and by code inspection only. |
| Multi-worker / cross-process concurrency | Charter out-of-scope (one worker per store directory constraint). Only crash-durability (atomic writes) tested. |
| Windows `os.replace` atomicity across a genuine crash mid-write | `test_failed_write_leaves_old_content_intact` simulates via failing serializer, not a real kill-mid-write. Atomicity guarantee rests on OS `os.replace` semantics — accepted per the charter. |
| Python 3.11 compatibility | Only Python 3.13 available locally; the CI matrix adds 3.11 on push. The review package notes this is intentional (push to demonstrate, not assert). |
| httpx version dependency for R1 mitigation | The Unicode-digit SSRF is blocked by httpx's "Invalid IDNA hostname" validation. This was verified against the installed httpx version; future upgrades or library changes are not tracked here. |

---

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| R1 | 2026-06-11 | Independent reviewer | Initial adversarial review and QA. |
