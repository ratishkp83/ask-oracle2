# ADR-017 — Email a report via Gmail SMTP (user-approved data egress)

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Product/Engineering (Phase 8 charter, owner-approved; v2 branch)
- **Phase:** 8 (Follow-up Actions: Email a Report) — v2

## Context
After a report runs, a decision-maker needs to act on it — typically by sending the
result to whoever should follow up. v2 Phase 8 adds a **"Send as email" follow-up
action**: compose an email, attach the output (CSV/Excel), send via Gmail. This is the
product's first feature that **intentionally transmits row data to an external party**, so
the transport, credential handling, and the egress framing warrant a recorded decision.

Inputs (charter): single-box/owner deployment today; must support a **real demoable send**;
avoid the Google OAuth verification burden; keep the SELECT-only chokepoint and the
schema-redaction posture untouched; no new dependency if avoidable.

## Decision
Ship email as a **user-initiated, user-reviewed send** through **Gmail SMTP with an App
Password**, a **single shared mailbox**, using **stdlib only** (`smtplib` + `ssl` +
`email.message.EmailMessage`) — no new dependency. All sends route through one chokepoint,
`send_report_email` (`src/core/mailer/`): validate → build → send → audit-log → meter; it
**never auto-sends**.

- **Transport (D-A):** SMTP STARTTLS on 587 (implicit SSL on 465); App Password (account has
  2-Step Verification). Gmail API/OAuth rejected for now — `gmail.send` is a sensitive scope
  needing Google app-verification before external release (deferred, **ITM-020**).
- **Sender (D-B):** one configured "from" mailbox from env. Per-user sender deferred
  (multi-tenant / OAuth; RISK-07 territory).
- **Attachment (D-C):** CSV or Excel, the user's pick — reuses `dataframe_to_csv_bytes` /
  `dataframe_to_excel_bytes`. No PDF (would add a dependency).
- **Recipients (D-D):** free-form (validated) **plus** smart quick-pick of email-like values
  detected in the result columns.
- **Surface (D-E):** Streamlit UI + a unit-testable service function; **no public HTTP send
  endpoint** this phase (an authenticated `POST /email` is a strong exfil primitive on a
  networked deploy).
- **Egress framing:** emailing output is the **same trust boundary as the existing CSV/Excel
  download** — a sanctioned, user-approved export. It does **not** relax the
  "schema-names-only to the LLM" rule (which governs prompts to the LLM provider, not user
  exports). **No LLM call** on the email path; AI-drafted bodies are OUT (that would send data
  to the model — deferred, **ITM-021**).

## Security properties (must hold)
- **Credential:** `SMTP_PASSWORD` (the App Password) is **env-only**, reaches only
  `smtplib.login`, and is **never** placed in a `SendResult`, audit field, log record, or any
  return value. Feature is **opt-in** — inert unless `SMTP_USER` + `SMTP_PASSWORD` are set
  (`email_enabled`).
- **Header-injection-safe:** addresses and the subject carrying CR/LF/control chars are
  rejected; the message is assembled with `EmailMessage` (no hand-built headers).
- **Exfiltration controls:** every send is **audit-logged** on `ask_oracle.audit` — **metadata
  only** (recipients/subject/format/row_count/bytes; **no body, no row data, no credential**);
  optional **`EMAIL_ALLOWED_DOMAINS`** allow-list (default allow-all, every send still audited);
  pre-send **size cap** (`EMAIL_MAX_ATTACHMENT_MB`, default 20, headroom under Gmail's 25 MB).
- **Errors:** transport/auth exceptions are sanitized — generic `GENERIC_EMAIL_DETAIL` + an
  `error_id` to the user, full detail server-side only (the ADR-012 pattern).
- **Chokepoint untouched:** the attachment is built from the already-fetched result; no new SQL
  path; the SELECT-only guarantee is unaffected.

## Consequences
- A real, demoable send ships now with **zero new dependencies** and no OAuth/verification gate.
- The product gains a deliberate external-egress surface, controlled by audit + optional
  allow-list + opt-in gating.
- Future increments are tracked, not lost: **ITM-020** (Gmail API/OAuth + per-user sender),
  **ITM-021** (optional AI-drafted body behind an explicit opt-in).

## Alternatives considered
- **Gmail API (OAuth2):** rejected for now — verification burden for external/commercial
  release; SMTP+App Password demos immediately (ITM-020).
- **Per-user OAuth sender:** deferred — needs the multi-tenant identity layer (RISK-07).
- **PDF attachment / AI-drafted body:** out of scope (new dependency / LLM egress; ITM-021).
- **Public `POST /email` endpoint:** not this phase (D-E) — UI + service only.

## Notes
- Charter: [charters/phase-8-charter.md](../charters/phase-8-charter.md);
  design: [email-followup-action-design.md](../email-followup-action-design.md).
- Risks: **RISK-20** (email data egress), **RISK-21** (SMTP credential handling).
