# ADR-020 — Result export & email over HTTP (post-the-shown-result, no re-query, no LLM)

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 9 (B2)

## Context
The Phase-8 email mailer (`src/core/mailer/`) and the CSV/Excel export helpers lived **only in the
Streamlit app**, rendered server-side. The React surface ([ADR-019](ADR-019-react-cxo-surface.md)) has
no server-side render, so it needs to email and export **the exact result the user is looking at** —
without re-running the query (which could drift from what was shown, costs a round-trip, and re-touches
the DB) and **without** invoking an LLM.

## Decision
Expose two auth-gated endpoints, mounted at the **root and `/v1`**:

- **`POST /reports/email`** — the client posts the **already-shown** `columns` + `rows` (plus
  recipient/subject/body and CSV-or-xlsx choice); the handler rebuilds the table and calls
  `send_report_email` **unchanged**. Opt-in (`email_enabled`): **503** when SMTP is unconfigured.
  `SendResult → HTTP` mapping: `ok→200`, `rejected→400` (safe verbatim), transport/auth `error→502`
  with the mailer's `error_id`.
- **`POST /reports/export`** — the server builds **CSV or xlsx** (openpyxl) from the posted result and
  streams it back as a download, so **no spreadsheet library ships in the browser**; filename sanitized.

Both paths: **no LLM, no re-query**; a pre-build **row/column cap** (100k×1k → 400) so an oversized body
can't spike memory before the mailer's byte cap; full audit log (metadata only).

## Consequences
- The React app can email and export the shown result with one POST; logic is reused, not duplicated.
- The result `rows` transit the API to the server on export/email (they were already in the client from
  `/execute`) — no new disclosure beyond what `/execute` returned; tracked as [RISK-22](../risk-register.md).
- Export/email behaviour is identical between Streamlit and React because both call the same code.

## Security
- Reuses every Phase-8 guard ([ADR-017](ADR-017-email-report-via-gmail-smtp.md)): address validation +
  control-char/header-injection guard, optional `EMAIL_ALLOWED_DOMAINS` allow-list, attachment size cap,
  metadata-only audit log (no body, no rows, no credential), sanitized transport errors (`error_id`).
- Auth-gated (opt-in `X-API-Key`, [ADR-013](ADR-013-network-edge-hardening.md)); SMTP credential stays
  env-only and is never returned or logged ([RISK-21](../risk-register.md)).

## Alternatives considered
- **Re-query server-side from a saved query id:** rejected — needs the query persisted, adds a DB
  round-trip, and risks the emailed/exported data differing from what the user reviewed and approved.
- **Build xlsx in the browser:** rejected — ships a spreadsheet lib into the bundle and duplicates the
  server's export logic; server-side keeps one implementation and a small client.
