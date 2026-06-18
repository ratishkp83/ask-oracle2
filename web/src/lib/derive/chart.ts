import { ColumnMeta, rankMeasures } from "./columns";
import { Agg } from "./sql";
import { dimKey } from "./cascade";
import { toNumber } from "@/lib/format";

export interface ChartSpec {
  type: "bar" | "line";
  data: { label: string; value: number }[];
  measureName: string;
  dimensionName: string;
  dimensionIndex: number; // the column the chart groups by (for drill-down)
  currency: boolean;
  extra: number; // count folded out of a top-N bar chart ("+N more")
}

const MAX_BARS = 6;
const MAX_POINTS = 60;

// Pick a sensible driver chart from the result shape, or null (band hides).
// Dimensions come from the SQL when known (GROUP BY keys, including numeric ones
// like FISCAL_YEAR) via ColumnMeta.isMeasure; otherwise from the name+value
// heuristics. date dimension + measure → trend line; other dimension + measure →
// top-N bar. `exclude` skips dimension columns already drilled into. `order`, when
// supplied (multi-level cascade), descends in that order: the breakdown is the
// first ordered, non-excluded dimension — its type still decides the visual.
export function pickChart(
  rows: unknown[][],
  cols: ColumnMeta[],
  exclude: number[] = [],
  order?: number[],
): ChartSpec | null {
  if (rows.length < 2) return null;
  const measure = rankMeasures(cols)[0];
  if (!measure) return null;
  // A chart aggregates the measure *within each dimension value* (a grouping), so
  // SUM is the right default — daily/regional totals are meaningful, and for a
  // record list with unique keys sum == the per-record value anyway. (The KPI
  // tiles, which roll up across ALL rows, are where an un-aggregated SUM misleads.)
  const agg: Agg = measure.agg ?? "sum";

  const dims = cols.filter((c) => !c.isMeasure && c.type !== "id" && !exclude.includes(c.index));
  if (dims.length === 0) return null;

  if (order && order.length) {
    // Descend in cascade order, skipping any dimension that's constant in the
    // current scope (one value → not a useful breakdown, and it's already implied
    // by the active filters). Return the first dimension that actually splits the
    // data, so the cascade reaches real detail instead of dead-ending early.
    for (const idx of order) {
      const dim = dims.find((d) => d.index === idx);
      if (!dim) continue;
      const c = chartForDim(rows, dim, measure, agg);
      if (c) return c;
    }
    return null;
  }

  const dateDim = dims.find((c) => c.type === "date");
  if (dateDim) {
    const lineSpec = chartForDim(rows, dateDim, measure, agg);
    if (lineSpec) return lineSpec; // else fall through to a categorical driver
  }

  const catDim = dims.find((c) => c.type !== "date");
  if (catDim) return chartForDim(rows, catDim, measure, agg);
  return null;
}

// Render one chosen dimension against the measure: a date → trend line, anything
// else → top-N bar. Returns null when fewer than 2 points/bars survive.
function chartForDim(
  rows: unknown[][],
  dim: ColumnMeta,
  measure: ColumnMeta,
  agg: Agg,
): ChartSpec | null {
  if (dim.type === "date") {
    const data = aggregate(rows, dim.index, measure.index, agg).slice(0, MAX_POINTS);
    return data.length >= 2 ? spec("line", data, measure, dim, 0) : null;
  }
  const all = aggregate(rows, dim.index, measure.index, agg).sort((a, b) => b.value - a.value);
  const top = all.slice(0, MAX_BARS);
  return top.length >= 2 ? spec("bar", top, measure, dim, Math.max(0, all.length - top.length)) : null;
}

function spec(
  type: "bar" | "line",
  data: { label: string; value: number }[],
  measure: ColumnMeta,
  dim: ColumnMeta,
  extra: number,
): ChartSpec {
  return {
    type,
    data,
    measureName: measure.name,
    dimensionName: dim.name,
    dimensionIndex: dim.index,
    currency: measure.type === "currency",
    extra,
  };
}

// Roll the measure up per dimension value using its aggregation (so a chart of an
// AVG/MIN/MAX column isn't silently summed). Single pass, O(n).
function aggregate(
  rows: unknown[][],
  dimIdx: number,
  measIdx: number,
  agg: Agg,
): { label: string; value: number }[] {
  const acc = new Map<string, number>();
  const counts = new Map<string, number>();
  for (const r of rows) {
    const key = dimKey(r[dimIdx]);
    const v = toNumber(r[measIdx]);
    if (!Number.isFinite(v)) continue;
    if (agg === "min") {
      acc.set(key, acc.has(key) ? Math.min(acc.get(key)!, v) : v);
    } else if (agg === "max") {
      acc.set(key, acc.has(key) ? Math.max(acc.get(key)!, v) : v);
    } else {
      acc.set(key, (acc.get(key) ?? 0) + v);
    }
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Array.from(acc, ([label, value]) => ({
    label,
    value: agg === "avg" ? value / (counts.get(label) || 1) : value,
  }));
}
