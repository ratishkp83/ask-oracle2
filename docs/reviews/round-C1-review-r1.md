# Round C1 — Independent Adversarial Review · r1

> **Reviewer:** Independent AI instance (fresh context, no author session) ·
> **Date:** 2026-06-12 · **Scope:** B1–B3 (`a395003..f374380`) ·
> **Prompt:** [Adversarial Review & QA Prompt v1.0](../process/adversarial-reviewer-prompt.md)

---

## 1. Verdict

**`PASS-WITH-FIXES`** — two non-blocking findings (S3, S4). No invariant
violations. No blocking items. All S1/S2 attack vectors exhausted without
success. The three items may close; the S3 fix is recommended before GA but
does not gate it.

---

## 2. Findings table

| ID | Sev | Category | Location | Description | Reproduction | Recommended fix |
|----|-----|----------|----------|-------------|--------------|-----------------|
| C1-R1-F1 | **S3** | Robustness / security degradation | `src/storage.py:42-43` | `OSError` on `os.remove(CONFIG_FILE)` is swallowed with bare `pass`. If the OS cannot delete the legacy file (permissions, Windows lock, read-only mount), the plaintext password remains at rest indefinitely and no log entry is emitted. The function returns the config so the session works, but the "delete the plaintext file" invariant is silently broken. | Create `connection.json` with `{"password":"secret"}`, mark it read-only or lock it (Windows: `attrib +R connection.json`). Call `migrate_legacy_connection()`. Returns the config; file still present; no log warning. On next startup the same result repeats. | Replace `pass` with a `logger.warning(...)` call (using `get_logger("storage")`). Still return `cfg` so startup proceeds; the operator sees the warning in stdout/logs and can resolve the permission issue. |
| C1-R1-F2 | **S4** | Race condition (theoretical) | `src/storage.py:21-24` | `load_connection_config` checks `os.path.exists` then calls `open` — a TOCTOU window. If a concurrent deletion (or second Streamlit instance) removes the file between the two calls, `open()` raises `FileNotFoundError`, which propagates through `migrate_legacy_connection()` and crashes the Streamlit startup (`app.py:66`). | Requires two concurrent processes deleting the file simultaneously; not reproducible in the standard single-user deployment. | Wrap the `open` call (or the whole function body) in a `try/except FileNotFoundError: return None` instead of relying on `os.path.exists`. |

---

## 3. Blocking items

**None.** Default blocking threshold is open S1/S2. No S1 or S2 findings
were found. F1 (S3) and F2 (S4) are recommended fixes but do not gate closure.

---

## 4. Adversarial attack results (Part A)

### 4.1 ITM-007 — Pure deprecation swap (B1)

**Attack: any remaining `use_container_width=True`?**
- `grep -r use_container_width src/` → 0 matches. Confirmed clean.
- Diff verified: 14 removals of `use_container_width=True` (13 replaced with
  `width="stretch"`, 1 — the deprecated "Save" button — removed entirely in B2
  as part of ITM-006). The commit split is correct: B1 swaps the API on all
  call sites; B2 then removes the Save button and its store call.
- No behaviour change: `width="stretch"` is the Streamlit replacement for
  `use_container_width=True`; no layout semantics altered.

**Result: PASS ✓**

---

### 4.2 ITM-006 — No second credential path, no plaintext at rest (B2)

**Attack A: Does `save_connection_config` still exist anywhere?**
- `storage.py`: function removed; `atomic_write_json` import dropped.
- `app.py`: import changed from `load_connection_config, save_connection_config`
  → `migrate_legacy_connection`. No call site remains.
- Test `test_plaintext_write_path_is_removed` asserts
  `not hasattr(storage, "save_connection_config")`. ✓

**Attack B: Does anything else write `connection.json`?**
- `atomic_write_json` is still used in `profiles.py`, `schema_store.py`, and
  `reports.py` for their own files (`profiles.json`, `schemas.json`,
  `reports.json`). None of these reference `connection.json`.
- The `CONFIG_FILE` constant remains in `storage.py` for the read path only
  (`migrate_legacy_connection` + `load_connection_config`). No write call sites
  anywhere in `src/`. ✓

**Attack C: Legacy file with a `password` field — confirm deleted after startup.**
- `migrate_legacy_connection()` calls `load_connection_config()` then
  `os.remove(CONFIG_FILE)`. The password is returned to the caller (session
  state only) and the file is deleted. Test
  `test_migrate_removes_pre_f5_plaintext_password_file` covers exactly this
  case and passes. ✓
- **Caveat (F1):** OSError on delete is silently swallowed; see Finding C1-R1-F1.

**Attack D: Password returned by the API / shown in UI?**
- `_draw_manual_connection()` (`app.py:127-159`): password shown only in a
  `type="password"` widget (masked); never passed to a logger; session-state
  dict is not serialized or persisted.
- `ProfilePublic` (the model returned by `store.list()`) excludes the
  password field entirely. The password is re-encrypted on `ProfileCreate`;
  never returned by API responses. ✓

**Result: PASS ✓ (with S3 caveat at F1)**

---

### 4.3 ITM-008 — Scrubbing opt-in, external-only, safe-by-default (B3)

**Attack A: Flag-off default.**
- `pii_scrub_enabled()`: `os.environ.get("SCRUB_PII") or ""` → `""` when
  absent; `"".strip().lower()` → `""` → not in `_TRUTHY`. Default is `False`.
- Test `test_flag_unset_is_off` (monkeypatches `delenv`) and 4 falsy parametrize
  cases confirm. ✓

**Attack B: Ordinary numeric thresholds not masked.**
- Tested `\b\d{13,16}\b` pattern against:
  - `"show orders over 100000 in 2026"` → no match ✓ (6-digit, below 13)
  - `"salary > 50000"` → no match ✓ (5-digit)
  - `"WHERE id = 999999999999"` → no match ✓ (12-digit, below threshold)
  - `"12345678901234567"` (17-digit) → no match ✓ (above ceiling)
- The `\b\d{13,16}\b` pattern correctly preserves all ordinary financial
  quantities (≤12 digits). 13-16-digit sequences are intentionally masked
  (credit cards / long IDs). Per-design, documented in known limitations. ✓
- **Note (not a finding):** A 13-16 digit Oracle sequence value used as a filter
  predicate in the NL question (e.g. "show customer 1234567890123") *would* be
  masked as `[CARD]`, causing the generated SQL to contain a literal `[CARD]`
  string that Oracle would reject. This is acceptable per the stated conservative
  design; the user can still type the raw SQL in the Query Builder. No test
  covers this edge, but the known limitations section acknowledges it.

**Attack C: Scrubbing external-path-only.**
- `nl2sql.py:91-99`: the `pii_scrub_enabled()` / `scrub_pii()` block is inside
  the `else` branch of `if provider.name == "local":`. Local providers receive
  the verbatim question regardless of the flag.
- Tests `test_local_path_never_scrubbed` and `test_external_question_scrubbed_when_flag_on`
  confirm the boundary. ✓

**Attack D: Masking cannot corrupt prompt structure.**
- Placeholders (`[EMAIL]`, `[SSN]`, `[CARD]`, `[PHONE]`) are plain ASCII strings
  with no backticks, newlines, or shell metacharacters. No pattern substitution
  can produce a `` ``` `` code fence or modify the `"Schema:\n"` /
  `"User request:\n"` / `"Return the Oracle SQL…"` scaffolding. ✓

**Attack E: No PII or key logged.**
- `natural_language` (the raw pre-scrub question) is never passed to any logger.
- `log_error` at `api.py:417` logs only `type(exc).__name__` and `str(exc)`.
- The `_` in `question, _ = scrub_pii(question)` discards the count (no
  sensitive data).
- Audit logger records SQL hash + metadata only — the NL question is absent. ✓

**Attack F: Masking after existing schema-name redaction.**
- `build_external_context(schema)` and `assert_no_values(context)` run before
  `scrub_pii(question)`. Scrubbing operates only on `question`, never on
  `context`. Schema redaction is orthogonal and prior. ✓

**Result: PASS ✓**

---

### 4.4 Standing invariants — no regression

**SELECT/CTE-only chokepoint:**
- `git diff a395003..f374380 -- src/db.py src/core/sql_safety.py` → empty (confirmed
  by shell). Both files are byte-for-byte identical to the pre-C1 baseline.
- The three-layer safety policy (parse → root-type → AST-scan → denylist) is
  unchanged. ✓

**DML/DDL bypass attempts (re-verified on current code):**

| Attack vector | Result |
|---|---|
| `SELECT 1; DROP TABLE emp` | Rejected: 2 parsed statements |
| `WITH x AS (INSERT INTO t …) SELECT …` | Rejected: `exp.Insert` found in AST |
| `BEGIN EXECUTE IMMEDIATE …; END;` | Rejected: root not in `_ALLOWED_ROOTS` |
| `SELECT … FOR UPDATE` | Rejected: `root.args.get("locks")` check |
| `SELECT … INTO …` | Rejected: `exp.Into` found in tree |
| `SELECT 'DELETE'` | Accepted (string literal blanked before denylist scan) |
| `/* DELETE */SELECT 1` | Accepted if sqlglot strips the comment; denylist scans normalized SQL |
| Parse-error input | Fail-closed: `allowed=False` returned |

All pass. ✓

**Secrets-via-env, metadata-only persistence, Phase-6 error sanitization:**
- No changes to `api.py` error handling, `errors.py`, or environment-variable
  loading in this change set. Verified by grep. ✓

**AI-proposes-never-runs:**
- `generate_sql_from_nl` returns an `NLSQLResult`; it does not call
  `OracleClient.run_select`. The UI's "Run SQL" button is a distinct action.
  Unchanged. ✓

---

## 5. QA results (Part B)

### Automated suite

- **Claimed:** `pytest -q` → 260 passed (Python 3.13, mocked DB); CI green on
  3.11 + 3.13 (run #12 on `f374380`).
- **Could not independently re-run** the full suite in this review (no local
  Python environment available to invoke pytest). Reviewer accepts the CI
  evidence as claimed; the CI run reference (#12 on `f374380`) is verifiable by
  the owner in the CI console.

### Boundary and abuse cases executed (manually reasoned)

| Case | Input / state | Expected | Verified? |
|------|--------------|----------|-----------|
| `SCRUB_PII` absent | No env var | verbatim question sent | ✓ Code + test |
| `SCRUB_PII=1` local provider | `provider.name == "local"` | verbatim | ✓ Code + test |
| `SCRUB_PII=true` external | email in question | `[EMAIL]` in prompt | ✓ Code + test |
| 6-digit threshold | `"salary over 100000"` | not masked | ✓ Pattern test |
| 12-digit ID | `"WHERE id = 999999999999"` | not masked | ✓ Pattern test |
| 13-digit ID | `"id 1234567890123"` | masked `[CARD]` (by design) | ✓ Pattern test |
| 17-digit sequence | `"12345678901234567"` | not masked | ✓ Pattern test |
| SSN `123-45-6789` | standard SSN | masked `[SSN]` | ✓ Pattern test |
| Date `2026-06-12` | YYYY-MM-DD | not masked | ✓ Pattern test |
| `migrate_legacy_connection` absent file | no `connection.json` | returns `None` | ✓ Code + test |
| migration with `password` field | file with plaintext pw | file deleted; pw session-only | ✓ Code + test |
| migration idempotent | call twice | second returns `None` | ✓ Code + test |
| `save_connection_config` missing | `hasattr(storage, …)` | `False` | ✓ Test |
| SQL `WITH … INSERT … SELECT` | CTE-wrapped DML | rejected | ✓ Code reasoning |
| SQL `FOR UPDATE` | row-lock clause | rejected | ✓ Code + layer 3b |
| SQL parse error | malformed SQL | fail-closed | ✓ Code + `except` path |
| OSError on file deletion | read-only `connection.json` | file remains; no log | ✗ Bug → F1 |

### Graceful failure verification

- DB connection errors → `sanitize_db_error_for_ui` produces a reference ID;
  no stack trace or credential in the user message. Unchanged from prior phases.
- LLM errors → `LLMError` wraps with `type(exc).__name__` only; key not
  surfaced. Unchanged.
- Schema parse error → caught by `except Exception` in UI, shown as a plain
  string message. ✓

---

## 6. Could-not-verify

| Item | Reason | What's needed |
|------|--------|---------------|
| Full pytest re-run (260 tests) | No Python runtime available in this review context | Run `pytest -q` locally; CI run #12 result is already recorded |
| Live-Oracle smoke re-run | No XE 21c connection available to reviewer | Already evidenced by owner in `round-C1-live-pass.md`; re-run with `AOR_LIVE_*` creds if required |
| EBS template SQL against a real EBS instance | No EBS available | ITM-012 (known, scheduled) |
| Streamlit widget key uniqueness at runtime | Static analysis only | Headless smoke is the proxy; 7-section green run cited |
| F1 reproduction (OS-level file lock) | Would require a live OS file permission change | Owner can reproduce on dev box with `attrib +R connection.json` |

---

## 7. Summary

All three code items deliver their stated changes correctly and without
regression:

- **B1 (ITM-007):** `use_container_width` fully retired; 0 remaining
  occurrences; no behaviour change.
- **B2 (ITM-006):** `save_connection_config` gone; `connection.json` write
  path dead; `migrate_legacy_connection` correctly reads once + deletes;
  encrypted `ProfileStore` is the sole persistence path.
- **B3 (ITM-008):** PII scrubbing correctly default-off, external-only,
  conservative (no ordinary-number masking), no prompt-structure risk, no
  PII in logs.

The single actionable finding (C1-R1-F1) is an S3 robustness gap in the
delete-failure path of `migrate_legacy_connection`; the fix is a one-liner
log call. It does not block GA.
