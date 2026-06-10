# ADR-002 — Encrypt connection-profile passwords at rest (Fernet)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product owner, Engineering

## Context
Saved connection profiles must persist usable credentials while treating
passwords as secrets. Phase-1 stored a single connection in cleartext JSON.

## Decision
Persist profiles with the password **encrypted using Fernet**. The key is derived
(SHA-256) from an `APP_SECRET_KEY` env var so operators can supply any passphrase.
The API returns a `ProfilePublic` view that **has no password field**; only an
internal `ResolvedConnection` carries the decrypted password to open a connection.

## Consequences
- Convenient "save & reuse" UX without cleartext at rest.
- Requires `APP_SECRET_KEY` to be set; rotating it invalidates stored passwords ([RISK-08](../risk-register.md)).
- Pluggable `ProfileStore` allows a future SQLite/Postgres backend.

## Alternatives considered
- **Never persist password (prompt each session):** safest, more friction.
- **In-memory only:** lost on restart; not a saved-profiles product.
