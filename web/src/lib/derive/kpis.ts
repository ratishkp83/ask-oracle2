import { ColumnMeta, rankMeasures } from "./columns";
import { Agg } from "./sql";
import { foldAgg } from "./aggregate";
import { formatCompact, formatInt, formatNumber, formatPercent, humanize, toNumber } from "@/lib/format";

export interface Kpi {
  label: string;
  value: string; // formatted figure
  context: string; // honest provenance, e.g. "Total · 12 values" — never a fabricated delta
}

// Fallback only (no SQL agg): rates/durations/averages average; everything sums.
const AVG_HINT = /(pct|percent|rate|ratio|margin|avg|average|days|age|score|price)/;

export function deriveKpis(rows: unknown[][], cols: ColumnMeta[]): Kpi[] {
  const ranked = rankMeasures(cols);
  if (ranked.length === 0 || rows.length === 0) return [];

  return ranked.slice(0, 4).map((c) => {
    const nums: number[] = [];
    for (const r of rows) {
      const v = r[c.index];
      if (v === null || v === undefined || v === "") continue;
      const num = toNumber(v);
      if (Number.isFinite(num)) nums.push(num);
    }
    const count = nums.length;
    // The SQL aggregation wins; the name heuristic is the fallback for raw
    // detail columns (SELECT *, expressions) where the SQL couldn't be read.
    const agg: Agg = c.agg ?? (AVG_HINT.test(c.name.toLowerCase()) ? "avg" : "sum");
    const raw = foldAgg(nums, agg);
    return {
      label: humanize(c.name),
      value: formatMeasure(raw, c, agg),
      context: contextFor(agg, count, c.agg != null),
    };
  });
}

function formatMeasure(raw: number, c: ColumnMeta, agg: Agg): string {
  if (c.type === "percent") return formatPercent(raw);
  if (c.type === "currency") return formatCompact(raw, true);
  if (agg === "avg") {
    return c.isInteger ? formatInt(raw) : formatNumber(Math.round(raw * 10) / 10);
  }
  return formatCompact(raw, false);
}

function contextFor(agg: Agg, count: number, fromSql: boolean): string {
  const n = count.toLocaleString();
  const values = `${n} value${count === 1 ? "" : "s"}`;
  switch (agg) {
    case "avg":
      // Honest about the roll-up: across pre-aggregated groups it's an average of
      // group values, not a true weighted mean (Decision 2).
      return fromSql ? `Average across ${n} group${count === 1 ? "" : "s"}` : `Average · ${values}`;
    case "min":
      return `Minimum · ${values}`;
    case "max":
      return `Maximum · ${values}`;
    case "count":
    case "sum":
    default:
      return `Total · ${values}`;
  }
}
