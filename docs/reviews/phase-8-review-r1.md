# Phase 8 (v2) — Independent Adversarial Review · r1

> **Reviewer:** Independent AI instance (fresh context, no author session) ·
> **Date:** 2026-06-13 · **Scope:** `640bd92..HEAD` (B1–B5) ·
> **Branch:** `v2` (local-only; not pushed) ·
> **Suite:** `pytest -q` → **365 passed** (Python 3.13.2, all SMTP mocked) ·
> **Mailer tests:** 58/58 passed.

---

## 1. Verdict

**`PASS-WITH-FIXES`** — all eight invariants hold in their security-relevant
sense. Two S3 findings require fixes before GA deployment: (P8-R1-F1) the
attachment size cap is enforced on raw bytes, causing confusing SMTP-level
rejections at the default 20 MB ceiling because Gmail's 25 MB limit applies
to the base64-encoded message (~26.7 MB encoded); (P8-R1-F2) `validate_address`
does not reject all ASCII control chars — `\x01`–`\x08`, `\x0e`–`\x1e`, `\x7f`
pass both regex guards and produce malformed `To` headers. Neither finding
enables an actual email to be sent that shouldn't be, or exposes any
credentials or row data. Two S4 findings (spec/code mismatch on subject
rejection vs sanitization; unvalidated `EMAIL_FROM` sender field) are noted for
completeness but do not gate closure.

---

## 2. Findings table

| ID | Sev | Category | Location | Description | Reproduction | Recommended fix |
|----|-----|----------|----------|-------------|--------------|-----------------|
| P8-R1-F1 | **S3** | Size cap / UX | `src/core/mailer/config.py:18` · `.env.example:75` · `render.yaml` (`EMAIL_MAX_ATTACHMENT_MB: "20"`) | The size cap is enforced on **raw bytes** (`len(data)` before MIME encoding). A 20 MB raw attachment becomes ≈26.7 MB after base64 encoding, exceeding Gmail's 25 MB per-message limit. A user with a 20 MB report gets `GENERIC_EMAIL_DETAIL` from a SMTP-level rejection instead of a clean pre-send `EmailRejected`. No credential or data leak; the email is not delivered. | Build a 20 MB DataFrame (e.g. `pd.DataFrame({"v": range(300_000)})`), call `send_report_email` with a mocked SMTP that passes transport but check that real Gmail raises `smtplib.SMTPDataError: 552 5.3.4 Message size exceeds …`. Alternatively: `len(build_message(..., df=big_df, ...).as_bytes()) > 25*1024*1024` confirms the overflow. | Lower `DEFAULT_MAX_ATTACHMENT_MB` from 20 to **17** (17 MB raw × 1.33 base64 ≈ 22.6 MB encoded + headers stays under 25 MB). Update `.env.example` comment and `render.yaml` default. Add a unit test asserting that a 17.5 MB raw attachment triggers `EmailRejected` at 17 MB cap and that a 17 MB attachment passes. |
| P8-R1-F2 | **S3** | Input validation (address) | `src/core/mailer/message.py:27-28` | `_CONTROL_RE = re.compile(r"[\r\n\t\x00]")` checks only four chars. ASCII control chars `\x01`–`\x08`, `\x0e`–`\x1e`, and `\x7f` are not in `_CONTROL_RE` and are also not excluded by `_ADDR_RE`'s `[^\s@]+` (Python `\s` covers only `\x09\x0a\x0b\x0c\x0d\x20`). `validate_address("a@b.com\x01")` returns the address without raising; Python's `EmailMessage` accepts the header silently; the SMTP relay rejects at DATA with a 5xx error, producing `GENERIC_EMAIL_DETAIL`. **Does not enable header injection** (CR/LF required for that; those are caught). | `python -c "from src.core.mailer.message import validate_address; print(validate_address('a@b.com\x01'))"` — prints `a@b.com\x01` without raising. Confirmed in probe: `\x01`, `\x07`, `\x7f` all pass. | Replace `_CONTROL_RE` with a full ASCII-control-char pattern: `re.compile(r"[\x00-\x1f\x7f]")`. This catches all 33 C0/DEL control chars, including the existing `\r\n\t\x00`. Add parametrized test cases for `\x01`, `\x07`, `\x7f`. |
| P8-R1-F3 | **S4** | Spec/code mismatch | `src/core/mailer/message.py:89-91` (docstring/invariant 4 claim) | Invariant 4 states "any address **or subject** carrying CR/LF/control chars is **rejected** (`EmailRejected`)." `sanitize_subject` does **not** reject — it collapses control chars to spaces and lets the email through with a modified subject. The implementation is header-injection-safe (sanitization is sufficient since EmailMessage folds headers), but the invariant description is factually incorrect. A subject `"Hi\r\nBcc: evil@x.com"` becomes `"Hi  Bcc: evil@x.com"` (spaces) and the message is sent, not rejected. | `from src.core.mailer.message import sanitize_subject; sanitize_subject("Hi\r\nBcc: evil@x.com")` — returns `"Hi  Bcc: evil@x.com"` (no raise). | Either (a) update the review-package/invariant text to say subjects are *sanitized, not rejected*; or (b) change `sanitize_subject` to raise `EmailRejected` when any control char is detected (consistent with address behavior). Option (b) is the safer, more consistent contract. |
| P8-R1-F4 | **S4** | Input validation (sender) | `src/core/mailer/message.py:141` · `src/core/mailer/sender.py:75` | `cfg.sender` (from `EMAIL_FROM` env var) is set directly as `msg["From"]` without control-char or format validation. Operator-controlled, so trust boundary is acceptable. A misconfigured `EMAIL_FROM` with `\r\n` would produce a malformed header; Python's `email.headerregistry` may or may not sanitize it. | Set `EMAIL_FROM="From: spoofed\r\nBcc: x@y.com"` in env, call `load_config()`, inspect `cfg.sender`. | Add a `validate_sender` call in `build_message` that strips/rejects control chars from the sender string. Consistent with the defense-in-depth posture applied to all user-supplied fields. |

---

## 3. Blocking items

| ID | Status |
|----|--------|
| P8-R1-F1 | **Open** — must fix before GA (confusing UX at default 20 MB; fix is mechanical) |
| P8-R1-F2 | **Open** — should fix before GA (complete the control-char contract; fix is a one-line regex change + tests) |
| P8-R1-F3 | S4 — does not block |
| P8-R1-F4 | S4 — does not block |

---

## 4. Adversarial attack results

### 4.1 Invariant 1 — SELECT-only chokepoint untouched

**Attack:** `git diff 640bd92..HEAD -- src/db.py src/core/sql_safety.py`

**Result: PASS.** Output is empty. Neither file has a single changed line across
all six Phase 8 commits. The attachment is built from `st.session_state.last_results`
(an already-fetched DataFrame) via `dataframe_to_csv_bytes` / `dataframe_to_excel_bytes`.
No new SQL path exists.

---

### 4.2 Invariant 2 — No LLM on the email path

**Attack:** grep all `src/core/mailer/*.py` for any import of or reference to
`llm`, `openai`, `groq`, `anthropic`, `nl2sql`, `prompt`, `completion`.

**Result: PASS.** Zero LLM imports in the entire `mailer/` package. The only
mention of `llm` is in `recipients.py:5` — a comment that the `_EMAIL_RE` pattern
shape comes from `core/llm/pii.py`, but no import follows. The email body is
`st.text_area` user input only. `assert_no_values` (schema-redaction tripwire) is
never called on this path because no prompt is constructed.

---

### 4.3 Invariant 3 — Credential secrecy (RISK-21)

**Attack A — force a transport/auth failure and inspect the return value:**

`test_send_transport_failure_is_sanitized` (`test_mailer_sender.py:73`) mocks
`server.send_message.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 bad creds")`.

Confirmed: `result.message == GENERIC_EMAIL_DETAIL`; `"5.7.8"` not in message;
`_SECRET ("SUPER-SECRET-APP-PW")` not in message; `result.error_id` set.
`emails_failed` incremented. Audit `.warning` called once with no secret in
`repr(call_args)`. Test **passed**.

**Attack B — inspect `SendResult` fields:**

`SendResult` is a frozen dataclass with fields `{kind, message, error_id,
recipients, attachment_bytes}`. No password field. The password is never
assigned to any local variable outside `cfg.password` and the `smtplib.login`
call. `log_error` in `errors.py` records `str(exc)` and `type(exc).__name__`;
for `SMTPAuthenticationError` the standard `str()` is `"(535, b'5.7.8 …')"` —
no password echoed.

**Minor observation (not a finding):** If a rogue SMTP server deliberately
echoes the password in its error banner, `str(exc)` would capture it in the
server log. This is theoretically possible but outside the code's control;
`smtplib` does not include the password in its exception messages.

**Result: PASS.**

---

### 4.4 Invariant 4 — Header-injection-safe (RISK-21 / P8-R3)

**Attack A — CR/LF in recipient address:**

`validate_address("a@b.com\r\nBcc: evil@x.com")` → raises `EmailRejected`
(caught by `_CONTROL_RE`). Test `test_validate_address_rejects_header_injection`
covers `\r\n`, `\n`, and `\t` payloads. All **passed**.

**Attack B — CR/LF in subject:**

`sanitize_subject("Hello\r\nBcc: x@y.com" + " z" * 300)` → returns
`"Hello  Bcc: x@y.com …"` (control chars replaced with spaces, length capped at
200). Test `test_sanitize_subject_strips_control_and_caps` **passed**. No
injection; header is safe. However see **F3** — this is sanitize, not reject.

**Attack C — non-CRLF control char in address (partial failure → F2):**

`validate_address("a@b.com\x01")` → **does not raise**. Confirmed via live
probe: `\x01`, `\x07`, `\x7f` all pass `_CONTROL_RE` and `_ADDR_RE`. Python's
`EmailMessage` accepts the header. The SMTP relay would reject at DATA. Not a
header injection vector (CR/LF required), but a contract violation. See **F2**.

**Result: PASS** on traditional header injection; **F2** raised for incomplete
control-char coverage.

---

### 4.5 Invariant 5 — User-initiated, never auto-sent

**Attack — page-load / rerun inspection:**

`_render_email_action` is called at the tail of `draw_query_builder` and
`draw_reports`. It returns immediately when `df is None` or `not email_enabled()`.
The send fires only inside `if st.button("Send email", ..., key="email_send"):`,
which Streamlit evaluates to `False` on every rerun unless the button was
physically clicked in that render cycle. There is no `st.session_state`
auto-trigger, no timer, and no callback that invokes `send_report_email` outside
of that branch. The expander is `expanded=False` by default.

**Result: PASS.**

---

### 4.6 Invariant 6 — Egress controls (RISK-20)

**Attack A — allow-list bypass:**

`test_reject_disallowed_domain` sets `allowed_domains=frozenset({"corp.io"})` and
sends to `x@gmail.com`. `enforce_allowlist` raises `EmailRejected` before
`build_message`; `mock_smtp.assert_not_called()` **passed**. The allowlist check
covers `to_list + cc_list` together (both headers, not To only).

**Attack B — oversize:**

`test_reject_oversize_attachment` (200-byte cap on a 50 K-row DataFrame). SMTP
not called; `"limit"` in `result.message`. **Passed**. (See F1 for the default
cap mismatch with Gmail's encoded limit.)

**Attack C — audit field inspection:**

`audit_fields` in `sender.py:130-137`:
```python
{
    "to": to_list,            # validated address strings
    "cc": cc_list,            # validated address strings
    "subject": msg["Subject"],  # sanitized string
    "attachment_format": fmt,  # "csv" or "excel"
    "row_count": int(len(df)), # integer
    "attachment_bytes": size,  # integer
}
```
No body text, no row data, no `df` contents, no password, no raw SQL. The
`test_send_success_starttls_path` assertion `"see attached" not in logged` (body
content) and `_SECRET not in logged` (password) both **passed**.

**Result: PASS.**

---

### 4.7 Invariant 7 — Attachment correctness

**Attack — verify round-trip fidelity and MIME types:**

`test_build_message_csv` confirms: `atts[0].get_payload(decode=True) == dataframe_to_csv_bytes(DF)` (byte-exact match reusing the existing export helper). `test_build_message_excel` confirms: payload `[:2] == b"PK"` (ZIP magic bytes; xlsx is a zip), MIME type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. `test_build_message_custom_filename_gets_extension` confirms extension is appended when missing. All **passed**.

Format selection: `attachment_format="excel" if fmt == "Excel" else "csv"` in the
UI correctly maps the `st.radio` output. `normalize_format` also accepts `"xlsx"` /
`"xls"` aliases and coerces them to `"excel"`.

**Result: PASS.**

---

### 4.8 Invariant 8 — No regression to standing invariants

**Chokepoint:** db.py / sql_safety.py diff is empty (confirmed, Invariant 1).

**Phase-6 error sanitization:** `GENERIC_EMAIL_DETAIL` reuses `new_error_id()` /
`log_error()` from `src/core/errors.py` — the same pattern as `GENERIC_DB_DETAIL`.
No raw exception detail reaches the caller.

**Phase-6.5 edge posture:** The mailer has no new network-facing endpoint; it is
UI-only (Streamlit). API (`src/api.py`) is not touched by Phase 8 (confirmed: not
in the Phase 8 diff).

**Redaction guarantee:** `assert_no_values` is not invoked anywhere on the email
path. The body is a plain string from `st.text_area` — the LLM is never consulted.

**Secrets via env:** `SMTP_PASSWORD` lives only in `cfg.password` and is passed
only to `smtplib.login`. It is not returned, logged, or embedded in any response.

**Full suite:** 365 passed, 1 warning (pre-existing `python-multipart` deprecation
in Starlette, unrelated to Phase 8). No regressions.

**Result: PASS.**

---

## 5. QA results

| Check | Result |
|-------|--------|
| `pytest -q` (full suite, Python 3.13.2) | **365 passed, 0 failed, 1 warning** |
| Mailer sub-suite (58 tests) | **58/58 passed** |
| `git diff 640bd92..HEAD -- src/db.py src/core/sql_safety.py` | **Empty (clean)** |
| `grep -r "llm\|openai\|groq\|anthropic" src/core/mailer/` (imports only) | **Zero hits** |
| `validate_address` rejects `a@b.com\r\nBcc: evil@x.com` | **Raises EmailRejected** ✓ |
| `validate_address` rejects `a@b.com\x01` | **Does NOT raise** ✗ → F2 |
| `SendResult` fields contain no password | **Confirmed** ✓ |
| Audit log fields contain no body/row data/password | **Confirmed** ✓ |
| `mock_smtp.assert_not_called()` after domain reject / oversize | **Passed** ✓ |
| 20 MB raw attachment → encoded size vs Gmail 25 MB limit | **26.7 MB encoded > 25 MB** ✗ → F1 |

---

## 6. Could-not-verify

- **Streamlit UI** (`_render_email_action`, `_append_recipient`): no Streamlit
  runtime in test suite. Verified by `py_compile` + code read. Button-trigger
  logic is correct by inspection (Streamlit's `st.button` returns `False` on
  non-click reruns). Quick-pick button key `f"qp_{addr}"` is fine for Streamlit.
- **Live Gmail send**: not re-run by this reviewer (requires SMTP credentials).
  The author's live-send log during smoke (`scripts/p8_email_smoke.py`) was
  verified in build and accepted per the review package. The reviewer notes that
  the live send used an attachment well below the 20 MB cap, so F1 was not
  triggered during smoke.
- **`EMAIL_FROM` with display-name format** (`"Reports <reports@example.com>"`):
  `load_config()` stores it verbatim; `build_message` sets it as `msg["From"]`
  directly. Python's `email.headerregistry` handles display-name encoding. Not
  a regression relative to the prior codebase (this field is operator-controlled).
