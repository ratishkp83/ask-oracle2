import { ColumnMeta, rankMeasures } from "./columns";
import { dimensionOrder, dimKey, NULL_KEY } from "./cascade";
import { foldAgg } from "./aggregate";
import { Agg, SqlMeta } from "./sql";
import { formatCompact, formatInt, formatNumber, formatPercent, humanize, toNumber } from "@/lib/format";

// Local, deterministic insight narration (ADR-027). Reads ONLY the already-fetched
// result + local column/SQL metadata and emits a short, ranked set of plain-language
// facts — "what stands out". It sends nothing anywhere (invariant 3), makes no LLM
// call, and never throws (degrades to []). Every statement is a fact with an
// explainable `basis`; thresholds keep weak signals silent (P10-R4). Mirrors the
// aggregation rules the KPIs use (kpis.ts) so a stated total matches its KPI card.

export type InsightKind = "total" | "top" | "trend" | "spread" | "coverage";

export interface Insight {
  kind: InsightKind;
  text: string; // plain-language, executive-facing
  measure?: string; // the measure column it concerns
  basis: string; // short factual explanation of the math (UI tooltip)
  confidence: "high" | "med";
}

// Mirror of the kpis.ts fallback: rate/duration/average-ish names average; the rest
// sum. Only used when the SQL didn't yield an exact aggregation (c.agg).
const AVG_HINT = /(pct|percent|rate|ratio|margin|avg|average|days|age|score|price)/;

// Conservative thresholds — a weak signal stays silent rather than misleading.
const CONCENTRATION_MIN = 0.3; // top-1 share of the total to call out concentration
const TREND_MIN_PCT = 0.1; // |first→last % change| to call out a trend
const SPREAD_RATIO_MIN = 2; // max/min group ratio to call out spread
const COVERAGE_MIN = 0.05; // null-dimension share of rows to call out coverage
const ISO_LIKE = /^\d{4}(-\d{2}(-\d{2})?)?/; // sortable date/year key for trend ordering

function leadAgg(c: ColumnMeta): Agg {
  return c.agg ?? (AVG_HINT.test(c.name.toLowerCase()) ? "avg" : "sum");
}

function formatMeasure(raw: number, c: ColumnMeta, agg: Agg): string {
  if (c.type === "percent") return formatPercent(raw);
  if (c.type === "currency") return formatCompact(raw, true);
  if (agg === "avg") return c.isInteger ? formatInt(raw) : formatNumber(Math.round(raw * 10) / 10);
  return formatCompact(raw, false);
}

function plural(w: string): string {
  if (/[^aeiou]y$/.test(w)) return w.slice(0, -1) + "ies";
  if (/(s|x|z|ch|sh)$/.test(w)) return w + "es";
  return w + "s";
}
function units(w: string, n: number): string {
  return n === 1 ? w : plural(w);
}
function keyLabel(key: string, dimLabel: string): string {
  return key === NULL_KEY ? `(no ${dimLabel})` : key;
}
function pctStr(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

interface GroupStat {
  key: string;
  sum: number;
  count: number;
  min: number;
  max: number;
}

// Fold the lead measure within each value of a dimension, in one O(n) pass.
function groupByDim(rows: unknown[][], dimIndex: number, measureIndex: number): GroupStat[] {
  const map = new Map<string, GroupStat>();
  for (const r of rows) {
    const v = r[measureIndex];
    if (v === null || v === undefined || v === "") continue;
    const num = toNumber(v);
    if (!Number.isFinite(num)) continue;
    const key = dimKey(r[dimIndex]);
    let g = map.get(key);
    if (!g) {
      g = { key, sum: 0, count: 0, min: num, max: num };
      map.set(key, g);
    }
    g.sum += num;
    g.count += 1;
    if (num < g.min) g.min = num;
    if (num > g.max) g.max = num;
  }
  return [...map.values()];
}

function foldStat(g: GroupStat, agg: Agg): number {
  switch (agg) {
    case "min":
      return g.min;
    case "max":
      return g.max;
    case "avg":
      return g.count ? g.sum / g.count : 0;
    default:
      return g.sum; // sum / count
  }
}

/**
 * Derive a ranked, capped set of local insights from a result. Pure; never throws;
 * returns [] when nothing clears the thresholds (or there is no measure / no rows).
 */
export function deriveInsights(
  cols: ColumnMeta[],
  rows: unknown[][],
  sqlMeta: SqlMeta | null,
  opts?: { max?: number },
): Insight[] {
  const max = opts?.max ?? 4;
  if (rows.length === 0) return [];

  const lead = rankMeasures(cols)[0];
  if (!lead) return []; // no measure → nothing quantitative to say

  const agg = leadAgg(lead);
  const mLabel = humanize(lead.name);
  const mLower = mLabel.toLowerCase();

  // All-rows fold for the anchor "total" + the concentration denominator.
  let totalSum = 0;
  let measureRows = 0;
  for (const r of rows) {
    const v = r[lead.index];
    if (v === null || v === undefined || v === "") continue;
    const num = toNumber(v);
    if (!Number.isFinite(num)) continue;
    totalSum += num;
    measureRows += 1;
  }
  if (measureRows === 0) return []; // measure is entirely null → say nothing

  const out: Insight[] = [];

  const order = dimensionOrder(cols, sqlMeta);
  const dimIndex = order.length > 0 ? order[0] : -1;
  const dimCol = dimIndex >= 0 ? cols.find((c) => c.index === dimIndex) : undefined;
  const dimLabel = dimCol ? humanize(dimCol.name).toLowerCase() : "row";

  const stats = dimCol ? groupByDim(rows, dimIndex, lead.index) : [];
  const groupCount = stats.length;

  // --- total (anchor) -------------------------------------------------------
  {
    const allNums: number[] = [];
    for (const r of rows) {
      const v = r[lead.index];
      if (v === null || v === undefined || v === "") continue;
      const num = toNumber(v);
      if (Number.isFinite(num)) allNums.push(num);
    }
    const total = foldAgg(allNums, agg);
    const val = formatMeasure(total, lead, agg);
    const n = dimCol ? groupCount : rows.length;
    const unit = dimCol ? units(dimLabel, n) : units("row", n);
    const scope = `across ${n.toLocaleString()} ${unit}`;
    let text: string;
    if (agg === "avg") text = `Average ${mLower} ${scope}: ${val}.`;
    else if (agg === "min") text = `Lowest ${mLower} ${scope}: ${val}.`;
    else if (agg === "max") text = `Highest ${mLower} ${scope}: ${val}.`;
    else text = `${mLabel} ${scope}: ${val}.`;
    out.push({
      kind: "total",
      measure: lead.name,
      text,
      basis: `${agg.toUpperCase()} of ${lead.name} over ${n.toLocaleString()} ${unit}`,
      confidence: "high",
    });
  }

  if (dimCol && groupCount >= 2) {
    // --- top (+ concentration when meaningful) ------------------------------
    {
      let topG = stats[0];
      let topV = foldStat(topG, agg);
      for (const g of stats) {
        const v = foldStat(g, agg);
        if (v > topV) {
          topV = v;
          topG = g;
        }
      }
      const name = keyLabel(topG.key, dimLabel);
      let text = `${name} leads ${mLower} at ${formatMeasure(topV, lead, agg)}`;
      let basis = `largest ${agg} of ${lead.name} by ${dimLabel}`;
      // Share only makes sense for additive totals (sum/count), not avg/min/max.
      if ((agg === "sum" || agg === "count") && totalSum > 0) {
        const share = topG.sum / totalSum;
        if (share >= CONCENTRATION_MIN) {
          text += ` — ${pctStr(share)} of the total`;
          basis = `${formatCompact(topG.sum, lead.type === "currency")} of ${formatCompact(totalSum, lead.type === "currency")}`;
        }
      }
      out.push({ kind: "top", measure: lead.name, text: text + ".", basis, confidence: "high" });
    }

    // --- trend (only an ordered date/time dimension) ------------------------
    if (dimCol.type === "date" && stats.every((s) => ISO_LIKE.test(s.key))) {
      const ordered = [...stats].sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
      const first = ordered[0];
      const last = ordered[ordered.length - 1];
      const fv = foldStat(first, agg);
      const lv = foldStat(last, agg);
      if (fv !== 0) {
        const change = (lv - fv) / Math.abs(fv);
        if (Math.abs(change) >= TREND_MIN_PCT) {
          out.push({
            kind: "trend",
            measure: lead.name,
            text: `${mLabel} ${change > 0 ? "rose" : "fell"} ${pctStr(Math.abs(change))} from ${first.key} (${formatMeasure(fv, lead, agg)}) to ${last.key} (${formatMeasure(lv, lead, agg)}).`,
            basis: `first vs last ${dimLabel}`,
            confidence: "med",
          });
        }
      }
    }

    // --- spread (additive/avg measures; a material max/min ratio) -----------
    if (groupCount >= 3 && agg !== "min" && agg !== "max") {
      let lo = stats[0];
      let hi = stats[0];
      let loV = foldStat(lo, agg);
      let hiV = foldStat(hi, agg);
      for (const g of stats) {
        const v = foldStat(g, agg);
        if (v < loV) {
          loV = v;
          lo = g;
        }
        if (v > hiV) {
          hiV = v;
          hi = g;
        }
      }
      if (loV > 0 && hiV / loV >= SPREAD_RATIO_MIN) {
        out.push({
          kind: "spread",
          measure: lead.name,
          text: `${mLabel} ranges from ${formatMeasure(loV, lead, agg)} (${keyLabel(lo.key, dimLabel)}) to ${formatMeasure(hiV, lead, agg)} (${keyLabel(hi.key, dimLabel)}).`,
          basis: `max vs min ${dimLabel}`,
          confidence: "high",
        });
      }
    }

    // --- coverage (a notable share of rows missing the dimension) -----------
    {
      let nullRows = 0;
      for (const r of rows) if (dimKey(r[dimIndex]) === NULL_KEY) nullRows += 1;
      const share = nullRows / rows.length;
      if (share >= COVERAGE_MIN && share < 1) {
        out.push({
          kind: "coverage",
          text: `${pctStr(share)} of rows have no ${dimLabel}.`,
          basis: `${nullRows.toLocaleString()} of ${rows.length.toLocaleString()} rows null`,
          confidence: "high",
        });
      }
    }
  }

  return out.slice(0, max);
}
