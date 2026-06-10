# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/); the project predates formal semantic versioning, so entries are grouped by delivery phase.

## [Unreleased]

### Added
- **Governance baseline (P2.5):** full `/docs` governed set (Vision, BRD/PRD, Architecture, Data Models, API Contracts, Test Strategy, Deployment Plan), ADR log, Risk Register, Task Tracker, Issue Log, Traceability Matrix, Roadmap, and this changelog.
- Git version control initialized for the repository.
- GitHub Actions CI running the test suite (`.github/workflows/ci.yml`).

## [Phase 2 — Hardened Connectivity & Safety] - 2026-06-10

### Added
- `src/core/` package: `sql_safety` (layered, fail-closed SELECT/CTE enforcement via sqlglot + denylist), `config` (`SafetyLimits`), `crypto` (Fernet), `profiles` (encrypted connection profiles + pluggable store), `audit` (secret-free logging).
- API: `/profiles` CRUD + `/profiles/{id}/test`; `/execute` as the single safety chokepoint (accepts `profile_id` or inline `connection`; returns `truncated`).
- Per-user LLM customization: `nl2sql.LLMConfig` (provider/model/key, env fallback) + `/nl2sql` `llm` field.
- Streamlit: **Connections** screen, profile-aware "Active Connection" sidebar, **Settings** screen (per-session LLM).
- Tests: 48 automated tests (safety, profiles, execute endpoint, LLM config).
- `requirements-dev.txt`; `sqlglot` + `cryptography` dependencies.

### Changed
- `db.py`: `run_select()` enforces row/time/result-size limits; `execute_query()` retained as a back-compat wrapper.
- `nl2sql.py`: removed duplicate safety check; uses the central layer.
- README, `.env.example`, `ask-oracle-techspec.md`: updated for the above.

### Security
- **Removed committed API keys** from `docker-compose.yml` and `src/api.py`; switched compose to `env_file`.
- `.gitignore`: now ignores `.env`, `storage/`, `__pycache__/`, `.venv/`.
- ⚠️ Previously committed Groq/OpenAI keys must be **rotated** (see [RISK-01](risk-register.md)).

## [Phase 1 — Productization] - prior

- Initial product: Streamlit + FastAPI + React scaffold; NL→SQL (Groq/OpenAI); schema upload; basic reports/export.
