import { describe, expect, it } from "vitest";
import { classifyColumns } from "./columns";
import { parseSelectMeta } from "./sql";
import { dimensionOrder, filterRows, nextDimension } from "./cascade";

// The drill-stack model: dimension ordering (GROUP BY-aware), row filtering down
// the stack, and choosing the next dimension to descend into. All pure.

describe("dimensionOrder", () => {
  it("descends in GROUP BY order, not column order", () => {
    // SELECT order is customer, region but GROUP BY is region, customer — the
    // cascade must follow the analyst's GROUP BY hierarchy (region first).
    const sql = "SELECT customer, region, SUM(amount) total FROM t GROUP BY region, customer";
    const rows = [["Acme", "North", 10]];
    const cols = classifyColumns(["customer", "region", "total"], rows, parseSelectMeta(sql));
    expect(dimensionOrder(cols, parseSelectMeta(sql))).toEqual([1, 0]); // region(idx1) → customer(idx0)
  });

  it("excludes measures and id columns from the cascade", () => {
    const sql = "SELECT region, customer, SUM(amount) total FROM t GROUP BY region, customer";
    const rows = [["North", "Acme", 10]];
    const cols = classifyColumns(["region", "customer", "total"], rows, parseSelectMeta(sql));
    expect(dimensionOrder(cols, parseSelectMeta(sql))).toEqual([0, 1]); // total (measure) absent
  });

  it("falls back to column order when the SQL can't be read", () => {
    const rows = [["North", "Acme", 10]];
    const cols = classifyColumns(["region", "customer", "amount"], rows, null);
    expect(dimensionOrder(cols, null)).toEqual([0, 1]);
  });
});

describe("filterRows", () => {
  const rows = [
    ["North", "Acme", 10],
    ["North", "Beta", 20],
    ["South", "Acme", 30],
  ];

  it("returns all rows for an empty stack", () => {
    expect(filterRows(rows, [])).toHaveLength(3);
  });

  it("ANDs every active drill level", () => {
    const out = filterRows(rows, [
      { dimIndex: 0, value: "North" },
      { dimIndex: 1, value: "Acme" },
    ]);
    expect(out).toEqual([["North", "Acme", 10]]);
  });

  it("matches on stringified cell values (chart group keys)", () => {
    const numRows = [[2026, "Q1"], [2025, "Q1"]];
    expect(filterRows(numRows, [{ dimIndex: 0, value: "2026" }])).toEqual([[2026, "Q1"]]);
  });
});

describe("nextDimension", () => {
  const order = [0, 1, 2];

  it("returns the first un-drilled dimension", () => {
    expect(nextDimension(order, [])).toBe(0);
    expect(nextDimension(order, [{ dimIndex: 0, value: "x" }])).toBe(1);
    expect(
      nextDimension(order, [
        { dimIndex: 0, value: "x" },
        { dimIndex: 1, value: "y" },
      ]),
    ).toBe(2);
  });

  it("returns null once every dimension is drilled (the cascade leaf)", () => {
    const full = order.map((dimIndex) => ({ dimIndex, value: "x" }));
    expect(nextDimension(order, full)).toBeNull();
  });
});
