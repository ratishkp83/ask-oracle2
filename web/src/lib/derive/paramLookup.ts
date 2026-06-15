import type { SchemaRecord } from "@/lib/api/schemas";

// Auto value-pickers (owner request 2026-06-15): when a report parameter has no
// explicit lookup, derive one from the report SQL + the active data dictionary.
// We map each :bind to the column it's compared against in the SQL, and if that
// column is a foreign key in the dictionary, build a value-picker SELECT against
// the referenced table. Purely heuristic and read-only — the result still runs
// through the SELECT-only chokepoint, and the run dialog falls back to a typed
// input when nothing is derived. Kept as pure functions so it's easy to test.

const COL = "[A-Za-z_][A-Za-z0-9_$#]*(?:\\.[A-Za-z_][A-Za-z0-9_$#]*)?";
const BIND = ":([A-Za-z_][A-Za-z0-9_]*)";

const lastSegmentUpper = (col: string): string => col.split(".").pop()!.toUpperCase();

// Map every bind name found in `sql` to the (unqualified, upper-cased) column it
// is compared against. Handles `col <op> :b`, `col IN (:b)`, `col BETWEEN :a AND
// :b`, and the bind-on-the-left form. First match wins per bind. Note: an
// `IN (:a, :b, …)` list only maps the FIRST bind; the rest simply fall back to a
// typed input (a safe degradation — multi-value IN binds are out of scope, cf.
// ITM-011). Exit-gate review F-2.
export function deriveBindColumns(sql: string): Record<string, string> {
  const out: Record<string, string> = {};
  const set = (bind: string, col: string) => {
    if (!(bind in out)) out[bind] = lastSegmentUpper(col);
  };

  // col BETWEEN :a AND :b  (both binds bind to the same column)
  const between = new RegExp(`(${COL})\\s+between\\s+${BIND}\\s+and\\s+${BIND}`, "gi");
  for (let m; (m = between.exec(sql)); ) {
    set(m[2], m[1]);
    set(m[3], m[1]);
  }
  // col <op> :bind   and   col IN ( :bind   and   col LIKE :bind
  const right = new RegExp(`(${COL})\\s*(?:=|>=|<=|<>|!=|>|<|(?:not\\s+)?like|(?:not\\s+)?in\\s*\\()\\s*${BIND}`, "gi");
  for (let m; (m = right.exec(sql)); ) set(m[2], m[1]);
  // :bind <op> col   (bind on the left)
  const left = new RegExp(`${BIND}\\s*(?:=|>=|<=|<>|!=|>|<)\\s*(${COL})`, "gi");
  for (let m; (m = left.exec(sql)); ) set(m[1], m[2]);

  return out;
}

type Fk = { refTable: string; refCol: string; labelCol: string };

// Index the dictionary's foreign-key columns by their (upper-cased) column name,
// choosing a *_NAME column in the referenced table as the human label when present.
export function fkByColumn(schema: SchemaRecord): Record<string, Fk> {
  const tables = schema.definition.tables;
  const map: Record<string, Fk> = {};
  for (const cols of Object.values(tables)) {
    for (const c of cols) {
      if (!c.is_foreign_key || !c.references_table) continue;
      const refTable = c.references_table;
      const refCol = c.references_column || c.column_name;
      const labelCol = (tables[refTable] ?? []).find((rc) => /name/i.test(rc.column_name))?.column_name ?? refCol;
      map[c.column_name.toUpperCase()] = { refTable, refCol, labelCol };
    }
  }
  return map;
}

// For the given report SQL + active dictionary, return bindName → derived lookup
// SELECT for every bind whose column is a foreign key. Empty when no schema.
export function buildAutoLookups(sql: string, schema: SchemaRecord | undefined | null): Record<string, string> {
  if (!schema) return {};
  const fk = fkByColumn(schema);
  const binds = deriveBindColumns(sql);
  const out: Record<string, string> = {};
  for (const [bind, col] of Object.entries(binds)) {
    const f = fk[col];
    if (f) out[bind] = `SELECT ${f.refCol}, ${f.labelCol} FROM ${f.refTable} ORDER BY ${f.labelCol}`;
  }
  return out;
}
