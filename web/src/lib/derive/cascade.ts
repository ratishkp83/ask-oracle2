import { ColumnMeta } from "./columns";
import { SqlMeta } from "./sql";

// The drill-stack model behind multi-level cascading. A cascade is just an
// ordered stack of (dimension, value) filters: each level narrows the rows and
// the next breakdown descends to the next dimension. Everything here is pure and
// local — it reads only the already-fetched rows + the local column/SQL metadata
// and sends nothing anywhere. The chart, KPIs, and grid re-scope off these.

export interface DrillLevel {
  dimIndex: number; // result column index of the grouping dimension
  value: string; // the selected value (stringified, matching chart group keys)
}

// Ordered breakdown-dimension column indices for cascading. A dimension is any
// non-measure, non-id column (categorical or date). When the proposed SQL read
// cleanly with a GROUP BY, dimensions descend in GROUP BY order — the analyst's
// intended hierarchy (region → customer → …); otherwise they fall back to column
// (SELECT) order. Pure; never throws.
export function dimensionOrder(cols: ColumnMeta[], sqlMeta?: SqlMeta | null): number[] {
  const dims = cols.filter((c) => !c.isMeasure && c.type !== "id");
  const useGroupBy =
    !!sqlMeta && sqlMeta.reliable && sqlMeta.hasGroupBy && sqlMeta.groupBy.length > 0;
  if (!useGroupBy) return dims.map((c) => c.index);

  const gb = sqlMeta!.groupBy; // normalized, UPPERCASE expressions
  const outputs = sqlMeta!.outputs;
  const rankOf = (c: ColumnMeta): number => {
    const name = c.name.toUpperCase();
    const alias = outputs.length === cols.length ? outputs[c.index]?.alias ?? null : null;
    const pos = gb.findIndex(
      (g) => g === name || (alias != null && g === alias) || g.endsWith("." + name),
    );
    // Unmatched dimensions sort after matched ones, preserving column order.
    return pos === -1 ? gb.length + c.index : pos;
  };
  return dims
    .slice()
    .sort((a, b) => rankOf(a) - rankOf(b))
    .map((c) => c.index);
}

// Rows matching every active drill level (AND down the stack). Compares the
// stringified cell to the level's value, matching how the chart derives its
// group-key labels (see chart.ts `aggregate`).
export function filterRows(rows: unknown[][], stack: DrillLevel[]): unknown[][] {
  if (stack.length === 0) return rows;
  return rows.filter((r) => stack.every((d) => String(r[d.dimIndex]) === d.value));
}

// The next breakdown dimension to descend into: the first ordered dimension not
// already drilled. null when the stack has exhausted every dimension — the leaf
// of the cascade, where "pull live detail" takes over.
export function nextDimension(order: number[], stack: DrillLevel[]): number | null {
  const used = new Set(stack.map((d) => d.dimIndex));
  for (const idx of order) if (!used.has(idx)) return idx;
  return null;
}
