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

// Per-entity measures — an attribute of one record (a person's pay), NOT additive
// across distinct records. In a record list (e.g. "top earner per department")
// summing them is meaningless, so roll up by MAX. Additive measures (amount /
// revenue / balance / sales) still sum to an honest Total (e.g. total outstanding
// AR across customers). Heuristic — extend as real cases appear.
const PER_ENTITY_MEASURE = /(salary|salaries|wage|stipend|compensation)/i;

export function deriveKpis(rows: unknown[][], cols: ColumnMeta[]): Kpi[] {
  const ranked = rankMeasures(cols);
  if (ranked.length === 0 || rows.length === 0) return [];

  // A non-measure column means the rows are records (one per entity). An
  // un-aggregated *per-entity* measure (salary) must NOT be summed across them —
  // roll up by MAX. Additive measures and flat lists still sum to a Total.
  const isRecordList = cols.some((c) => !c.isMeasure);

  return ranked.slice(0, 4).map((c) => {
    const nums: number[] = [];
    for (const r of rows) {
      const v = r[c.index];
      if (v === null || v === undefined || v === "") continue;
      const num = toNumber(v);
      if (Number.isFinite(num)) nums.push(num);
    }
    const count = nums.length;
    // The SQL aggregation wins. For an un-aggregated measure (a list of records —
    // no GROUP BY / no agg function) we must NOT default to SUM: adding a measure
    // across distinct records (e.g. salaries of two different people) is
    // meaningless. Default to MAX (the extreme the user usually wants), unless the
    // name signals an average. Only a real SQL SUM/COUNT yields a "Total" tile.
    const agg: Agg =
      c.agg ??
      (AVG_HINT.test(c.name.toLowerCase())
        ? "avg"
        : isRecordList && PER_ENTITY_MEASURE.test(c.name)
          ? "max"
          : "sum");
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
