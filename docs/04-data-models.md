# D4 — Data Models

> **Document:** Data Models · **Version:** 1.0 · **Status:** Baseline · **Owner:** Engineering · **Last updated:** 2026-06-10

All models are in-process (no relational DB yet). Persistence is JSON under `STORAGE_DIR` (git-ignored).

## 1. Connection profile family (`src/core/profiles.py`)

| Model | Fields | Notes |
|-------|--------|-------|
| `ProfileCreate` (input) | name, host, port=1521, service_name?, sid?, username, password, environment∈{DEV,TEST,PROD} | Validator: `service_name` **or** `sid` required. Carries plaintext password (inbound only). |
| `StoredProfile` (at rest) | id, name, host, port, service_name?, sid?, username, environment, **password_encrypted** | Fernet ciphertext; written to `profiles.json`. |
| `ProfilePublic` (output) | id, name, host, port, service_name?, sid?, username, environment | **No password field by design.** |
| `ResolvedConnection` (internal) | host, port, service_name?, sid?, username, **password** | Decrypted; used only to open a connection server-side. Never serialized to clients. |

## 2. Connection & execution (`src/db.py`)

| Model | Fields |
|-------|--------|
| `OracleConnectionConfig` (dataclass) | host, port, service_name?, sid?, username, password |
| `QueryResult` (dataclass) | columns: list[str], rows: list[tuple], elapsed_seconds: float, truncated: bool, row_count: int |

## 3. Safety & LLM config

| Model | Fields | Source |
|-------|--------|--------|
| `SafetyLimits` (pydantic) | max_rows=1000, max_execution_seconds=30.0, max_result_bytes=5_000_000 | `core/config.py` (env-overridable) |
| `SafetyResult` (pydantic) | allowed: bool, reason?, normalized_sql? | `core/sql_safety.py` |
| `LLMConfig` (dataclass) | provider?, model?, api_key?, base_url? | `core/llm/base.py`; None fields → env fallback |
| `NLSQLResult` (dataclass) | sql, explanation?, confidence? | `core/llm/base.py` — output of `generate_sql_from_nl` |
| `Confidence` (dataclass) | level ("High"/"Medium"/"Low"), reasons[] | `core/llm/base.py` (heuristic) |
| `LLMProvider` (Protocol) | name; is_available(); resolve_model(); complete() | `core/llm/base.py`; impls `ExternalLLMProvider`, `LocalLLMProvider` (stub) |

## 4. Schema metadata (`src/schema.py`)

| Model | Fields |
|-------|--------|
| `ColumnDefinition` | table_name, column_name, data_type?, is_primary_key, is_foreign_key, references_table?, references_column? |
| `RelationshipDefinition` | from_table, from_column, to_table, to_column, relationship_type? |
| `TableDefinition` | name, columns[] |
| `Schema` | tables{name→TableDefinition}, relationships[] |

**Upload formats:** schema CSV columns = `table_name, column_name, data_type, is_primary_key, is_foreign_key, references_table, references_column`; relationships CSV = `from_table, from_column, to_table, to_column, relationship_type`.

## 5. Persistence formats (`STORAGE_DIR`)

| File | Shape | Sensitivity |
|------|-------|-------------|
| `profiles.json` | `{ profile_id: StoredProfile }` | Password **encrypted**; file git-ignored. |
| `reports.json` | `{ report_name: { sql } }` | SQL text (no creds). |
| `connection.json` | single manual connection (legacy) | **Contains plaintext password** — git-ignored; candidate for migration to profiles (see [issue-log](issue-log.md)). |

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Baseline catalogue of Phase-2 models. |
