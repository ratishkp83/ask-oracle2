# D9 — Architecture Decision Records (ADR)

> **Status:** Living · **Owner:** Engineering · **Last updated:** 2026-06-10

Each significant decision is recorded as an immutable ADR: context, the decision,
consequences, and alternatives considered. Superseding a decision means adding a
new ADR that references the old one (don't rewrite history).

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-sql-safety-engine.md) | Layered SQL safety engine (sqlglot + denylist) | Accepted |
| [ADR-002](ADR-002-encrypted-profiles.md) | Encrypt connection-profile passwords at rest (Fernet) | Accepted |
| [ADR-003](ADR-003-secrets-via-env.md) | Secrets via environment only; remediate + rotate | Accepted |
| [ADR-004](ADR-004-per-user-llm-config.md) | Per-user LLM config, per-session (no auth yet) | Accepted |
| [ADR-005](ADR-005-execute-chokepoint.md) | `/execute` is the single execution chokepoint | Accepted |
| [ADR-006](ADR-006-external-review-gate.md) | Independent adversarial review & QA gate (effective Phase 3; reviewer supplied by owner) | Accepted |
| [ADR-007](ADR-007-parameterized-reports-bind-variables.md) | Parameterized reports use bind variables (never interpolation) | Accepted |

Template: [ADR-template.md](ADR-template.md).
