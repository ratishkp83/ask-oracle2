# D9 — Architecture Decision Records (ADR)

> **Status:** Living · **Owner:** Engineering · **Last updated:** 2026-06-14

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
| [ADR-008](ADR-008-reports-core-module-api-parity.md) | Reports are a core module with API parity | Accepted |
| [ADR-009](ADR-009-readonly-db-account-precondition.md) | Least-privilege read-only DB account is a required deployment precondition | Accepted |
| [ADR-010](ADR-010-schema-introspection-via-chokepoint.md) | Live schema introspection via the SELECT-only chokepoint | Accepted |
| [ADR-011](ADR-011-schema-persistence-store.md) | Schema persistence store (metadata only) | Accepted |
| [ADR-012](ADR-012-observability-and-error-handling.md) | Observability & error handling (structured logs, error IDs, sanitized DB errors, metrics) | Accepted |
| [ADR-013](ADR-013-network-edge-hardening.md) | Network-edge hardening (opt-in API-key auth + explicit env-driven CORS) | Accepted |
| [ADR-014](ADR-014-file-store-durability.md) | File-store durability (atomic JSON writes; corrupt-record quarantine) | Accepted |
| [ADR-015](ADR-015-ebs-metadata-packs.md) | EBS metadata packs as curated, redaction-safe NL→SQL overlays | Accepted |
| [ADR-016](ADR-016-defer-23ai-vector-track.md) | Defer the Oracle 23ai vector track (record direction; ITM-018) | Accepted |
| [ADR-017](ADR-017-email-report-via-gmail-smtp.md) | Email a report follow-up action via Gmail SMTP (opt-in, user-approved, no LLM) | Accepted |
| [ADR-018](ADR-018-per-profile-default-schema.md) | Per-profile default schema (`ALTER SESSION SET CURRENT_SCHEMA`) | Accepted |
| [ADR-019](ADR-019-react-cxo-surface.md) | Bespoke React CXO executive surface (against the existing `/v1` API) | Accepted |
| [ADR-020](ADR-020-result-export-and-email-api.md) | Result export & email over HTTP (post-the-shown-result, no re-query, no LLM) | Accepted |
| [ADR-021](ADR-021-sql-aware-derivation-and-cascade.md) | SQL-aware deterministic derivation + cascading drill-down (no row data to any LLM) | Accepted |
| [ADR-022](ADR-022-auto-run-mode.md) | Auto-run mode + the reframing of Invariant 2 (chokepoint never bypassed) | Accepted |
| [ADR-023](ADR-023-report-parameter-value-pickers.md) | Report parameter value-pickers (lookups, FK suggest, run-time auto-derivation) | Accepted |
| [ADR-024](ADR-024-user-readable-error-presentation.md) | User-readable error presentation (no developer text to end users; `error_id` kept) | Accepted |

Template: [ADR-template.md](ADR-template.md).
