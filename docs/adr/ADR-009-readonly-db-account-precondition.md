# ADR-009 — A least-privilege read-only DB account is a required deployment precondition

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Product/Engineering
- **Phase:** 4 (raised by independent review r1, finding F1)

## Context
The central safety layer (`assert_safe_select`, [ADR-001](ADR-001-sql-safety-engine.md))
is a **parse-based allowlist**: it proves a statement *is* a single read-only
SELECT/CTE and rejects DML/DDL/PL-SQL/stacked/`FOR UPDATE`. But static parsing cannot
prove a SELECT has **no side effects**: a SELECT may invoke a PL/SQL function that does
I/O or performs an **autonomous-transaction** DML (e.g. `SELECT my_writer_fn() FROM dual`,
`SELECT DBMS_LOCK.SLEEP(1) FROM dual`). This is an inherent limit of *any* parse-based
gate. Review r1 (F1) verified `assert_safe_select("SELECT DBMS_LOCK.SLEEP(1) FROM dual")`
is allowed. The product's vision (D1 §6) markets "no data modification of any kind" as a
permanent guarantee — which the application layer alone cannot deliver.

## Decision
The read-only guarantee is delivered by **defense in depth**, and the database account is
a **non-negotiable deployment precondition**:

1. **Application layer** — the SELECT/CTE-only safety chokepoint ([ADR-001](ADR-001-sql-safety-engine.md))
   + bind-variable parameterization ([ADR-007](ADR-007-parameterized-reports-bind-variables.md)).
   The tool only ever *issues* read-only SELECT/CTE statements.
2. **Database layer (required)** — Ask Oracle Reports must connect with a **least-privilege,
   read-only Oracle account**: `CREATE SESSION` + `SELECT` (or read-only) on the target
   objects only; **no** `INSERT/UPDATE/DELETE`, **no** `EXECUTE` on side-effecting packages
   (`DBMS_LOCK`, `DBMS_SCHEDULER`/`DBMS_JOB`, `UTL_FILE`/`UTL_HTTP`/`UTL_SMTP`/`UTL_TCP`,
   `DBMS_AQ`, …). With this account, even a SELECT that *tries* to invoke a writing
   function fails at the database on privilege — so "no data modification" holds.

This precondition is documented in the [Deployment Plan](../07-deployment-plan.md) and
referenced from the Product Vision and Architecture. Optionally, a package/function
denylist may be added at the parse layer as *additional* defense-in-depth — it does **not**
replace the account requirement and is deferred unless the owner requests it.

## Consequences
- The marketed guarantee is honest and enforceable: parse gate ⇒ "only SELECTs issued";
  read-only account ⇒ "those SELECTs cannot write."
- Ops/onboarding must provision the read-only account; this is now a checklist item.
- The app cannot, by parsing alone, guarantee side-effect-freedom; this ADR records why
  the account is mandatory rather than optional.

## Alternatives considered
- **Parse-time function denylist as the sole control:** rejected — fragile and incomplete
  (cannot cover user-defined side-effecting functions), and gives false assurance.
- **Leave the precondition implicit:** rejected — it is the actual control behind a
  marketed guarantee and must be explicit (the F1 gap).
