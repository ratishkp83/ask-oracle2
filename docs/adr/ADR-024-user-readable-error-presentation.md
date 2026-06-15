# ADR-024 — User-readable error presentation (no developer text to end users)

- **Status:** Accepted
- **Date:** 2026-06-15
- **Deciders:** Product/Engineering (owner-requested)
- **Phase:** v2 / Phase 9 (B6 — cross-cutting)

## Context
During owner testing a failed report run surfaced **"Database error — see server logs."** in the UI. That
string is the backend's *sanitized* DB error ([ADR-012](ADR-012-observability-and-error-handling.md)):
the full driver detail is logged server-side and an `error_id` is returned for support correlation — but
the message itself is **operator-facing** and should never be shown to an end user. The owner's
requirement: **all errors must be user-readable**, and anything not actionable by the user should be a
generic message that points to IT support, carrying the reference id.

## Decision
Fix it at the source and centralize the presentation policy:

1. **Backend (`_db_error`).** Its user-facing `detail` becomes friendly and support-oriented
   ("A database error occurred while running your request. Please try again, or contact IT support with
   this reference."). Full driver detail is **still logged server-side**; the `error_id` is unchanged.
   This fixes every client, not just React.
2. **Frontend single policy (`web/src/lib/api/client.ts`).** `friendlyError`/`errorMessage` are the one
   place a thrown error becomes copy:
   - **Pass through** the server's safe, intentional messages (validation, safety rejections, not-found,
     the now-friendly DB message) **with the reference id**.
   - **Substitute a generic "contact IT support" message** only for the cases with no usable server
     message: a **network failure** (status 0) and a **bodyless HTTP fallback** (`Request/Export
     failed (NNN)`).
   - Every error surface (Ask, Email, Excel export, and the B6 screens) routes through it.

## Rationale / Security
- The backend already sanitizes anything sensitive, so the frontend's job is to **show** those messages,
  not re-hide them — and to genericize only the genuinely opaque. Raw driver text never reaches the client.
- The **`error_id` is always preserved** so support can correlate to the full server-side log.
- Blanket-genericizing all `5xx` was **rejected**: it would discard genuinely useful intentional messages
  (e.g. "The model is temporarily unavailable.").

## Consequences
- Consistent, readable errors across the whole surface; the support reference is retained.
- The backend DB-error contract string changed (3 assertions updated in `tests/test_error_handling.py`).
- One small, well-tested helper (`web/src/lib/api/errorMessage.test.ts`) locks the policy.

## Alternatives considered
- **Frontend-only pattern-matching** of the old "see server logs" string: rejected — brittle; the fix
  belongs at the source so all clients benefit.
- **Status-only routing (4xx verbatim / 5xx generic):** rejected — the opaque DB error is a 400, and some
  5xx messages are useful; the message-usability signal (network / synthetic fallback) is more accurate.
