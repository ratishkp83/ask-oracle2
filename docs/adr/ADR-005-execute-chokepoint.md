# ADR-005 — `/execute` is the single execution chokepoint

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Engineering

## Context
Before Phase 2, the Streamlit UI executed SQL by calling `db.py` directly while
the API `/execute` was a stub — two paths, with the safety check duplicated and
inconsistent.

## Decision
Route **all** execution through one path: `OracleClient.run_select()` validates
via `core.sql_safety` and enforces `SafetyLimits`. The API `/execute` and the
Streamlit Query Builder both call it; NL→SQL also re-checks generated SQL with the
same enforcer. No second/weaker copy of the check exists.

## Consequences
- One place to audit, limit, and reason about safety.
- `execute_query()` kept as a thin back-compat wrapper for existing callers.

## Alternatives considered
- **Per-path checks:** rejected — drift and inconsistency risk (the original defect).
