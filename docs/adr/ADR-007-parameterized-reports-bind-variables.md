# ADR-007 — Parameterized reports use bind variables (never interpolation)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product/Engineering
- **Phase:** 4 (Reports, Templates & UX)

## Context
Phase 4 makes saved reports and templates **parameterized**. A naive implementation
would substitute parameter values into the SQL string before execution. That would
let a value carry SQL structure (`'; DELETE …`, stacked statements, comment tricks)
and could defeat the SELECT/CTE-only guarantee enforced by `core.sql_safety` — the
product's central non-negotiable.

## Decision
Parameters are passed to Oracle as **bind variables** (`:name`) and handed to the
driver as **values**, never spliced into the SQL text:

- `OracleClient.run_select(sql, limits, binds)` calls `cur.execute(sql, binds)`; the
  SQL string is unchanged by the values.
- `assert_safe_select(sql)` still runs **first**, on the text — binds cannot alter the
  parsed statement, so the safety verdict is independent of parameter values.
- `validate_binds(binds)` (in `src/db.py`) is a fail-closed backstop at the chokepoint:
  bind names must match `^[A-Za-z_][A-Za-z0-9_]*$` (≤30 chars) and values must be
  scalars (`str`/`int`/`float`/`bool`/`None`/`date`/`datetime`); dicts/lists/objects
  are rejected.
- `coerce_report_binds(parameters, raw_values)` (in `src/core/reports.py`) applies
  defaults, enforces `required`, coerces to the declared type, and rejects unknown keys
  before values reach `validate_binds`.
- **Scalar binds only** in v1; `IN (:list)` multi-value expansion is deferred (charter D-B).

## Consequences
- Parameter values are inert: a value such as `'; DROP TABLE x; --` is bound as a string
  literal and cannot change the statement (covered by `tests/test_bind_safety.py`).
- The single execution chokepoint (ADR-005) is preserved; `/execute` and
  `/reports/{id}/run` share the same safety + bind path.
- List/multi-value parameters require a follow-up design (safe expansion of `IN`).

## Alternatives considered
- **String interpolation / templating of values:** rejected — reintroduces injection and
  can bypass the SELECT-only check.
- **Allowing arbitrary bind value types:** rejected — non-scalars add surface with no
  reporting benefit in v1.
