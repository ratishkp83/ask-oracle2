import { describe, expect, it } from "vitest";
import { classifyColumns } from "./columns";
import { parseSelectMeta } from "./sql";
import { dimensionOrder } from "./cascade";
import { deriveKpis } from "./kpis";
import { pickChart } from "./chart";
import { formatCell } from "@/lib/format";

// Edge-case matrix E1–E8 at the derivation level: every path must stay
// deterministic, never throw, and never misclassify on degenerate input.

describe("E1 — empty result (0 rows)", () => {
  it("derives nothing and does not throw", () => {
    const cols = classifyColumns(["REGION", "AMOUNT"], []);
    expect(() => deriveKpis([], cols)).not.toThrow();
    expect(deriveKpis([], cols)).toEqual([]);
    expect(pickChart([], cols)).toBeNull();
  });
});

describe("E3 — single row, multiple columns", () => {
  it("derives KPIs from the row but hides the chart (needs ≥2 points)", () => {
    const sql = "SELECT customer, SUM(amount) total FROM ar GROUP BY customer";
    const cols = classifyColumns(["CUSTOMER", "TOTAL"], [["Acme", 500]], parseSelectMeta(sql));
    const kpis = deriveKpis([["Acme", 500]], cols);
    expect(kpis).toHaveLength(1);
    expect(kpis[0].value).toBe("$500");
    expect(pickChart([["Acme", 500]], cols)).toBeNull();
  });
});

describe("E4 — large result (tens of thousands of rows)", () => {
  const N = 50_000;
  const CARDINALITY = 200;
  const rows: unknown[][] = [];
  for (let i = 0; i < N; i++) rows.push([`cat-${i % CARDINALITY}`, 10]);
  const cols = classifyColumns(
    ["CATEGORY", "AMOUNT"],
    rows,
    parseSelectMeta("SELECT category, SUM(amount) amount FROM t GROUP BY category"),
  );

  it("aggregates O(n) with a correct grand total", () => {
    const start = performance.now();
    const kpis = deriveKpis(rows, cols);
    const ms = performance.now() - start;
    expect(kpis[0].value).toBe("$500.0K"); // 50,000 × 10
    expect(ms).toBeLessThan(500); // loose guard against accidental O(n²)
  });

  it("caps chart cardinality and folds the rest into +N more", () => {
    const chart = pickChart(rows, cols)!;
    expect(chart.data.length).toBeLessThanOrEqual(6);
    expect(chart.extra).toBe(CARDINALITY - chart.data.length); // 200 − 6 = 194
  });
});

describe("E5 — pathological column count", () => {
  it("classifies many columns and still surfaces at most 4 KPIs", () => {
    const columns = Array.from({ length: 300 }, (_, i) => `AMT_${i}`);
    const row = columns.map(() => 100);
    const cols = classifyColumns(columns, [row, row]);
    expect(cols).toHaveLength(300);
    expect(deriveKpis([row, row], cols).length).toBeLessThanOrEqual(4);
  });
});

describe("E6 — nulls and mixed types", () => {
  it("skips nulls in aggregation and counts only real values", () => {
    const cols = classifyColumns(["AMOUNT"], [[100], [null], [200], [""]]);
    const kpi = deriveKpis([[100], [null], [200], [""]], cols)[0];
    expect(kpi.value).toBe("$300"); // 100 + 200; null/"" skipped
    expect(kpi.context).toBe("Total · 2 values");
  });

  it("does not misclassify a mixed numeric/text column as a measure", () => {
    const cols = classifyColumns(["CODE"], [[1], ["N/A"], [3]]);
    expect(cols[0].isMeasure).toBe(false);
  });

  it("renders nulls/empties as an em dash in the grid", () => {
    expect(formatCell(null)).toBe("—");
    expect(formatCell(undefined)).toBe("—");
    expect(formatCell("")).toBe("—");
  });
});

describe("E7 — all-null column", () => {
  it("is not treated as a measure and produces no KPI", () => {
    const cols = classifyColumns(["NOTE", "REGION"], [[null, "N"], [null, "S"]]);
    expect(cols[0].isMeasure).toBe(false);
    expect(deriveKpis([[null, "N"], [null, "S"]], cols)).toEqual([]);
  });
});

describe("E8 — pre-aggregated AVG is never summed in the chart", () => {
  it("rolls the chart measure up by its aggregation", () => {
    const sql = "SELECT region, AVG(score) score FROM s GROUP BY region";
    const rows: unknown[][] = [["N", 80], ["N", 100], ["S", 90]];
    const cols = classifyColumns(["REGION", "SCORE"], rows, parseSelectMeta(sql));
    const chart = pickChart(rows, cols)!;
    expect(chart.data.find((d) => d.label === "N")!.value).toBe(90); // avg(80,100), not 180
  });
});

describe("E9 — cascade skips a dimension that is constant in the drilled scope", () => {
  it("breaks down by the next dimension that actually splits the data", () => {
    // GROUP BY region, customer, product. After drilling region (excluded), this
    // slice has one customer but two products — the chart must descend to product,
    // not dead-end on the constant customer.
    const sql =
      "SELECT region, customer, product, SUM(amt) amt FROM t GROUP BY region, customer, product";
    const meta = parseSelectMeta(sql);
    const rows: unknown[][] = [
      ["X", "Acme", "P1", 10],
      ["X", "Acme", "P2", 20],
    ];
    const cols = classifyColumns(["region", "customer", "product", "amt"], rows, meta);
    const order = dimensionOrder(cols, meta); // [0, 1, 2]
    const chart = pickChart(rows, cols, [0], order)!; // region drilled
    expect(chart.dimensionName).toBe("product");
    expect(chart.data.map((d) => d.label).sort()).toEqual(["P1", "P2"]);
  });
});
