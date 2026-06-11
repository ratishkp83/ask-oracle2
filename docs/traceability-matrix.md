# D13 — Traceability Matrix

> **Document:** Traceability Matrix · **Version:** 1.6 · **Status:** Living · **Owner:** QA/Engineering · **Last updated:** 2026-06-11

Maps requirements → design → implementation → tests, so coverage gaps are visible.

| Requirement | Design ref | Implementation | Test(s) |
|-------------|-----------|----------------|---------|
| FR-1 Connection profiles | [Arch §2](03-architecture.md), [Data §1](04-data-models.md) | `core/profiles.py`, `api.py:/profiles` | `test_profiles.py`, `test_execute_endpoint.py::test_profiles_crud*` |
| FR-2 Test connection | [API §/profiles/{id}/test](05-api-contracts.md) | `api.py`, `db.py:run_select` | manual UI smoke; `/test-connection` |
| FR-3 SELECT-only safety | [ADR-001](adr/ADR-001-sql-safety-engine.md), [Arch §3](03-architecture.md) | `core/sql_safety.py`, `db.py`, `api.py:/execute` | `test_sql_safety.py`, `test_execute_endpoint.py::test_execute_rejects_unsafe_sql` |
| FR-4 Bounded execution | [Data §3](04-data-models.md) | `core/config.py`, `db.py:run_select` | covered via `QueryResult.truncated` (live-DB test future) |
| FR-5 NL→SQL propose-only | [Arch §3](03-architecture.md) | `nl2sql.py`, `api.py:/nl2sql` | `test_nl2sql_config.py` (config); generation = manual |
| FR-6 Per-user LLM | [ADR-004](adr/ADR-004-per-user-llm-config.md) | `nl2sql.LLMConfig`, `app.py` Settings | `test_nl2sql_config.py` |
| FR-7 Export CSV/Excel | — | `utils.py`, `app.py` | manual UI smoke |
| FR-8 Saved/parameterized reports | [Design](reports-templates-ux-design.md), [ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md), [ADR-008](adr/ADR-008-reports-core-module-api-parity.md) | `core/reports.py`, `api.py:/reports`, `app.py` Reports | `test_reports.py`, `test_reports_api.py`, `test_bind_safety.py` |
| FR-9 Audit without leakage | [Arch §4](03-architecture.md), [ADR-012](adr/ADR-012-observability-and-error-handling.md) | `core/audit.py`, `core/logging_config.py`, `api.py:/execute` | `test_logging_config.py::test_audit_execution_emits_valid_json_without_secrets` |
| FR-10 EBS templates | [Design §2.4](reports-templates-ux-design.md) | `core/templates.py`, `api.py:/templates`, `app.py` Templates | `test_templates.py` |
| FR-11 Data-dictionary browser | [Design §2,7](data-dictionary-design.md) | `schema.py` helpers, `app.py` Data Dictionary | `test_schema_tools.py`, `test_app_smoke.py` |
| FR-12 Schema introspection | [Design §5](data-dictionary-design.md), [ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md) | `core/introspection.py`, `api.py:/schemas/introspect` | `test_introspection.py`, `test_schemas_api.py` |
| FR-13 Schema persistence | [Design §4](data-dictionary-design.md), [ADR-011](adr/ADR-011-schema-persistence-store.md) | `core/schema_store.py`, `api.py:/schemas` | `test_schema_store.py`, `test_schemas_api.py` |
| NFR-1 Safety/fail-closed | [ADR-001](adr/ADR-001-sql-safety-engine.md), [ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md), [ADR-009](adr/ADR-009-readonly-db-account-precondition.md), [ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md) | `core/sql_safety.py` (incl. `SELECT…INTO` reject), `db.py:validate_binds`, introspection via chokepoint | `test_sql_safety.py` (26), `test_bind_safety.py` (14), `test_introspection.py` |
| NFR-2 Secret confidentiality | [ADR-002](adr/ADR-002-encrypted-profiles.md), [ADR-003](adr/ADR-003-secrets-via-env.md) | `core/crypto.py`, `storage.py` (no plaintext password), `.gitignore` | `test_profiles.py::test_file_store_encrypts_at_rest`, `test_storage.py` |
| NFR-6 Testability/CI | [Test Strategy](06-test-strategy.md) | `tests/`, CI workflow (3.11+3.13 matrix) | full suite (260) |
| NFR-7 Observability & safe error handling | [ADR-012](adr/ADR-012-observability-and-error-handling.md), [Design](observability-error-handling-design.md) | `core/logging_config.py`, `core/errors.py`, `core/metrics.py`, `api.py` middleware/handlers, `app.py` UI sanitizer | `test_logging_config.py`, `test_error_handling.py` (incl. ITM-015 leak proof + ITM-017 surfaces), `test_metrics.py` |
| NFR-8 Deployment hardening (edge auth/CORS, SSRF encodings, store durability) | [ADR-013](adr/ADR-013-network-edge-hardening.md), [ADR-014](adr/ADR-014-file-store-durability.md), [Design](pre-deployment-hardening-design.md) | `core/auth.py`, `api.py` CORS config, `core/llm/providers.py` host decode, `core/fileio.py`, store quarantine (`reports`/`profiles`/`schema_store`) | `test_auth.py`, `test_llm_providers.py` (encoding matrix), `test_fileio.py`, `test_store_robustness.py` |

**Known gaps:** FR-4 (no live-DB limit test), FR-9 (no dedicated audit-redaction test), FR-5 generation quality (manual only), FR-10 template SQL not validated vs. a live EBS instance, FR-12 introspection not run vs. a live instance (both pre-GA RISK-04). Tracked in [task-tracker](task-tracker.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | QA/Eng | Initial matrix; gaps flagged. |
| 1.1 | 2026-06-10 | QA/Eng | Phase 4: FR-8 upgraded, FR-10 added, bind-safety traced (ADR-007/008); suite 118. |
| 1.2 | 2026-06-10 | QA/Eng | Phase 5: FR-11/12/13 traced (ADR-010/011); introspection-via-chokepoint under NFR-1; suite 155. |
| 1.3 | 2026-06-10 | QA/Eng | Phase 6: NFR-7 (observability & safe error handling) added; FR-9 now has a dedicated test; NFR-6 suite 182 + CI matrix; ADR-012. |
| 1.4 | 2026-06-11 | QA/Eng | Phase 6.5: NFR-8 (deployment hardening) added (ADR-013/014); NFR-7 extended with ITM-017; suite 236. |
| 1.5 | 2026-06-11 | QA/Eng | Phase 6.5 review r1 remediation (R1–R4): NFR-8 hardened (Unicode SSRF fold, fd-close, blank-CORS fallback); suite 242. |
| 1.6 | 2026-06-11 | QA/Eng | Round C1 (ITM-007/006/008): suite 260; `core/llm/pii.py` opt-in PII scrubbing, `connection.json` write path retired. |
