import { describe, expect, it } from "vitest";
import { parseSelectMeta } from "./sql";

describe("parseSelectMeta", () => {
  it("reads GROUP BY dimensions and aggregate measures with their exact aggregation", () => {
    const meta = parseSelectMeta(
      "SELECT region, SUM(amount) AS total, AVG(unit_price) avg_price, COUNT(*) orders " +
        "FROM sales GROUP BY region ORDER BY total DESC",
    )!;
    expect(meta).not.toBeNull();
    expect(meta.reliable).toBe(true);
    expect(meta.hasGroupBy).toBe(true);
    expect(meta.outputs.map((o) => o.role)).toEqual(["dimension", "measure", "measure", "measure"]);
    expect(meta.outputs.map((o) => o.agg)).toEqual([undefined, "sum", "avg", "count"]);
    expect(meta.groupBy).toEqual(["REGION"]);
  });

  it("treats a numeric GROUP BY key as a dimension, not a measure", () => {
    const meta = parseSelectMeta(
      "SELECT fiscal_year, SUM(revenue) rev FROM gl GROUP BY fiscal_year",
    )!;
    expect(meta.outputs[0].role).toBe("dimension"); // fiscal_year is numeric but a grouping key
    expect(meta.outputs[1]).toMatchObject({ role: "measure", agg: "sum" });
  });

  it("detects MIN and MAX aggregations", () => {
    const meta = parseSelectMeta(
      "SELECT dept, MIN(salary) lo, MAX(salary) hi FROM emp GROUP BY dept",
    )!;
    expect(meta.outputs.map((o) => o.agg)).toEqual([undefined, "min", "max"]);
  });

  it("handles COUNT(DISTINCT ...) as a count measure", () => {
    const meta = parseSelectMeta(
      "SELECT region, COUNT(DISTINCT customer_id) customers FROM ar GROUP BY region",
    )!;
    expect(meta.outputs[1]).toMatchObject({ role: "measure", agg: "count" });
  });

  it("does NOT treat a window aggregate as a group measure", () => {
    const meta = parseSelectMeta(
      "SELECT region, SUM(amount) OVER (PARTITION BY region) running FROM sales",
    )!;
    // No GROUP BY and the only SUM is a window function → per-row, not a measure.
    expect(meta.outputs[1].role).toBe("passthrough");
    expect(meta.outputs[1].agg).toBeUndefined();
    expect(meta.reliable).toBe(false);
  });

  it("marks detail-row queries (no GROUP BY, no aggregate) as not reliable", () => {
    const meta = parseSelectMeta(
      "SELECT customer_name, outstanding_amount, days_overdue FROM ar_summary WHERE fiscal_year = 2026",
    )!;
    expect(meta.reliable).toBe(false);
    expect(meta.outputs.every((o) => o.role === "passthrough")).toBe(true);
  });

  it("returns null for SELECT * (cannot map outputs to columns)", () => {
    expect(parseSelectMeta("SELECT * FROM invoices")).toBeNull();
    expect(parseSelectMeta("SELECT t.* FROM invoices t")).toBeNull();
  });

  it("returns null for CTE and compound queries", () => {
    expect(parseSelectMeta("WITH x AS (SELECT 1 FROM dual) SELECT * FROM x")).toBeNull();
    expect(parseSelectMeta("SELECT a FROM t1 UNION SELECT a FROM t2")).toBeNull();
  });

  it("is not confused by commas/parens inside string literals", () => {
    const meta = parseSelectMeta(
      "SELECT region, SUM(amount) total FROM sales WHERE note = 'A, (B), C' GROUP BY region",
    )!;
    expect(meta.outputs.map((o) => o.role)).toEqual(["dimension", "measure"]);
    expect(meta.outputs[1].agg).toBe("sum");
  });

  it("is not confused by commas inside function arguments (DECODE/EXTRACT)", () => {
    const meta = parseSelectMeta(
      "SELECT EXTRACT(YEAR FROM order_dt) yr, SUM(amount) total " +
        "FROM orders GROUP BY EXTRACT(YEAR FROM order_dt)",
    )!;
    expect(meta.outputs).toHaveLength(2);
    expect(meta.outputs[0].role).toBe("dimension");
    expect(meta.outputs[1]).toMatchObject({ role: "measure", agg: "sum" });
  });

  it("ignores GROUP BY inside a subquery (only the outer one counts)", () => {
    const meta = parseSelectMeta(
      "SELECT region, SUM(amount) total FROM (SELECT region, amount FROM sales GROUP BY region, amount) " +
        "GROUP BY region",
    )!;
    expect(meta.groupBy).toEqual(["REGION"]);
    expect(meta.outputs).toHaveLength(2);
  });

  it("returns null for empty or non-SELECT input", () => {
    expect(parseSelectMeta("")).toBeNull();
    expect(parseSelectMeta("   ")).toBeNull();
    // @ts-expect-error guard against non-string at runtime
    expect(parseSelectMeta(null)).toBeNull();
  });
});
