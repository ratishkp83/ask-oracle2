import { ColumnMeta, rankMeasures } from "./columns";
import { Agg } from "./sql";
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
// top-N bar. `exclude` skips dimension columns already drilled into.
export function pickChart(rows: unknown[][], cols: ColumnMeta[], exclude: number[] = []): ChartSpec | null {
  if (rows.length < 2) return null;
  const measure = rankMeasures(cols)[0];
  if (!measure) return null;
  const agg: Agg = measure.agg ?? "sum";

  const dims = cols.filter((c) => !c.isMeasure && c.type !== "id" && !exclude.includes(c.index));

  const dateDim = dims.find((c) => c.type === "date");
  if (dateDim) {
    const data = aggregate(rows, dateDim.index, measure.index, agg).slice(0, MAX_POINTS);
    if (data.length >= 2) {
      return spec("line", data, measure, dateDim, 0);
    }
  }

  const catDim = dims.find((c) => c.type !== "date");
  if (catDim) {
    const all = aggregate(rows, catDim.index, measure.index, agg).sort((a, b) => b.value - a.value);
    const top = all.slice(0, MAX_BARS);
    if (top.length >= 2) {
      return spec("bar", top, measure, catDim, Math.max(0, all.length - top.length));
    }
  }
  return null;
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
    const key = r[dimIdx] == null || r[dimIdx] === "" ? "—" : String(r[dimIdx]);
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
