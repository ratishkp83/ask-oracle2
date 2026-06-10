# Adversarial Review & QA Prompt (reusable, per-phase)

> **Document:** Process Artifact · **Version:** 1.0 · **Status:** Baseline · **Owner:** Delivery Lead · **Last updated:** 2026-06-10

This is the standing prompt handed to an **independent** reviewer at the end of
every phase. The reviewer **must not be the author** of the code under review —
a different person, or a separate AI instance with fresh context. Fill the
**Context** block, then run. The reviewer's output drives the
[External Review & QA Gate](external-review-gate.md).

---

## Context (fill in per phase)

- **Product:** Ask Oracle Reports — a read-only, AI-assisted reporting layer for Oracle DB / EBS.
- **Phase under review:** «Phase N — title»
- **Charter / scope:** «paste objectives + deliverables, or link the phase charter»
- **Change set:** «git range `<base>..<head>` or PR link»
- **Updated docs:** «links to changed governed docs»
- **Product invariants that MUST hold — attack these first:**
  - SELECT/CTE only; **all** DML/DDL/PL-SQL, stacked statements, and `FOR UPDATE` are rejected, **fail-closed**.
  - No secret (DB password, API key) appears in source, logs, API responses, error messages, or git history.
  - Connection-profile passwords are encrypted at rest and **never** returned by the API.
  - `/execute` is the **single execution chokepoint** — UI and API both route through it; no second/weaker check exists.
  - Configurable limits (max rows / time / result-size) are enforced; a per-request `max_rows` may only **narrow**, never widen, the global cap.
  - Audit logs contain a SQL **hash + metadata only** — never raw SQL or credentials.
  - *(Append invariants introduced by this phase.)*

---

## Your stance

You are a **hostile, senior reviewer**. Assume the code is broken and unsafe
until proven otherwise. Your job is to **break it** — find the input, sequence,
or state that violates an invariant, leaks a secret, or crashes the app — not to
praise it. Skip style nits unless they cause real risk. **Every finding needs an
exact `file:line` and a concrete reproduction** (the precise input/steps).

---

## Part A — Adversarial code review

Probe at minimum:

1. **Safety bypass.** Can any non-SELECT reach the database? Try: SQL comments (`--`, `/* */`), CTE-/subquery-wrapped DML, set operations, optimizer hints, unicode/whitespace/newline tricks, multiple statements, anonymous PL/SQL blocks, `FOR UPDATE`, `MERGE`, `INSERT … RETURNING`, side-effecting functions/`TABLE()` calls, and dialects sqlglot may mis-parse. Does fail-closed truly hold when the parser errors?
2. **Secret exposure.** Search the diff, responses, logs, and history for credentials/keys. Can a password be coaxed into an API response, error, stack trace, or audit record? What happens when `APP_SECRET_KEY` is missing or rotated?
3. **Contract integrity.** Do endpoints match the API-contracts doc exactly (status codes, error shape, required/forbidden fields)? Any drift between code, docs, and tests?
4. **State & concurrency.** File-store races, partial/torn writes, duplicate IDs, session bleed-through, UI widget-key collisions, cache staleness.
5. **Error handling.** Are DB/LLM/network failures surfaced without leaking internals? Any bare `except` swallowing real errors or masking failures as success?
6. **Limits.** Can a caller exceed max rows/time/result-size? Is `truncated` honest? Can request params widen a global cap?
7. **Assumptions.** List each implicit assumption the author relied on that isn't enforced, and show exactly where it breaks.
8. **Dependencies.** New deps — supply-chain risk, version pinning, license, known CVEs.

## Part B — Adversarial QA

- Re-run the automated suite; report pass/fail and **coverage gaps**.
- Design and **execute** abuse / negative / boundary cases beyond the existing tests, with exact inputs. At minimum: the invariant attacks above, malformed/empty/oversized inputs, missing configuration, and edge/unauthorized states.
- Verify **graceful failure** — no stack traces or secrets reach the user.
- Note anything you **could not** test and why.

---

## Required output (use exactly this structure)

1. **Verdict** — one of:
   - `PASS` — no blocking findings.
   - `PASS-WITH-FIXES` — only non-blocking findings.
   - `FAIL — second iteration required` — one or more blocking findings.
2. **Findings table:** `ID | Severity | Category | Location (file:line) | Description | Reproduction/exploit (exact input) | Recommended fix`.
3. **Blocking items** — explicit list that must be fixed before the phase can close (default: all open **S1/S2**).
4. **QA results** — cases run, outcomes, evidence.
5. **Could-not-verify** — what was out of reach and what's needed to verify it.

**Severity guide:** **S1** = invariant violation / data loss / secret exposure / crash on a normal path. **S2** = security or correctness bug on a plausible path. **S3** = minor correctness/robustness. **S4** = trivial.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial adversarial review + QA prompt. |
