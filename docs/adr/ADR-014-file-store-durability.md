# ADR-014 — File-store durability (atomic JSON writes; corrupt-record quarantine)

- **Status:** Accepted
- **Date:** 2026-06-11
- **Deciders:** Product/Engineering (Phase 6.5 charter D-D/D-E, owner-approved)
- **Phase:** 6.5 (Pre-Deployment Hardening)

## Context
All four JSON stores — `storage.py` (legacy connection config), `core/profiles.py`,
`core/reports.py`, `core/schema_store.py` — persisted by truncating and rewriting the target
file in place under a per-process lock. A crash mid-write could leave a torn, unparseable
file (**ITM-013 / RISK-16**); and in the report store a single malformed v2 record raised an
uncaught `ValidationError`, turning `list`/`get` into a 500 (**ITM-014**). Both matter the
moment the product runs anywhere less forgiving than a developer laptop.

## Decision
1. **Shared atomic write** (`src/core/fileio.py::atomic_write_json`): serialize to a temp
   file created in the **same directory** as the target, `flush` + `os.fsync`, then
   `os.replace` — atomic on POSIX and Windows because the swap stays on one volume. On any
   failure the target is untouched and the temp is removed. All four stores adopt the helper;
   the on-disk JSON shape (`indent=2`, per-store `default=`) is unchanged.
2. **Keep JSON, defer SQLite** (charter D-D): the helper solves crash-corruption with a
   minimal blast radius. Cross-*process* concurrency is not solved and remains the documented
   **one-worker-per-store-directory** deployment constraint (D7); SQLite is the revisit point
   when a multi-worker deployment is actually planned.
3. **Corrupt-record quarantine** (charter D-E, ITM-014 — implemented in build step B4): a
   record that fails validation is **skipped from serving and logged** (keyed by `error_id`,
   record *key* only — never the body, which can embed SQL), but is **preserved verbatim on
   save** so a subsequent write cannot silently drop it. Availability wins over fail-closed:
   one bad record must not take down every saved report.

## Consequences
- An interrupted write leaves either the old or the new complete file — never a torn one;
  proven by `tests/test_fileio.py` (failed-write-keeps-old-content, no temp residue).
- Store code shrinks: `makedirs` + open/dump boilerplate collapses into one helper call.
- Quarantined records survive until an operator repairs the file; `list`/`get` keep serving
  good records; `get`/`update`/`delete` on a quarantined id behave as "not found".
- `fsync` on every save is a real (tiny) cost per write — acceptable at this write rate.

## Alternatives considered
- **SQLite-backed stores:** also solves multi-worker concurrency and partial-write torn
  states, but a much larger migration (schema, locking semantics, backup story) than the
  risk warrants today (D-D).
- **File locking (e.g. `msvcrt`/`fcntl`) for multi-worker:** platform-divergent and easy to
  get wrong; out of scope while the deployment is single-worker by contract.
- **Fail-closed on corrupt records:** safer-sounding, but one bad record would disable the
  whole store — a full outage of saved reports to protect data that is already broken (D-E).

## Notes
- Documented in D3 (module table) and D7 (single-worker constraint). Closes **ITM-013**
  (with B4 closing **ITM-014**); tests in `tests/test_fileio.py` + the malformed-store tests.
