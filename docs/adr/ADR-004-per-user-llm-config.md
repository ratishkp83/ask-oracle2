# ADR-004 — Per-user LLM configuration, per-session (no auth yet)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product owner, Engineering

## Context
Users want to choose their own LLM provider/model and supply their own API key,
rather than relying on a single server-wide key. The app currently has no
authentication/identity layer.

## Decision
Introduce `nl2sql.LLMConfig(provider, model, api_key, base_url)`; any omitted
field falls back to server env config. The Streamlit **Settings** screen stores a
user's choice in **session state only** (never written to disk); the API accepts
an optional `llm` override on `/nl2sql`. Keys are used transiently and are never
logged or persisted. Given no accounts, "per user" = **per session**.

## Consequences
- Immediate per-user customization with zero new infrastructure.
- Seeds the Phase-3 `LLMProvider` abstraction.
- Not true multi-tenant isolation ([RISK-07](../risk-register.md)); persisted per-account keys require an identity layer (future, can reuse ADR-002 encryption).

## Alternatives considered
- **Persisted shared store:** without accounts it is effectively one shared config, not per-user.
- **Add auth now:** larger scope; deferred to a dedicated phase.
