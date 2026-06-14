import { ColumnMeta, rankMeasures } from "./columns";
import { toNumber } from "@/lib/format";

export interface ChartSpec {
  type: "bar" | "line";
  data: { label: string; value: number }[];
  measureName: string;
  dimensionName: string;
  currency: boolean;
  extra: number; // count folded out of a top-N bar chart ("+N more")
}

const MAX_BARS = 6;
const MAX_POINTS = 60;

// Pick a sensible driver chart from the result shape, or null (band hides).
// date dimension + measure → trend line; category + measure → top-N bar.
export function pickChart(rows: unknown[][], cols: ColumnMeta[]): ChartSpec | null {
  if (rows.length < 2) return null;
  const measure = rankMeasures(cols)[0];
  if (!measure) return null;

  const dateCol = cols.find((c) => c.type === "date");
  if (dateCol) {
    const data = aggregate(rows, dateCol.index, measure.index).slice(0, MAX_POINTS);
    if (data.length >= 2) {
      return spec("line", data, measure, dateCol, 0);
    }
  }

  const catCol = cols.find((c) => c.type === "category");
  if (catCol) {
    const all = aggregate(rows, catCol.index, measure.index).sort((a, b) => b.value - a.value);
    const top = all.slice(0, MAX_BARS);
    if (top.length >= 2) {
      return spec("bar", top, measure, catCol, Math.max(0, all.length - top.length));
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
  return { type, data, measureName: measure.name, dimensionName: dim.name, currency: measure.type === "currency", extra };
}

function aggregate(rows: unknown[][], dimIdx: number, measIdx: number): { label: string; value: number }[] {
  const map = new Map<string, number>();
  for (const r of rows) {
    const key = r[dimIdx] == null || r[dimIdx] === "" ? "—" : String(r[dimIdx]);
    const v = toNumber(r[measIdx]);
    if (!Number.isFinite(v)) continue;
    map.set(key, (map.get(key) ?? 0) + v);
  }
  return Array.from(map, ([label, value]) => ({ label, value }));
}
