# External Review & QA Gate (mandatory, every phase)

> **Document:** Process · **Version:** 1.0 · **Status:** Baseline · **Owner:** Delivery Lead · **Last updated:** 2026-06-10

## Policy

**No phase is "closed" until it passes an independent adversarial code review + QA.**
The reviewer **must not be the author** of the code under review (a different
person, or a separate AI instance with fresh context — author self-review does
not satisfy this gate). This is part of the Definition of Done for every phase.

## Definition of Done — phase exit gate

A phase may close only when **all** hold:

1. Development complete; automated tests green in CI.
2. Governed docs updated (code + docs in the same change set).
3. **Independent adversarial review + QA performed** using the [Adversarial Review & QA Prompt](adversarial-reviewer-prompt.md); verdict recorded.
4. All **blocking** findings (S1/S2) remediated and re-validated by tests; S3 fixed or **formally deferred** (logged with rationale in the risk/issue register); S4 backlogged.
5. A review iteration returns **`PASS`** or **`PASS-WITH-FIXES` with no open blocking findings**.
6. Closure sign-off recorded (task tracker + CHANGELOG).

## The loop

```
prepare package → review (rN) → triage to issue log → remediate blocking
       ↑                                                      │
       └──────────────  second review (rN+1)  ←───────────────┘
                         (only if blocking findings)
                                  │
                       no blocking → GATE PASS → next phase
```

1. **Prepare package** — phase charter, change set (git range / PR), updated docs, test results, known limitations.
2. **Review (iteration r1)** — hand the package + adversarial prompt to the independent reviewer. They return findings + QA results + a verdict.
3. **Triage** — log **every** finding in [issue-log.md](../issue-log.md) with a severity (S1–S4) and disposition.
4. **Remediate** — fix all blocking findings (S1/S2) and any accepted S3; update tests and docs together.
5. **Re-review decision:**
   - If the latest verdict was **`PASS` / `PASS-WITH-FIXES` (no open blocking)** → **gate passes**; proceed to the next phase.
   - Otherwise (**`FAIL`** or any open blocking) → after remediation, run a **second review (r2)** focused on the fixes **plus regression**. Repeat the loop.
6. **Escalate** — if the gate has not passed after **2 iterations**, pause and reassess scope/approach; record the decision as an ADR.
7. **Record** — each iteration produces `docs/reviews/phase-<N>-review-r<n>.md` (findings + verdict). Update the tracker and CHANGELOG; capture sign-off.

## How to run the review (tooling options)

- A **separate AI instance/agent** briefed with the adversarial prompt (fresh context = independent of the author), **or** an external human reviewer.
- `/code-review ultra` — a multi-agent cloud review of the branch/PR — is a strong way to operationalize the **code-review** half. It is **user-triggered and billed**; the assistant cannot launch it.
- **QA half:** re-run `pytest` and execute the adversarial QA cases from the prompt.

## Roles

| Role | Responsibility |
|------|----------------|
| Author (delivery) | Prepares the package; remediates findings. |
| Independent reviewer | Adversarial code review + QA; **not** the author. |
| Delivery lead | Triages findings, records verdict, signs off the gate. |

## Standing per-phase tasks (instantiate as R-tasks each phase)

`R.1` prepare review package · `R.2` independent adversarial code review · `R.3` adversarial QA · `R.4` triage findings → issue log · `R.5` remediate blocking + re-validate · `R.6` re-review until PASS · `R.7` record verdict + closure sign-off.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Gate introduced: mandatory independent adversarial review + QA, with iterate-until-PASS loop. |
