import { describe, expect, it } from "vitest";
import { classifyColumns } from "./columns";
import { parseSelectMeta } from "./sql";
import { deriveKpis } from "./kpis";
import { pickChart } from "./chart";

// End-to-end of the SQL-aware path: parse → classify → derive. These pin the
// correctness win (AVG/MIN/MAX/COUNT roll up correctly, numeric GROUP BY keys are
// dimensions) and confirm the name-heuristic fallback is unchanged.

function derive(sql: string, columns: string[], rows: unknown[][]) {
  const meta = parseSelectMeta(sql);
  const cols = classifyColumns(columns, rows, meta);
  return { meta, cols, kpis: deriveKpis(rows, cols), chart: pickChart(rows, cols) };
}

describe("SQL-aware KPIs", () => {
  it("averages an AVG() column instead of summing it (with an honest label)", () => {
    const { kpis } = derive(
      "SELECT region, AVG(unit_price) avg_price FROM sales GROUP BY region",
      ["REGION", "AVG_PRICE"],
      [["North", 100], ["South", 200], ["East", 300]],
    );
    expect(kpis).toHaveLength(1); // REGION is a dimension, not a KPI
    expect(kpis[0].value).toBe("$200"); // avg of 100/200/300, NOT the sum (600)
    expect(kpis[0].context).toBe("Average across 3 groups");
  });

  it("rolls MIN up by the min and MAX up by the max, not the sum", () => {
    const { kpis } = derive(
      "SELECT dept, MIN(salary) lo, MAX(salary) hi FROM emp GROUP BY dept",
      ["DEPT", "LO", "HI"],
      [["A", 50000, 90000], ["B", 30000, 60000]],
    );
    const lo = kpis.find((k) => k.label === "Lo")!;
    const hi = kpis.find((k) => k.label === "Hi")!;
    expect(lo.value).toBe("30.0K"); // min, not 80K
    expect(lo.context).toBe("Minimum · 2 values");
    expect(hi.value).toBe("90.0K"); // max, not 150K
    expect(hi.context).toBe("Maximum · 2 values");
  });

  it("sums COUNT() columns into a grand total count", () => {
    const { kpis } = derive(
      "SELECT region, COUNT(*) orders FROM sales GROUP BY region",
      ["REGION", "ORDERS"],
      [["North", 5], ["South", 3]],
    );
    expect(kpis[0].value).toBe("8");
    expect(kpis[0].context).toBe("Total · 2 values");
  });

  it("treats a numeric GROUP BY key as a dimension, never a measure", () => {
    const { cols, kpis } = derive(
      "SELECT fiscal_year, SUM(revenue) rev FROM gl GROUP BY fiscal_year",
      ["FISCAL_YEAR", "REV"],
      [[2025, 1000], [2026, 2000]],
    );
    expect(cols[0].isMeasure).toBe(false); // 2025/2026 are years, not money
    expect(kpis).toHaveLength(1);
    expect(kpis[0].label).toBe("Rev");
    expect(kpis[0].value).toBe("3,000"); // SUM rolls up by summing (1000+2000); "rev" isn't a currency-word
  });
});

describe("name-heuristic fallback (SQL unreadable)", () => {
  it("sums a detail-row currency column exactly as before", () => {
    const { meta, kpis } = derive(
      "SELECT customer_name, outstanding_amount FROM ar WHERE fiscal_year = 2026",
      ["CUSTOMER_NAME", "OUTSTANDING_AMOUNT"],
      [["A", 100], ["B", 200]],
    );
    expect(meta!.reliable).toBe(false); // no GROUP BY, no aggregate
    expect(kpis[0].value).toBe("$300"); // additive amount → still a Total
    expect(kpis[0].context).toBe("Total · 2 values");
  });

  it("rolls a per-entity measure (salary) up by MAX in a record list, never a sum (F4)", () => {
    const cols = classifyColumns(
      ["FIRST_NAME", "SALARY"],
      [["Alan", 130000], ["Bob", 125000]],
    );
    const kpi = deriveKpis([["Alan", 130000], ["Bob", 125000]], cols)[0];
    expect(kpi.label).toBe("Salary");
    expect(kpi.context).toMatch(/^Maximum/);
    expect(kpi.value).not.toContain("255"); // never the sum of two people's pay
  });

  it("classifies with no SQL meta at all (backward compatible)", () => {
    const cols = classifyColumns(["AMOUNT"], [[10], [20]]);
    expect(cols[0].isMeasure).toBe(true);
    expect(cols[0].agg).toBeUndefined();
    expect(deriveKpis([[10], [20]], cols)[0].value).toBe("$30");
  });
});

describe("SQL-aware chart", () => {
  it("picks the GROUP BY dimension and rolls the measure up by its aggregation", () => {
    const { chart } = derive(
      "SELECT region, AVG(unit_price) avg_price FROM sales GROUP BY region",
      ["REGION", "AVG_PRICE"],
      // duplicate region rows so summing vs averaging diverge
      [["North", 100], ["North", 300], ["South", 200]],
    );
    expect(chart).not.toBeNull();
    expect(chart!.type).toBe("bar");
    expect(chart!.dimensionName).toBe("REGION");
    const north = chart!.data.find((d) => d.label === "North")!;
    expect(north.value).toBe(200); // avg(100,300), not sum(400)
  });
});
