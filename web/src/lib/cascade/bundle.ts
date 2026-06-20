import { ColumnMeta, rankMeasures } from "../derive/columns";
import { Agg, SqlMeta } from "../derive/sql";
import { dimKey } from "../derive/cascade";
import { deriveKpis, Kpi } from "../derive/kpis";
import { ChartSpec, pickChart } from "../derive/chart";
import { deriveInsights, Insight } from "../derive/insight";
import { buildPullDetailSql } from "../derive/pullDetail";
import { humanize, toNumber } from "@/lib/format";
import { errorMessage } from "@/lib/api/client";
import { ResolvedCascade } from "./spec";

// Client-orchestrated cascade fan-out (ADR-026). Starting from the APPROVED parent
// SQL + its result, descend the resolved dimension order: at each level take the
// top-N child values (ranked by the lead measure) and produce a child section for
// each, recursing to the next dimension. Every section's KPIs/chart/insights are
// derived LOCALLY (reusing the derive/* layer) — no row data leaves the browser.
//
// Two data modes for a child section's rows:
//  - LIVE (`run` provided): fetch a fresh, un-truncated slice via the SELECT-only
//    chokepoint — `buildPullDetailSql(approved, path)` is a plain `SELECT … WHERE
//    "DIM" = :v` (binds carry values; the chokepoint re-validates). This is the
//    deliverable path; bounded by a total-query budget.
//  - LOCAL (no `run`, or budget exhausted): filter the already-fetched parent rows.
//    Same bundle structure, no DB — used for the offline demo and tests.
// No new AI proposal is made: children are deterministic derivations of the
// approved parent (invariant 2); the chokepoint stays the only SQL authority.

export interface SectionResult {
  columns: string[];
  rows: unknown[][];
}
export type RunSql = (sql: string, binds: Record<string, unknown>) => Promise<SectionResult>;

export interface PathStep {
  column: string;
  value: string;
}

export interface BundleSection {
  path: PathStep[]; // drill path to this section ([] = root)
  rowCount: number;
  kpis: Kpi[];
  chart: ChartSpec | null;
  insights: Insight[];
  othersRollup?: { count: number; label: string }; // residual values folded out of top-N
  children: BundleSection[];
  detailRows?: unknown[][]; // leaf only: the (capped) underlying rows
  error?: string; // sanitized per-section failure (never aborts the whole bundle)
}

export interface BundleResult {
  root: BundleSection;
  columns: string[];
  queries: number; // live child queries actually run (0 in local mode)
  truncated: boolean; // a budget/section cap was hit
}

const MAX_TOTAL_QUERIES = 48; // live fan-out budget (P10-R1)
const MAX_SECTIONS = 256; // bound local-mode explosion too

// Mirror of the kpis.ts/insight.ts fallback so a section is RANKED by the same
// aggregation it is NARRATED by (P10-R1-F4): when the SQL gave no exact agg, a
// rate/duration/average-ish name averages, everything else sums.
const AVG_HINT = /(pct|percent|rate|ratio|margin|avg|average|days|age|score|price)/;

export async function buildCascadeBundle(
  approvedSql: string,
  parent: SectionResult,
  cols: ColumnMeta[],
  sqlMeta: SqlMeta | null,
  resolved: ResolvedCascade,
  run?: RunSql,
  onProgress?: (queriesDone: number) => void,
): Promise<BundleResult> {
  const columns = parent.columns;
  const measure = rankMeasures(cols)[0];
  const agg: Agg =
    measure?.agg ?? (measure && AVG_HINT.test(measure.name.toLowerCase()) ? "avg" : "sum");

  let queries = 0;
  let sections = 0;
  let truncated = false;

  const colIndex = (name: string) => columns.indexOf(name);

  function localFilter(filters: PathStep[]): unknown[][] {
    return parent.rows.filter((r) => filters.every((f) => dimKey(r[colIndex(f.column)]) === f.value));
  }

  // Rank a section's rows by a dimension, folding the lead measure (or row count
  // when there is no measure) per value; returns keys best-first.
  function rankGroups(rows: unknown[][], dimIndex: number): string[] {
    const sum = new Map<string, number>();
    const cnt = new Map<string, number>();
    const min = new Map<string, number>();
    const max = new Map<string, number>();
    for (const r of rows) {
      const key = dimKey(r[dimIndex]);
      cnt.set(key, (cnt.get(key) ?? 0) + 1);
      if (measure) {
        const v = toNumber(r[measure.index]);
        if (Number.isFinite(v)) {
          sum.set(key, (sum.get(key) ?? 0) + v);
          min.set(key, min.has(key) ? Math.min(min.get(key)!, v) : v);
          max.set(key, max.has(key) ? Math.max(max.get(key)!, v) : v);
        }
      }
    }
    const score = (k: string): number => {
      if (!measure) return cnt.get(k) ?? 0;
      if (agg === "min") return min.get(k) ?? 0;
      if (agg === "max") return max.get(k) ?? 0;
      if (agg === "avg") return (sum.get(k) ?? 0) / (cnt.get(k) || 1);
      return sum.get(k) ?? 0;
    };
    return [...cnt.keys()].sort((a, b) => score(b) - score(a));
  }

  async function childRows(filters: PathStep[]): Promise<{ rows: unknown[][]; error?: string }> {
    if (run && queries < MAX_TOTAL_QUERIES) {
      const { sql, binds } = buildPullDetailSql(approvedSql, filters);
      queries += 1;
      onProgress?.(queries);
      try {
        const res = await run(sql, binds);
        return { rows: res.rows };
      } catch (e) {
        return { rows: [], error: errorMessage(e) };
      }
    }
    if (run && queries >= MAX_TOTAL_QUERIES) truncated = true;
    return { rows: localFilter(filters) };
  }

  async function buildSection(
    filters: PathStep[],
    rows: unknown[][],
    level: number,
  ): Promise<BundleSection> {
    sections += 1;
    const excluded = filters.map((f) => colIndex(f.column));
    const section: BundleSection = {
      path: filters,
      rowCount: rows.length,
      kpis: deriveKpis(rows, cols),
      chart: pickChart(rows, cols, excluded, resolved.dimIndices),
      insights: deriveInsights(cols, rows, sqlMeta),
      children: [],
    };

    const atDepth = level >= resolved.dimIndices.length;
    if (atDepth || sections >= MAX_SECTIONS) {
      if (sections >= MAX_SECTIONS) truncated = true;
      section.detailRows = resolved.rowsPerChild ? rows.slice(0, resolved.rowsPerChild) : rows;
      return section;
    }

    const dimIndex = resolved.dimIndices[level];
    const ranked = rankGroups(rows, dimIndex);
    const top = ranked.slice(0, resolved.childrenPerLevel);
    const rest = ranked.length - top.length;
    if (rest > 0) {
      const dimLabel = humanize(columns[dimIndex]).toLowerCase();
      section.othersRollup = { count: rest, label: `${rest} more ${dimLabel}` };
    }

    for (const value of top) {
      if (sections >= MAX_SECTIONS) {
        truncated = true;
        break;
      }
      const childFilters = [...filters, { column: columns[dimIndex], value }];
      const { rows: cRows, error } = await childRows(childFilters);
      if (error) {
        sections += 1;
        section.children.push({
          path: childFilters,
          rowCount: 0,
          kpis: [],
          chart: null,
          insights: [],
          children: [],
          error,
        });
        continue;
      }
      section.children.push(await buildSection(childFilters, cRows, level + 1));
    }
    return section;
  }

  const root = await buildSection([], parent.rows, 0);
  return { root, columns, queries, truncated };
}
