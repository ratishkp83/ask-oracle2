# Phase 8 (v2) — Review Package (input to the independent gate)

> **Prepared:** 2026-06-13 · For: owner-supplied independent reviewer · Gate: [external-review-gate](../process/external-review-gate.md)
> Hand the **filled Context block** below (plus this package) to the reviewer along with the [Adversarial Review & QA Prompt](../process/adversarial-reviewer-prompt.md). The reviewer (fresh context, **not** the author) writes findings to `docs/reviews/phase-8-review-r1.md`.
> **Branch note:** this is the **`v2`** branch; per the active commit freeze it is **local-only (not pushed)**, so CI has **not** run on it — the reviewer runs `pytest` locally (expect **365 passed**).

## Change set
- **Code range:** `640bd92..HEAD` (the v2 Phase-8 build). Build commits: `0abbaca` B1 (mailer core)
  · `6e72fe8` B2 (SMTP transport) · `320da37` B3 (UI) · `53a4264` B4 (smoke + config) · `3cd2e07`
  B5 (governed docs).
- **Primary new/changed code:**
  - `src/core/mailer/` (new package): `config.py` (opt-in `email_enabled`, `load_config`),
    `message.py` (`validate_address` / `parse_recipients` / `enforce_allowlist` /
    `sanitize_subject` / `build_message`, `EmailRejected`), `recipients.py`
    (`detect_recipient_candidates`), `sender.py` (`send_report_email` → `SendResult`).
  - `src/core/errors.py` — `GENERIC_EMAIL_DETAIL` constant (reuses `new_error_id` / `log_error`).
  - `src/core/metrics.py` — `emails_sent` / `emails_failed` / `emails_rejected` counters.
  - `src/app.py` — `_render_email_action` + `_append_recipient`, called from `draw_query_builder`
    and `draw_reports` (gated on `email_enabled()`, rendered from `st.session_state.last_results`).
  - `scripts/p8_email_smoke.py` (new) — real-send smoke. `.env.example` + `render.yaml` config.

## Filled Context block (paste into the adversarial prompt)
- **Phase under review:** Phase 8 (v2) — Email a Report follow-up action (Gmail SMTP).
- **Charter:** [charters/phase-8-charter.md](../charters/phase-8-charter.md) · **Design:**
  [email-followup-action-design.md](../email-followup-action-design.md) · **ADR:**
  [ADR-017](../adr/ADR-017-email-report-via-gmail-smtp.md). **Risks:** RISK-20/21.
- **Change set:** `640bd92..HEAD` (branch `v2`).
- **Invariants to attack:**
  1. **SELECT-only chokepoint untouched.** `git diff 640bd92..HEAD -- src/db.py src/core/sql_safety.py`
     must be **empty**. The attachment is built from the already-fetched result; no new SQL path.
  2. **No LLM on the email path.** Nothing in `src/core/mailer/` imports or calls the LLM/provider
     layer; the email body is **user-typed only**. The schema-redaction tripwire (`assert_no_values`)
     is not involved because no prompt is built here. **Attack:** confirm no LLM import/call in the
     mailer; confirm the body is never model-generated.
  3. **Credential secrecy (RISK-21).** `SMTP_PASSWORD` reaches **only** `smtplib.login`; it must
     never appear in a `SendResult`, an audit-log field, an error message, or any return value.
     **Attack:** force a transport/auth failure (mock `smtplib.SMTP`) → confirm the user sees only
     `GENERIC_EMAIL_DETAIL` + an `error_id` (no creds, no raw SMTP transcript); confirm the audit
     record and the `SendResult` contain no password.
  4. **Header-injection-safe (RISK-21 / P8-R3).** Any address or subject carrying CR/LF/control
     chars is rejected (`EmailRejected`); the message is assembled with `EmailMessage` (no
     hand-built headers). **Attack:** `a@b.com\r\nBcc: evil@x.com` as a recipient or subject.
  5. **User-initiated, never auto-sent.** A send fires only on the explicit "Send email" button
     (UI) or an explicit `send_report_email` call. **Attack:** confirm nothing sends on page
     load/rerun; confirm the UI panel only appears when `email_enabled()`.
  6. **Egress controls (RISK-20).** Every send is **audit-logged** on `ask_oracle.audit` with
     **metadata only** (recipients/subject/format/row_count/bytes — **no body, no row data, no
     credential**); the optional `EMAIL_ALLOWED_DOMAINS` allow-list **hard-rejects** out-of-policy
     recipients **before any SMTP call**; the size cap (`EMAIL_MAX_ATTACHMENT_MB`) is enforced
     pre-send. **Attack:** confirm an allow-list/oversize/invalid-recipient rejection makes **no**
     SMTP call (`mock.assert_not_called()`); confirm no row data in the audit fields.
  7. **Attachment correctness.** CSV/Excel built via the existing `dataframe_to_csv_bytes` /
     `dataframe_to_excel_bytes`; filename + MIME correct; CSV/Excel selectable at send time.
  8. **No regression** to standing invariants — secrets-via-env, metadata-only persistence,
     Phase-6 error sanitization, Phase-6.5 edge posture, the redaction guarantee.

## Test status
- `pytest -q` → **365 passed** (Python 3.13; **SMTP fully mocked, no network in CI**). New: 58
  tests — `test_mailer_config.py`, `test_mailer_message.py`, `test_mailer_recipients.py`,
  `test_mailer_sender.py` — over Phase-7's 307.
- **Live send (success criterion 6):** the path was verified **end-to-end against real Gmail**
  during smoke testing (a real message was sent via `scripts/p8_email_smoke.py` / the product
  code). The reviewer may re-run the smoke against their own `.env` creds.

## Known limitations / not covered
- **Streamlit UI** (`_render_email_action`) is not unit-tested (no Streamlit runtime in the suite);
  verified by `py_compile` + manual/live use. Logic under test lives in the `core/mailer` service.
- **Gmail API / OAuth + per-user sender** deferred ([ITM-020](../issue-log.md), ADR-017) — SMTP +
  App Password + single shared mailbox is the shipped path.
- **AI-drafted email body** deferred ([ITM-021](../issue-log.md)) — would send row data to the LLM.
- **`EMAIL_ALLOWED_DOMAINS` defaults to empty = allow any** (by design; the operator sets it to
  restrict recipients). Every send is audited regardless.
- **CI has not run on this branch** (local-only during the freeze) — run the suite locally.

## Expected reviewer output
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + `file:line` + repro),
blocking list (default open S1/S2), QA results, could-not-verify — to `docs/reviews/phase-8-review-r1.md`.
