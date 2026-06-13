# Email-a-Report Follow-up Action — Technical Design (Phase 8 / v2)

> **Document:** Design · **Version:** 1.0 · **Status:** Draft — for owner approval · **Owner:** Product/Engineering · **Last updated:** 2026-06-13
> **Charter:** [charters/phase-8-charter.md](charters/phase-8-charter.md) · **Branch:** `v2` (local commits only, no push until July)

## 1. Goal
After a report runs, let the decision-maker **email the result** — to recipient(s) they choose based on the output — with the output attached (CSV or Excel), through **Gmail** (SMTP + App Password, single shared mailbox). Must support a **real, demoable send**. No change to the SELECT-only chokepoint or the redaction posture.

## 2. Design principles (from the charter)
- **Reuse, don't rebuild:** attachments come from the existing `dataframe_to_csv_bytes` / `dataframe_to_excel_bytes` ([src/utils.py](../src/utils.py)); quick-pick reuses the email regex in [src/core/llm/pii.py](../src/core/llm/pii.py); errors/audit/metrics reuse [core/errors.py](../src/core/errors.py), [core/logging_config.py](../src/core/logging_config.py), [core/metrics.py](../src/core/metrics.py).
- **No new dependencies:** stdlib `smtplib` + `ssl` + `email.message.EmailMessage` only. (Keeps the validated dependency set frozen.)
- **Opt-in:** the feature is inert unless SMTP env is configured — the UI surface is hidden otherwise.
- **User-initiated egress, never auto-sent:** same trust boundary as the existing export.

## 3. Module layout
A new package **`src/core/mailer/`** — deliberately **named `mailer`, not `email`, to avoid shadowing Python's stdlib `email` package**.

| File | Responsibility |
|------|----------------|
| `src/core/mailer/__init__.py` | Public surface: `email_enabled`, `send_report_email`, `detect_recipient_candidates`, `SendResult`, `EmailRejected`. |
| `src/core/mailer/config.py` | `EmailConfig` dataclass + `load_config()` from env + `email_enabled()`. |
| `src/core/mailer/message.py` | Address validation + CRLF/header-injection guard, recipient parsing, allow-list enforcement, subject sanitization, `build_message()` (attaches CSV/Excel, enforces size cap). Defines `EmailRejected`. |
| `src/core/mailer/recipients.py` | `detect_recipient_candidates(df)` — smart quick-pick from result columns. |
| `src/core/mailer/sender.py` | `send_report_email(...)` — orchestrates validate → build → SMTP send → audit-log → metrics; returns a `SendResult`. |

Touch-points in existing files:
- `src/app.py` — add a "Send as email" expander in `_run_and_display` (after the download buttons, gated on `email_enabled()`), plus a small `_render_email_action(df)`.
- `src/core/errors.py` — add `GENERIC_EMAIL_DETAIL` constant (reuse `new_error_id`/`log_error`).
- `src/core/metrics.py` — add counters `emails_sent`, `emails_failed`.

## 4. Config contract (env-only)
Feature is **enabled iff `SMTP_USER` and `SMTP_PASSWORD` are both set** (`email_enabled()`).

| Var | Default | Notes |
|-----|---------|-------|
| `SMTP_HOST` | `smtp.gmail.com` | |
| `SMTP_PORT` | `587` | `587`=STARTTLS (default); `465`=implicit SSL (supported). |
| `SMTP_USER` | — (required) | The Gmail address; logs in. |
| `SMTP_PASSWORD` | — (required) | **The Gmail App Password** (16 chars; account needs 2-Step Verification). Secret — env-only, never logged or returned. |
| `EMAIL_FROM` | = `SMTP_USER` | "From" header. |
| `EMAIL_ALLOWED_DOMAINS` | empty = allow all | Comma-separated allow-list (D-F). When set, every To/CC domain must match or the send is rejected. |
| `EMAIL_MAX_ATTACHMENT_MB` | `20` | Pre-send cap (headroom under Gmail's 25 MB). |

## 5. Data flow
```
results df (st.session_state.last_results, already through the chokepoint)
      │
   UI expander: To / CC / Subject / Body / format(CSV|Excel) / quick-pick chips
      │  send_report_email(to, cc, subject, body, df, attachment_format)
      ▼
 sender.py ──► message.py: parse+validate recipients ──► EmailRejected (verbatim) on bad/blocked/oversize
      │                     build EmailMessage + attachment (utils helpers)
      ▼
 smtplib.SMTP(host,port) → starttls(ssl.create_default_context()) → login(user,pw) → send_message()
      │
      ├─ success → audit log "email_sent" (metadata only) + metrics.emails_sent → SendResult(ok)
      └─ smtplib/transport error → log_error(error_id) + metrics.emails_failed → SendResult(error, generic msg + error_id)
```

`SendResult` discriminates three outcomes so the UI renders the right thing:
- `ok` — success summary (recipients, bytes, format).
- `rejected` — **safe, verbatim** user-actionable message (bad address / disallowed domain / oversize), no SMTP call made.
- `error` — **sanitized** generic message + `error_id` (transport/auth failure; full detail server-side only).

## 6. Security design (maps to charter risks)
- **P8-R2 credential handling:** `SMTP_PASSWORD` is read from env at send time, passed only to `smtplib.login()`, **never** placed in a `SendResult`, log record, audit field, or API response. The audit log and error log carry *no* credential. Transport errors are sanitized (generic message + `error_id`), the raw exception logged server-side only — exactly the `sanitize_db_error_for_ui` pattern, via a new `GENERIC_EMAIL_DETAIL`.
- **P8-R3 header injection:** recipients and subject are validated; any `\r`/`\n`/control char ⇒ `EmailRejected`. Message is built with `EmailMessage` (the stdlib sets headers + MIME correctly); we never concatenate raw header strings.
- **P8-R1 exfiltration:** every send is **audit-logged** on the `ask_oracle.audit` channel — `event=email_sent`, fields: `request_id`, `to` (addresses), `cc`, `subject`, `attachment_format`, `row_count`, `byte_size`, `outcome`. **No row data, no body, no credential.** Optional `EMAIL_ALLOWED_DOMAINS` (D-F) hard-rejects out-of-policy recipients before any SMTP call.
- **P8-R4 oversize:** the serialized attachment is measured; over `EMAIL_MAX_ATTACHMENT_MB` ⇒ `EmailRejected` with a clear message (suggest narrowing the query) before connecting.
- **No LLM call** anywhere on this path — the redaction tripwire is untouched. AI-draft remains out of scope.
- **Chokepoint untouched:** the attachment is built from the already-fetched `df`; no new SQL execution path.

## 7. Smart quick-pick (D-D)
`detect_recipient_candidates(df, limit=50)`: scan string cells with the email regex (reuse the `pii.py` pattern), collect matches, **dedupe case-insensitively**, preserve first-seen order, cap at `limit`. Robust to non-string / NaN cells. The UI shows the candidates as one-click "add to To" buttons; free-form entry is always available alongside.

## 8. UI design (Streamlit, in `_run_and_display`)
A `st.expander("✉️ Send as email (follow-up action)", expanded=False)`, shown only when `email_enabled()`:
- **To** (text, comma-separated) + a row of quick-pick buttons for detected candidates.
- **CC** (optional, text).
- **Subject** (prefilled, e.g. `"Report results — {n} rows — {YYYY-MM-DD}"`).
- **Body** (text area; small default).
- **Attachment format** (radio: CSV / Excel).
- **Send** button → `send_report_email(...)`, then `st.success` (ok), `st.warning`/`st.error` verbatim (rejected), or `st.error("{generic} (ref: {error_id})")` (error).

## 9. Live demo (success criterion 6)
- `scripts/p8_email_smoke.py` — loads `.env` (same approach as `scripts/c1_live_smoke.py`), builds a small sample DataFrame, calls `send_report_email(to=<argv/SMOKE_EMAIL_TO>, ..., attachment_format="csv")`, prints the `SendResult`. One real email proves the path end-to-end.
- Manual: run the Streamlit UI, run any query, open the expander, Send → a real email with the attachment arrives.
- **Gated on owner-provided Gmail App Password in `.env`** (no real send in CI; CI is fully mocked).

## 10. Test plan (all SMTP mocked — no network in CI)
- `tests/test_mailer_config.py` — `email_enabled()` true/false by env; `load_config()` defaults + allow-list parsing + max-MB.
- `tests/test_mailer_message.py` — address validation (valid / invalid / CRLF-injection rejected); `parse_recipients` (multi-separator, dedupe, invalid); allow-list (empty=allow-all, allow, deny); subject CRLF-strip + length cap; `build_message` (CSV & Excel attachment present with correct MIME + filename; oversize ⇒ `EmailRejected`).
- `tests/test_mailer_recipients.py` — candidate detection across columns, case-insensitive dedupe, `limit`, non-string/NaN safety.
- `tests/test_mailer_sender.py` — `patch("smtplib.SMTP")`: asserts `starttls`/`login`/`send_message` called correctly; `SendResult.ok`; `metrics.emails_sent` incremented; `email_sent` audit record emitted with **no** password/body/row-data. Failure: SMTP raises ⇒ `SendResult.error` + `error_id` + `emails_failed`, message contains **no** credential. Rejected: bad/blocked/oversize ⇒ `SendResult.rejected`, **no** SMTP call.

Target: existing **307 + ~25 new ≈ 332** passing on 3.11 + 3.13.

## 11. Build sequence
| Build | Scope | Files |
|-------|-------|-------|
| **B1** | Mailer core (no network): config, validation/injection-guard/allow-list/size-cap/compose, quick-pick + unit tests | `core/mailer/{__init__,config,message,recipients}.py`, `tests/test_mailer_{config,message,recipients}.py` |
| **B2** | Transport: `sender.py` (SMTP send, audit log, metrics, sanitized errors) + mocked-SMTP tests; `errors.py` + `metrics.py` additions | `core/mailer/sender.py`, `core/errors.py`, `core/metrics.py`, `tests/test_mailer_sender.py` |
| **B3** | UI surface in `_run_and_display` (gated on `email_enabled()`) | `src/app.py` |
| **B4** | Live-demo enablement: smoke script + config/deploy docs | `scripts/p8_email_smoke.py`, `.env.example`, `render.yaml`, `docker-compose.yml`, `docs/07-deployment-plan.md` |
| **B5** | Governed docs: ADR-017, RISK-20/21, issue-log/traceability/CHANGELOG/HANDOFF, governance index, task-tracker | `docs/**` |
| **B6** | Independent exit-gate review (reviewer ≠ author) → remediate → PASS | `docs/reviews/phase-8-review-r*.md` |

Live send (criterion 6) runs once the owner supplies the Gmail App Password — can happen any time after B2.

## 12. New governed IDs
- **ADR-017** — Email a report via Gmail SMTP (single shared mailbox, env creds, user-approved egress, no LLM, stdlib-only).
- **RISK-20** — Email data egress (mitigations: user-initiated + reviewed, audit log, optional allow-list, opt-in).
- **RISK-21** — SMTP credential handling (mitigations: env-only, never logged/returned, sanitized transport errors).

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-13 | Product/Eng | Initial design for Phase 8 email follow-up action — `core/mailer/` package (stdlib SMTP, no new deps), config contract, security design, quick-pick, UI, live-demo smoke, test plan, build sequence B1–B6. For owner approval. |
