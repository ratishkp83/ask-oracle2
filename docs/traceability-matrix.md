# D13 — Traceability Matrix

> **Document:** Traceability Matrix · **Version:** 1.0 · **Status:** Living · **Owner:** QA/Engineering · **Last updated:** 2026-06-10

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
| FR-8 Saved reports | — | `storage.py`, `app.py` | manual UI smoke |
| FR-9 Audit without leakage | [Arch §4](03-architecture.md) | `core/audit.py`, `api.py:/execute` | asserted indirectly; dedicated test = backlog |
| NFR-1 Safety/fail-closed | [ADR-001](adr/ADR-001-sql-safety-engine.md) | `core/sql_safety.py` | `test_sql_safety.py` (24 cases) |
| NFR-2 Secret confidentiality | [ADR-002](adr/ADR-002-encrypted-profiles.md), [ADR-003](adr/ADR-003-secrets-via-env.md) | `core/crypto.py`, `.gitignore` | `test_profiles.py::test_file_store_encrypts_at_rest` |
| NFR-6 Testability/CI | [Test Strategy](06-test-strategy.md) | `tests/`, CI workflow | full suite (48) |

**Known gaps:** FR-4 (no live-DB limit test), FR-9 (no dedicated audit-redaction test), FR-5 generation quality (manual only). Tracked in [task-tracker](task-tracker.md).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | QA/Eng | Initial matrix; gaps flagged. |
