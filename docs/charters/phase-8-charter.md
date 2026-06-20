# Phase 8 Charter — Follow-up Actions: Email a Report via Gmail (v2)

> **Document:** Phase Charter · **Version:** 1.1 · **Status:** 🟢 Discovery — approach approved (owner, 2026-06-13); Design next · **Owner:** Product/Engineering · **Last updated:** 2026-06-13

> **Owner directive (2026-06-13):** *"I want to be able to demo sending an actual email — build with the approach that achieves this."* A **live end-to-end send** is therefore a first-class deliverable (the email equivalent of the RISK-04 live-Oracle pass), not just mocked tests. The chosen transport (SMTP + App Password) is the fastest path to a real demoable send. **External dependency the owner provides:** a Gmail account with **2-Step Verification + an App Password**, placed in the git-ignored `.env` (see *Live-demo dependency*). All code, mocked CI tests, and the live smoke script can be built before the credential is supplied.

## Lifecycle stage
**Discovery OPENED 2026-06-13** on the **v2 branch** (`D:\Ratish\Personal\Project\ask-oracle-reports-main v2`, branch `v2`; local commits only, no push until the July limit reset). Phases 1–7 are all closed and the product is GA-ready for the core read-only reporting flow. Phase 8 is the **first v2 feature**: a *follow-up action* surface so a decision-maker, having run a report, can act on the result by **emailing it to whoever they decide should act on it**, with the report output attached, sent through **Gmail**.

## Context — grounding facts
- **The product flow today:** Connect → Ask (NL→SQL) → review SQL → run → view results → **export (CSV/Excel)**. Phase 8 adds a sibling to "export": **send**.
- **Export is already half-built and reusable:** `src/utils.py` has `dataframe_to_csv_bytes(df)` and `dataframe_to_excel_bytes(df, sheet_name)` (openpyxl), already wired to download buttons after a report runs ([app.py:594](../../src/app.py)). The email attachment reuses these — **no new serialization work** for CSV/Excel.
- **No email/SMTP/OAuth code exists** anywhere in `src/` — this is greenfield.
- **An email-detection regex already exists** in `src/core/llm/pii.py` (used by the PII scrubber) — reusable for the "smart quick-pick" of recipient candidates found in result columns.
- **Reusable platform pieces from earlier phases:** structured logging + `request_id`/`error_id` and the uniform error sanitizer (`core/logging_config.py`, `core/errors.py`, Phase 6); in-process metrics (`core/metrics.py`); opt-in `X-API-Key` auth + env CORS (`core/auth.py`, Phase 6.5); env-only secrets + Fernet-encrypted profile passwords.
- **This feature is a deliberate, user-initiated DATA EGRESS.** Emailing report output sends **real row data** to an external recipient. This is the **same trust boundary as the existing CSV/Excel download** (data already leaves the app when a user exports) — it does **not** violate the "schema names only to the LLM" rule, which governs prompts to the *LLM provider*, not user-approved exports. The send is **always user-reviewed, never auto-sent** (consistent with "AI proposes, user approves"). The *only* place this would touch the LLM-redaction line is auto-drafting the body with the LLM — which is **explicitly OUT of MVP scope** (see Scope OUT).

## Non-negotiables (unchanged, must not regress)
- **SELECT/CTE-only chokepoint** (`core/sql_safety.py` / `db.py`) — **untouched**. The attachment is built from a result set that already passed the chokepoint; no new SQL path is introduced.
- **AI proposes, user approves** — extended naturally: the *email* is composed and explicitly sent by the user; nothing is auto-sent.
- **External LLM prompts carry schema names only** — unaffected (no LLM call in MVP email path).
- **Secrets via env only; never logged, never returned by the API.** The Gmail credential follows this rule.

## Objectives
1. After a report runs, let the user **compose and send an email** — to one or more recipients they choose **based on the query output** — with the **report output attached** (CSV or Excel, their pick), via the configured **Gmail** mailbox.
2. Make "whom to contact" easy: **free-form entry** plus **smart quick-pick** of email-like values detected in the result columns.
3. Ship it **safely and opt-in**: feature disabled until configured; credentials env-only and never leaked; header-injection-safe; every send **audit-logged**; an **optional recipient allow-list** as an exfiltration guard.
4. Keep everything governed: charter → owner decisions → design → build (B1…Bn) → independent exit-gate review (reviewer ≠ author).

## Resolved decisions (owner, 2026-06-13)
| # | Decision | Choice |
|---|----------|--------|
| D-A | Gmail transport | **SMTP + App Password** — `smtp.gmail.com` STARTTLS, app password (account has 2-Step Verification). No Google OAuth review burden; fits the single-box/owner deployment. OAuth/Gmail API is a future increment. |
| D-B | Sender identity | **Single shared app mailbox** — one configured "from" account via env; emails appear from the app's address. Per-user sender is future (pairs with OAuth + multi-tenant). |
| D-C | Attachment format | **CSV or Excel, user picks at send time** — reuse the existing export helpers. PDF is out (no new dependency). |
| D-D | Recipient selection | **Free-form + smart quick-pick** — type any address(es) (comma-separated) **plus** one-click candidates detected from email-like values in the result columns. |
| D-E | Send surface | **UI + unit-testable service function; NO public HTTP send endpoint this phase** (recommended default; owner deferred to recommendation 2026-06-13). Minimizes the abuse/exfil surface; an auth-gated `POST /email` is a deliberate later increment. |
| D-F | Recipient allow-list | **Ship the optional `EMAIL_ALLOWED_DOMAINS` env allow-list** — default empty = allow all, every send audited (recommended default; owner deferred to recommendation 2026-06-13). |

### Live-demo dependency (owner-provided)
A real send needs a Gmail credential, supplied via the git-ignored `.env` (never committed), exactly as the Oracle XE creds are (`AOR_LIVE_*`):
- Gmail account with **2-Step Verification** enabled → **App password** created (16 chars).
- Env keys (finalized at design): `SMTP_HOST` (default `smtp.gmail.com`), `SMTP_PORT` (default `587`), `SMTP_USER` (the Gmail address), `GMAIL_APP_PASSWORD`, `EMAIL_FROM` (defaults to `SMTP_USER`).
- A `scripts/p8_email_smoke.py` drives one real send through the product code for the demo/live pass; CI stays fully mocked.

## Scope — proposed IN (subject to D-E, D-F)
- **New mailer module** (`src/core/email/` or `src/core/mailer.py`): send via `smtplib` + `ssl` STARTTLS to `smtp.gmail.com:587`, single shared mailbox from env (`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`GMAIL_APP_PASSWORD`/`EMAIL_FROM`). Built with Python's `email.message.EmailMessage` (correct MIME + encoding; no hand-built headers).
- **Attachment builder** reusing `dataframe_to_csv_bytes` / `dataframe_to_excel_bytes`; the **exact result already shown** is attached (no re-query, no extra DB hit). Filename derived from the report/query.
- **Recipient handling:** comma-separated To + optional CC; address validation (RFC-ish) and **CRLF/header-injection guard** on every address and the subject; **smart quick-pick** scans result columns for email-pattern values (reuse the `pii.py` regex), de-duplicated, offered as one-click adds.
- **Compose UI** (Streamlit, after results): a "Send as email / follow-up action" expander — To, CC, Subject (prefilled, e.g. report name + date), Body (free text), attachment-format toggle (CSV/Excel), Send. Clear success / error (`error_id`) feedback; the panel only appears when the feature is configured.
- **Guardrails:** feature **opt-in** — disabled with a clear hint when SMTP env is absent; **size/row cap** with a warning (respect Gmail's 25 MB limit; attach from the in-memory result); **audit log** of every send (sender, recipients+CC, subject, report id / row count, outcome, timestamp) via the observability layer; a **metrics counter** for sends/failures.
- **Config + deployment:** `.env.example`, `render.yaml`, `docker-compose.yml`, and D7 updated with the new env vars; credential redaction verified in logs/errors.
- **Tests + governed docs in lockstep:** SMTP fully mocked (no real send in CI); new **ADR-017** (Email-a-report via Gmail SMTP), **RISK-20** (email data egress) + **RISK-21** (SMTP credential handling), tracker/CHANGELOG/HANDOFF; independent exit-gate review at close.

## Scope — explicit OUT
- **No OAuth / Gmail API** and **no per-user sender** (future increment; multi-tenant / RISK-07 territory).
- **No AI-drafted email body** — would send row data to the LLM and brush the redaction line; deliberately deferred as a clean later increment behind an explicit opt-in.
- **No PDF attachment** (no new dependency this phase).
- **No inbound email, threading, reply/read tracking, or scheduled/automated sends** — every send is user-initiated and synchronous.
- **No persistent contact directory / address book** (smart quick-pick is derived from the current result, not stored).
- **No change to the SELECT-only chokepoint or the Phase-6.5 security posture.**

## Risks (initial — promoted to the register at design)
| ID | Risk | Sev | Mitigation |
|----|------|-----|------------|
| P8-R1 | **Data exfiltration** — user emails sensitive output to an unauthorized/personal/external address | Med-High | User-initiated + reviewed (same boundary as export); **audit log** every send; **optional `EMAIL_ALLOWED_DOMAINS` allow-list** (D-F); feature opt-in/off by default |
| P8-R2 | **SMTP credential leak** — app password exposed via logs or API responses | High | Env-only; never returned by any endpoint; redacted in logs/errors (reuse the DB-error sanitizer pattern); not written to any store |
| P8-R3 | **Email header injection** — CRLF in user-supplied subject/recipient forges headers | Med | Use `EmailMessage` (not raw headers); validate + strip CRLF from addresses and subject; reject malformed addresses |
| P8-R4 | **Oversized attachment** — large result blows memory or Gmail rejects (>25 MB) | Med | Row/byte cap with a clear pre-send warning; attach from the already-fetched result; surface SMTP rejects cleanly |
| P8-R5 | **Send failure ambiguity** — partial/failed send leaves the user unsure | Low-Med | Synchronous send; explicit success/error with `error_id`; audit log records the outcome |
| P8-R6 | **Scope creep into AI-draft → LLM egress** | Low | AI-draft is OUT this phase; if added later, body is built from a local summary or treated as an explicit sanctioned exception |

## Success criteria (phase exit — finalized at design)
1. After a report runs, the user can compose and send an email to one or more recipients with the result attached as **CSV or Excel**, via the configured Gmail mailbox — verified end-to-end with a **mocked SMTP** (no real send in CI).
2. **Smart quick-pick** surfaces email-like values from the result columns; **free-form** entry also works; invalid/injection-bearing addresses are rejected.
3. Feature is **opt-in** (disabled with a clear hint when SMTP env is unset); credentials are **never logged or returned**; subject/recipient handling is **header-injection-safe**.
4. **Every send is audit-logged** (sender, recipients, subject, report/row count, outcome, timestamp) and counted in metrics.
5. **SELECT-only chokepoint + redaction posture unchanged**; suite green on 3.11 + 3.13; ADR-017 + governed docs current; **independent exit-gate review = PASS** (reviewer ≠ author).
6. **Live send demonstrated** — `scripts/p8_email_smoke.py` sends one real email (with attachment) through the product code against the owner's Gmail App Password, and the Streamlit "Send" path delivers a real email in a manual demo. (The demo deliverable per the owner directive; CI remains mocked.)

## Decisions D-E / D-F — RESOLVED 2026-06-13 (owner deferred to the recommendations below)
- **D-E — Surface: UI-only vs API parity.**
  (a) **Core tested service + Streamlit UI only — no public HTTP send endpoint this phase** — **[Recommended]**; minimizes the abuse/exfil surface (an authenticated `POST /email` on a networked deploy is a powerful exfil primitive). The send logic lives in a unit-testable service function.
  (b) Also expose an **auth-gated `POST /actions/email` (and `/v1/...`)** for API/UI parity and automation.
  *Recommendation: (a)* — ship the value behind the UI first; add the endpoint deliberately once the multi-tenant auth story is firmer.

- **D-F — Recipient allow-list guard.**
  (a) **Ship an optional `EMAIL_ALLOWED_DOMAINS` env allow-list (default empty = allow all, every send audited)** — **[Recommended]**; cheap, strong exfil control for customers who want to restrict sends to corporate domains, off by default so it doesn't block the owner's testing.
  (b) No allow-list — rely on audit logging alone.
  *Recommendation: (a)* — additive, defends P8-R1, zero cost when unset.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-13 | Product/Eng | Discovery charter opened (v2 / Phase 8) — email-a-report follow-up action via Gmail SMTP. D-A…D-D resolved by owner (SMTP+App Password, single shared mailbox, CSV/Excel user-picks, free-form + smart quick-pick). D-E (UI-only vs API parity) and D-F (recipient allow-list) pending. **No code until the charter is approved.** |
| 1.1 | 2026-06-13 | Product/Eng | **Approach approved by owner** with the directive to demo a real send. D-E resolved (UI + service, no HTTP endpoint), D-F resolved (optional `EMAIL_ALLOWED_DOMAINS`). Added the **live-send demo** deliverable (success criterion 6) + the Gmail App Password **Live-demo dependency** (owner-provided via `.env`). Discovery → **Design next.** |
