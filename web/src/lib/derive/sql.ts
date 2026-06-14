// Deterministic, fail-safe reader of a *proposed* SELECT. It reads only the SQL
// string the user already approved — it sends nothing anywhere, mirrors no row
// data, and never throws. Whenever it cannot responsibly read the query it
// returns null (or `reliable: false`) so the caller falls back to the name +
// value heuristics in columns.ts. This is NOT a SQL validator: the chokepoint in
// the backend remains the only authority on what is safe to run.
//
// Why this exists: the proposed SQL carries the exact intent the column-name
// heuristics only guess at — GROUP BY columns are dimensions; SUM/AVG/COUNT/MIN/
// MAX outputs are measures with a *known* aggregation. Using it fixes a real
// correctness bug (averaging/min/max columns were being summed across groups).

export type Agg = "sum" | "avg" | "count" | "min" | "max";

export interface SqlOutput {
  alias: string | null; // best-effort output name — a cross-check only, never the source of truth
  role: "measure" | "dimension" | "passthrough";
  agg?: Agg; // the exact aggregation when role === "measure"
}

export interface SqlMeta {
  outputs: SqlOutput[]; // one per projection item, in SELECT order (maps to result.columns by index)
  groupBy: string[]; // normalized GROUP BY expressions
  hasGroupBy: boolean;
  reliable: boolean; // false → the caller should lean on heuristics
}

const AGG_RE = /^(sum|avg|count|min|max)\s*\(/i;
const SELECT_RE = /\bselect\b/i;
const FROM_RE = /\bfrom\b/i;
const GROUPBY_RE = /\bgroup\s+by\b/i;
const GB_END_RE = /\bhaving\b|\border\s+by\b|\bunion\b|\bintersect\b|\bminus\b|\bconnect\s+by\b/i;
const SETOP_RE = /\bunion\b|\bintersect\b|\bminus\b/i;
const ALIAS_KEYWORD = /^(sum|avg|count|min|max|distinct|unique|all)$/i;

// Strip comments and blank string-literal contents so commas/parens inside them
// can't confuse projection splitting. Double-quoted identifiers are masked later.
function sanitize(sql: string): string {
  return sql
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/--[^\n]*/g, " ")
    .replace(/'(?:[^']|'')*'/g, "''");
}

// Replace everything nested inside parens (any depth) and inside double-quoted
// identifiers with spaces, preserving length and index alignment with the input.
// The result lets plain regexes find only *top-level* keywords/commas.
function maskNested(s: string): string {
  let out = "";
  let depth = 0;
  let inDq = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inDq) {
      if (c === '"') inDq = false;
      out += " ";
      continue;
    }
    if (c === '"') {
      inDq = true;
      out += " ";
      continue;
    }
    if (c === "(") {
      depth++;
      out += " ";
      continue;
    }
    if (c === ")") {
      if (depth > 0) depth--;
      out += " ";
      continue;
    }
    out += depth > 0 ? " " : c;
  }
  return out;
}

// First match of `re` in `masked` at or after `from`; null if none.
function findFrom(masked: string, re: RegExp, from: number): { start: number; end: number } | null {
  const m = re.exec(masked.slice(from));
  if (!m) return null;
  return { start: from + m.index, end: from + m.index + m[0].length };
}

// Top-level comma ranges over a masked (depth-0) slice.
function splitRanges(masked: string): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  let start = 0;
  for (let i = 0; i < masked.length; i++) {
    if (masked[i] === ",") {
      ranges.push([start, i]);
      start = i + 1;
    }
  }
  ranges.push([start, masked.length]);
  return ranges;
}

function normalize(expr: string): string {
  return expr.replace(/\s+/g, " ").trim().toUpperCase();
}

// Best-effort trailing alias of a (masked) projection item — used only as a
// label/cross-check, never to decide a column's role.
function aliasOf(masked: string): string | null {
  const m = masked.trim().replace(/\s+as\s+/i, " ");
  const toks = m.split(/\s+/).filter(Boolean);
  if (toks.length === 0) return null;
  const last = toks[toks.length - 1].replace(/"/g, "");
  if (toks.length === 1 && ALIAS_KEYWORD.test(last)) return null;
  return /^[A-Za-z_$#][\w$#]*$/.test(last) ? last.toUpperCase() : null;
}

export function parseSelectMeta(sql: string): SqlMeta | null {
  if (!sql || typeof sql !== "string") return null;
  const sanitized = sanitize(sql);
  const masked = maskNested(sanitized);

  if (/^\s*with\b/i.test(sanitized)) return null; // CTE — outermost SELECT is ambiguous to read
  if (SETOP_RE.test(masked)) return null; // compound query — column mapping is unreliable

  const selM = SELECT_RE.exec(masked);
  if (!selM) return null;
  let selEnd = selM.index + selM[0].length;
  const lead = /^\s+(distinct|unique|all)\b/i.exec(masked.slice(selEnd));
  if (lead) selEnd += lead[0].length;

  const from = findFrom(masked, FROM_RE, selEnd);
  if (!from) return null;

  const projMasked = masked.slice(selEnd, from.start);
  const projSan = sanitized.slice(selEnd, from.start);
  if (projMasked.includes("*")) return null; // SELECT * / t.* → can't map outputs to columns

  // GROUP BY (top-level only — subquery GROUP BYs are masked out).
  let groupBy: string[] = [];
  let hasGroupBy = false;
  const gb = findFrom(masked, GROUPBY_RE, from.end);
  if (gb) {
    hasGroupBy = true;
    const end = findFrom(masked, GB_END_RE, gb.end);
    const gbEnd = end ? end.start : masked.length;
    const gbMasked = masked.slice(gb.end, gbEnd);
    groupBy = splitRanges(gbMasked)
      .map(([s, e]) => normalize(sanitized.slice(gb.end + s, gb.end + e)))
      .filter(Boolean);
  }

  const outputs: SqlOutput[] = splitRanges(projMasked).map(([s, e]) => {
    const orig = projSan.slice(s, e).trim();
    const mk = projMasked.slice(s, e);
    const aggM = AGG_RE.exec(orig);
    const isWindow = /\bover\b/i.test(mk); // SUM(..) OVER (..) is per-row, not a group aggregate
    const alias = aliasOf(mk);
    if (aggM && !isWindow) {
      return { alias, role: "measure", agg: aggM[1].toLowerCase() as Agg };
    }
    // In valid SQL with a GROUP BY, every non-aggregate projection is a grouping
    // key (a dimension); without one, it's a detail/passthrough column.
    return { alias, role: hasGroupBy ? "dimension" : "passthrough" };
  });

  const reliable = hasGroupBy || outputs.some((o) => o.agg);
  return { outputs, groupBy, hasGroupBy, reliable };
}
