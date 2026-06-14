import { NULL_KEY } from "./cascade";

// A single active drill filter: an output column of the approved result and the
// selected value. NULL_KEY ("—") means the source value was NULL/empty.
export interface PullFilter {
  column: string;
  value: string;
}

export interface PullDetailQuery {
  sql: string;
  binds: Record<string, unknown>;
}

// Quote an Oracle identifier, escaping embedded double-quotes. We quote the exact
// driver-returned column name so the predicate references the inline view's output
// column without case-folding surprises.
function quoteIdent(name: string): string {
  return `"${name.replace(/"/g, '""')}"`;
}

// Decision 3 — live "Pull <value> data": deterministically wrap the already-approved
// SELECT and filter it to the active drill path, so we re-fetch that exact slice
// LIVE from the database (fresh, un-truncated) without a new LLM call. Values are
// bound (never interpolated); a NULL bucket becomes `IS NULL`. The result is still
// a plain SELECT, so the SELECT-only chokepoint keeps enforcing read-only. The user
// re-approves it in the review step before it runs (invariant 2).
//
// Type assumption (load-bearing): `filters` only ever carry CATEGORICAL or NUMERIC
// drill dimensions, so binding a stringified value works (Oracle implicit-converts
// for NUMBER). DATE dimensions render as non-drillable trend lines and never enter
// the drill stack, so a string value is never bound against a DATE column (which
// would mismatch the NLS format). If dates ever become drillable, bind them typed.
export function buildPullDetailSql(approvedSql: string, filters: PullFilter[]): PullDetailQuery {
  // Drop a trailing statement terminator so it nests cleanly as an inline view.
  const inner = approvedSql.replace(/[;\s]+$/, "");
  const binds: Record<string, unknown> = {};
  const predicates: string[] = [];
  filters.forEach((f, i) => {
    const col = quoteIdent(f.column);
    if (f.value === NULL_KEY) {
      predicates.push(`${col} IS NULL`);
    } else {
      const p = `p${i}`;
      predicates.push(`${col} = :${p}`);
      binds[p] = f.value;
    }
  });
  const where = predicates.length ? `\nWHERE ${predicates.join("\n  AND ")}` : "";
  const sql = `SELECT * FROM (\n${inner}\n)${where}`;
  return { sql, binds };
}
