# ADR-029 — Plan-aware NL→SQL generation, static pre-flight, local value resolution

- **Status:** Proposed (B2 — awaiting owner sign-off)
- **Date:** 2026-06-18
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 11 (Pillar 1b, B4)

## Context
The base analytical SQL is **LLM-authored** (`generate_sql_from_nl`). Its quality is capped today by (a) a blunt **12 000-char truncation** of the schema context (`build_external_context`) that silently drops tables on large schemas, (b) no performance awareness, and (c) value-encoding blindness (`status='Active'` when the column stores `'A'`). We must improve generation **without** sending row data to the model (Invariant 3) and **without** widening the SELECT-only chokepoint (Invariant 1). Profiling (ADR-028) supplies the raw material.

## Decision
Three local, deterministic additions around the existing generator:

1. **Schema linking (relevant-subset selection)** — `select_relevant_tables(schema, question, semantics, budget)` ranks tables by lexical overlap (question + glossary terms) and expands along the FK graph to include directly-joined neighbors, capped to a budget. Replaces the blunt 12k truncation, so large schemas still present the *right* tables. Pure, never throws, falls back to "all" when it already fits.
2. **Performance brief** — `build_performance_brief(schema)` appends a compact, **names/magnitudes-only** brief (size class, indexed columns, partition key, fan-out joins) to the external context (before the `assert_no_values` tripwire), plus a `SYSTEM_PROMPT` directive to prefer indexed/partition-key predicates, include the partition key for large partitioned tables, drive from the smaller table, and aggregate in SQL.
3. **Static pre-flight heuristics** — `src/core/sql_plan.py` analyzes the **proposed** SQL's sqlglot AST for `CARTESIAN` / `FACT_SCAN` / `MISSING_PARTITION_PREDICATE` / `UNFILTERED_LARGE`, returning advisory `PlanWarning`s shown in the review step. **Never blocks.**
4. **Local value-domain resolution** — `resolve_value_literals(sql, schema, semantics)` rewrites an equality/IN literal that matches a domain **label** to its **code** (`'Active'`→`'A'`), recording a `Correction` the user sees in review. Conservative (confident matches only); output re-validated by `assert_safe_select`. **No values to the model.**

## Consequences
- Large schemas become tractable; queries steer onto indexed/partitioned columns → fewer timeouts (works with ADR-030).
- The `status='A'` class of silent wrong-answers is fixed **without** relaxing Invariant 3 — the fix is a deterministic server-side rewrite, surfaced for approval (Invariant 2).
- Static heuristics are cheap and always-on; the optional real-plan path (ADR-031) is a later fidelity upgrade.
- Generation stays LLM-authored; the durable shift to deterministic composition is the Phase-12 semantic layer.

## Security / invariants
- **Invariant 1:** no SQL is executed here; rewrites are re-checked by `assert_safe_select`; the chokepoint is unchanged.
- **Invariant 2:** value-domain corrections and any self-heal (ADR-030/charter D-H) surface in the editable review for approval.
- **Invariant 3:** only Channel-A names/magnitudes enter the prompt (covered by `assert_no_values`); value domains are used locally and never sent.

## Alternatives considered
- **Send sample column values to the model** (the mainstream text-to-SQL trick): rejected — violates Invariant 3 and the redaction tripwire; the local rewrite achieves the same accuracy without egress.
- **Raise the truncation limit / send the whole catalog:** rejected — doesn't scale and wastes tokens; schema linking is the standard, effective answer.
- **Block on static warnings:** rejected — advisory only; the user (or Auto-run) decides, and the chokepoint remains the hard boundary.
