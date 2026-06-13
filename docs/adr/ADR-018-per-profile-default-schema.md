# ADR-018 — Per-profile default schema (ALTER SESSION SET CURRENT_SCHEMA)

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Product/Engineering (owner-requested during the v2 Phase-8 UI demo)
- **Phase:** v2 (post-Phase-8 enhancement)

## Context
The recommended deployment is a **least-privilege, read-only account** ([ADR-009](ADR-009-readonly-db-account-precondition.md))
that holds `SELECT` **grants** on a separate business schema (e.g. `aor_readonly` with grants on
`AOR_DEMO`). Under that account, **unqualified** table names resolve against the *login's own*
schema, not the granted one — so `SELECT … FROM employees` raises **ORA-00942** unless every table
is written `AOR_DEMO.employees`. NL→SQL (and hand-written SQL) naturally emit unqualified names, so
**every query failed** for the product's own recommended setup (surfaced live in the Phase-8 demo).

Two fixes were considered: (1) make NL→SQL owner-qualify table names; (2) set the session's default
schema so bare names resolve. The owner chose **(2)** as the cleaner option — it fixes *all* SQL
(NL **and** hand-written) at the connection layer, with no per-query dependency on the model.

## Decision
Add an **optional `current_schema`** to a connection (config + profile). When set, the client runs
**`ALTER SESSION SET CURRENT_SCHEMA = <schema>`** immediately after connecting, so unqualified
names resolve against that schema for the session.

- **Config/profile:** `OracleConnectionConfig.current_schema` (db.py) and `current_schema` on
  `ProfileCreate`/`ProfilePublic`/`StoredProfile`/`ResolvedConnection` (profiles.py); optional,
  defaults `None` (so existing profile records load unchanged — backward compatible). UI field
  "Default schema (optional)" on both the manual sidebar connection and the add-profile form.
- **Where it runs:** `OracleClient._connect()`, once per connection, before any user query.

## Security
- **`ALTER SESSION SET CURRENT_SCHEMA` is a session setting — it changes name resolution, not data.**
  It cannot modify rows, escalate privilege, or run DML/DDL on the schema. It is therefore safe to
  execute as a **connection-init** statement, **outside** the SELECT-only user-query chokepoint
  (`run_select`), which is unchanged. The "no data modification" guarantee is unaffected.
- **Injection control:** a schema name **cannot be a bind variable**, so the value is interpolated
  into the statement. `validate_schema_name()` (db.py) restricts it **fail-closed** to the Oracle
  identifier charset (`^[A-Za-z][A-Za-z0-9_$#]*$`, ≤128 chars); anything else (spaces, quotes,
  `;`, `.`, `-`, leading digit, …) raises `SqlSafetyError` **before** the string is built. So a
  hostile value like `AOR_DEMO; DROP TABLE x` is rejected, never executed.
- The schema name is **not a secret** — it appears in `ProfilePublic` and may be logged; only the
  password remains encrypted/never-returned.

## Consequences
- The product works out-of-the-box under its own recommended ADR-009 grant-based read-only account:
  NL→SQL and hand-written SQL run with **unqualified** names. Verified live against XE 21c — an
  unqualified `SELECT … FROM employees …` returned rows under `aor_readonly` with
  `current_schema=AOR_DEMO`.
- Backward compatible: profiles without the field behave exactly as before (no ALTER SESSION).
- Tests: `tests/test_current_schema.py` (identifier validation incl. injection, connect-time ALTER
  SESSION, profile round-trip, legacy-record load) — **401 tests** total.

## Alternatives considered
- **Owner-qualify in NL→SQL** (option 1): rejected as the primary fix — only helps model-generated
  SQL (not hand-written), depends on the prompt/context carrying owners, and is per-query. A useful
  complement later, but (2) is the clean connection-layer fix.
- **Require fully-qualified names from users:** rejected — poor UX and defeats NL→SQL.

## Notes
- Surfaced while remediating [BUG-007](../issue-log.md) (NL→SQL Oracle dialect) in the v2 Phase-8 demo.
- Pairs with [ADR-009](ADR-009-readonly-db-account-precondition.md) (read-only grant-based account).
