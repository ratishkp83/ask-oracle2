# ADR-001 — Layered SQL safety engine (sqlglot + denylist)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product owner, Engineering

## Context
The core product guarantee is read-only (SELECT/CTE) execution against production
Oracle. The original check (`startswith("select ")`/`"with "`) was both too weak
(missed stacked statements, `FOR UPDATE`, PL/SQL, DML in subqueries) and buggy
(rejected valid SQL with a newline/paren after `SELECT`).

## Decision
Implement a single, layered, **fail-closed** enforcer (`core/sql_safety.py`):
1. Parse with sqlglot (Oracle dialect); reject parse failures and multiple statements.
2. Require a read-only root (SELECT / UNION / INTERSECT / MINUS / parenthesised SELECT; CTE allowed).
3. Reject any DML/DDL/PL-SQL node anywhere in the AST, and `FOR UPDATE` locks.
4. Apply a whole-word keyword denylist over normalised, comment- and literal-stripped SQL as a backstop.

## Consequences
- Strong, multi-layer protection; testable accept/reject matrix (24 cases).
- Fail-closed may reject exotic-but-valid Oracle SQL (accepted tradeoff — see [RISK-06](../risk-register.md)).
- Adds a `sqlglot` dependency.

## Alternatives considered
- **Parser-only:** clean but a single library is the only line of defense.
- **Denylist-only:** no new dependency, but weaker against obfuscation and dialect quirks.
