# ADR-003 — Secrets via environment only; remediate + rotate committed keys

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product owner, Engineering

## Context
Live Groq/OpenAI keys were committed in `docker-compose.yml`, `src/api.py`, and a
tracked `.env`. This is a production-blocking security defect.

## Decision
No secrets in source or compose. All secrets come from environment variables: a
git-ignored `.env` locally (loaded via python-dotenv) and dashboard-managed env
vars in hosted environments (Render `sync: false`). Inline keys were removed,
compose switched to `env_file`, and `.env` added to `.gitignore`.

## Consequences
- Code references only the *names* of secrets; access path (`os.getenv`) unchanged.
- File cleanup does **not** un-leak previously exposed keys → they **must be rotated** ([RISK-01](../risk-register.md)).

## Alternatives considered
- **Inline/committed keys:** rejected (the defect being fixed).
- **Secrets vault (e.g., cloud KMS/Secrets Manager):** stronger; deferred until hosting scale warrants it.
