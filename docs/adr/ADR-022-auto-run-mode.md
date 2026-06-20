# ADR-022 — Auto-run mode (and the reframing of Invariant 2)

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Product/Engineering (owner-requested; owner-approved reframing)
- **Phase:** v2 / Phase 9 (B5b-3 Inc 4 / Packet 4d)

## Context
**Invariant 2** has been stated as: *"AI proposes, the user approves; the editable review is the
deliberate gate; never auto-run."* The owner requested a faster path: an **Auto-run toggle** so that,
when on, asking a question converts to SQL **and fetches the data in the background** — seamlessly,
without the manual approve step — while the generated SQL can still be **pulled up, edited, and
re-run**. This directly tensions the literal "never auto-run" wording, so the decision is recorded here.

## Decision
Add a **persisted, default-OFF** Auto-run toggle (session preference) in the Ask panel.

- **Off (default):** unchanged — ask → propose → **review/approve** → run.
- **On (and a connection is set):** ask → `nl2sql` → `execute` in the background → results, via a single
  seamless loader (no review flash); the button relabels to **"Ask"**. With no connection set, it
  **falls back** to the review (Run disabled, E10 hint).
- **Always:** an **"Edit SQL"** action on the results opens the query in the **editable review** for
  modification + re-run; failures in either mode drop to that editable review (E9), so a bad query is
  one edit away from a re-run.

**Reframe Invariant 2** to: *"AI proposes; the human stays in control — approving each query, **or**
opting into auto-run via an explicit toggle; the SQL is always reviewable, editable, and re-runnable;
the SELECT-only chokepoint (Inv 1) is never bypassed."*

## Rationale / Security
- **Auto-run is read-only-safe.** The SELECT-only chokepoint ([ADR-005](ADR-005-execute-chokepoint.md))
  + the required least-privilege read-only account ([ADR-009](ADR-009-readonly-db-account-precondition.md))
  mean **nothing destructive is possible in either mode** — the server rejects anything that isn't a
  provably read-only SELECT/CTE. The review gate's value is **correctness and cost**, not
  safety-from-destruction.
- The human remains in control: they **choose the mode** (explicit, visible, default-off, persisted) and
  every query stays **inspectable/editable/re-runnable**. Auto-run trades a correctness/cost check for
  speed as a deliberate, reversible user choice.
- **Bounds:** runaway result size is bounded by the existing `SafetyLimits` row cap; errors are
  sanitized (`error_id`, [ADR-012](ADR-012-observability-and-error-handling.md)).

## Consequences
- Faster "ask → see" for users who opt in; the trust-by-default posture is preserved (off by default,
  every query reviewable). One additional persisted session preference.
- This ADR **supersedes the strict "never auto-run" wording** of Invariant 2 — but **not** the chokepoint
  (Inv 1), which remains absolute and is the actual safety control.

## Alternatives considered
- **No auto-run (keep mandatory per-query approval):** rejected — owner-requested, and defensible because
  the chokepoint already guarantees read-only.
- **Auto-run as the default:** rejected — approve-first stays the safe, out-of-the-box default.
- **A server-side "trusted/auto" flag:** rejected — auto-run is a **client UX preference**; the safety
  control is the chokepoint, not the review gate, so no server change is warranted.
