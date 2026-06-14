import { ColumnMeta, rankMeasures } from "./columns";
import { formatCompact, formatInt, formatNumber, formatPercent, humanize, toNumber } from "@/lib/format";

export interface Kpi {
  label: string;
  value: string; // formatted figure
  context: string; // honest provenance, e.g. "Total · 12 values" — never a fabricated delta
}

// Aggregate choice: rates/durations/averages average; everything else sums.
const AVG_HINT = /(pct|percent|rate|ratio|margin|avg|average|days|age|score|price)/;

export function deriveKpis(rows: unknown[][], cols: ColumnMeta[]): Kpi[] {
  const ranked = rankMeasures(cols);
  if (ranked.length === 0 || rows.length === 0) return [];

  return ranked.slice(0, 4).map((c) => {
    let sum = 0;
    let count = 0;
    for (const r of rows) {
      const v = r[c.index];
      if (v === null || v === undefined || v === "") continue;
      const num = toNumber(v);
      if (Number.isFinite(num)) {
        sum += num;
        count += 1;
      }
    }
    const avg = AVG_HINT.test(c.name.toLowerCase());
    const raw = avg ? (count ? sum / count : 0) : sum;
    const value =
      c.type === "percent"
        ? formatPercent(raw)
        : c.type === "currency"
          ? formatCompact(raw, true)
          : avg
            ? c.isInteger
              ? formatInt(raw) // whole-number columns (days, counts) stay whole
              : formatNumber(Math.round(raw * 10) / 10)
            : formatCompact(raw, false);
    return {
      label: humanize(c.name),
      value,
      context: `${avg ? "Average" : "Total"} · ${count.toLocaleString()} value${count === 1 ? "" : "s"}`,
    };
  });
}
