import { describe, expect, it } from "vitest";
import { classifyColumns } from "./columns";
import { parseSelectMeta } from "./sql";
import { NULL_KEY, dimKey, dimensionOrder, filterRows } from "./cascade";

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

  it("matches the '—' bucket so drilling a null/empty bar isn't a dead end", () => {
    const nullRows = [[null, 1], ["", 2], ["X", 3]];
    // The chart renders null and "" together as one "—" bar; drilling it must
    // return both, not zero rows.
    expect(filterRows(nullRows, [{ dimIndex: 0, value: NULL_KEY }])).toEqual([[null, 1], ["", 2]]);
  });
});

describe("dimKey", () => {
  it("collapses null/undefined/empty to the shared '—' bucket, else stringifies", () => {
    expect(dimKey(null)).toBe(NULL_KEY);
    expect(dimKey(undefined)).toBe(NULL_KEY);
    expect(dimKey("")).toBe(NULL_KEY);
    expect(dimKey("North")).toBe("North");
    expect(dimKey(2026)).toBe("2026");
  });
});

