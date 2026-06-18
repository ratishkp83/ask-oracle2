import { describe, it, expect } from "vitest";
import { deriveInsights } from "./insight";
import { ColumnMeta, ColType } from "./columns";
import { Agg } from "./sql";

// Build ColumnMeta directly so each test pins exactly the classification the
// engine reacts to (the real classifyColumns path is covered elsewhere).
function dim(name: string, index: number, type: ColType = "category"): ColumnMeta {
  return { name, index, type, isMeasure: false, isInteger: false, numericAligned: false };
}
function measure(
  name: string,
  index: number,
  o: { type?: ColType; agg?: Agg; isInteger?: boolean } = {},
): ColumnMeta {
  return {
    name,
    index,
    type: o.type ?? "number",
    isMeasure: true,
    isInteger: !!o.isInteger,
    numericAligned: true,
    agg: o.agg,
  };
}
const texts = (xs: { text: string }[]) => xs.map((i) => i.text);

describe("deriveInsights", () => {
  it("anchors with a total and calls out a concentrated leader + spread (currency, sum)", () => {
    const cols = [dim("DEPARTMENT", 0), measure("TOTAL_SALARY", 1, { type: "currency", agg: "sum" })];
    const rows = [
      ["Engineering", 375000],
      ["Sales", 250000],
      ["HR", 50000],
      ["Legal", 40000],
      ["Ops", 30000],
    ];
    const ins = deriveInsights(cols, rows, null);
    const kinds = ins.map((i) => i.kind);
    expect(kinds).toContain("total");
    expect(kinds).toContain("top");
    expect(kinds).toContain("spread");
    expect(texts(ins)).toContainEqual("Total salary across 5 departments: $745.0K.");
    expect(texts(ins).find((t) => /^Engineering leads/.test(t))).toBe(
      "Engineering leads total salary at $375.0K — 50% of the total.",
    );
    expect(texts(ins)).toContainEqual(
      "Total salary ranges from $30.0K (Ops) to $375.0K (Engineering).",
    );
  });

  it("averages an AVG measure across groups (never sums it)", () => {
    const cols = [dim("CUSTOMER", 0), measure("DAYS_OVERDUE", 1, { isInteger: true, agg: "avg" })];
    const rows = [
      ["A", 10],
      ["B", 20],
      ["C", 60],
    ];
    const ins = deriveInsights(cols, rows, null);
    const total = ins.find((i) => i.kind === "total")!;
    expect(total.text).toBe("Average days overdue across 3 customers: 30.");
    // Would be 90 if it (wrongly) summed.
    expect(total.text).not.toContain("90");
  });

  it("calls out a date trend (direction + % change), confidence med", () => {
    const cols = [dim("MONTH", 0, "date"), measure("REVENUE", 1, { type: "currency", agg: "sum" })];
    const rows = [
      ["2024-01", 100000],
      ["2024-02", 110000],
      ["2024-03", 130000],
    ];
    const ins = deriveInsights(cols, rows, null);
    const trend = ins.find((i) => i.kind === "trend");
    expect(trend).toBeDefined();
    expect(trend!.text).toBe("Revenue rose 30% from 2024-01 ($100.0K) to 2024-03 ($130.0K).");
    expect(trend!.confidence).toBe("med");
  });

  it("flags coverage when a notable share of rows lack the dimension", () => {
    const cols = [dim("REGION", 0), measure("AMT", 1, { type: "currency", agg: "sum" })];
    const rows = [
      ["East", 100],
      [null, 100],
      ["", 100],
      ["West", 100],
    ];
    const ins = deriveInsights(cols, rows, null);
    const cov = ins.find((i) => i.kind === "coverage");
    expect(cov).toBeDefined();
    expect(cov!.text).toBe("50% of rows have no region.");
  });

  it("suppresses concentration below the threshold (even split)", () => {
    const cols = [dim("CAT", 0), measure("AMT", 1, { type: "currency", agg: "sum" })];
    const rows = [
      ["A", 100],
      ["B", 100],
      ["C", 100],
      ["D", 100],
    ];
    const ins = deriveInsights(cols, rows, null);
    const top = ins.find((i) => i.kind === "top")!;
    expect(top.text).toBe("A leads amt at $100.");
    expect(top.text).not.toContain("of the total");
    // All-equal groups → no spread either.
    expect(ins.some((i) => i.kind === "spread")).toBe(false);
  });

  it("respects the max cap", () => {
    const cols = [dim("REGION", 0), measure("AMT", 1, { type: "currency", agg: "sum" })];
    const rows = [
      ["East", 100],
      [null, 100],
      ["", 100],
      ["West", 100],
    ];
    expect(deriveInsights(cols, rows, null, { max: 2 })).toHaveLength(2);
  });

  it("returns [] when there is no measure, no rows, or an all-null measure", () => {
    expect(deriveInsights([dim("NAME", 0), dim("CITY", 1)], [["a", "x"]], null)).toEqual([]);
    expect(deriveInsights([dim("D", 0), measure("M", 1, { agg: "sum" })], [], null)).toEqual([]);
    expect(
      deriveInsights(
        [dim("D", 0), measure("M", 1, { agg: "sum" })],
        [
          ["a", null],
          ["b", null],
        ],
        null,
      ),
    ).toEqual([]);
  });

  it("never throws on degenerate input", () => {
    const cols = [dim("D", 0), measure("M", 1, { agg: "sum" })];
    expect(() => deriveInsights(cols, [["x", "not-a-number"]], null)).not.toThrow();
    expect(() => deriveInsights([], [[1, 2, 3]], null)).not.toThrow();
    expect(() => deriveInsights(cols, [[undefined, undefined]], null)).not.toThrow();
  });

  // Phase 11 — single-record results must read logically, never "across 1 X".
  it("narrates a single-record top-1 result as the highest (not 'across 1')", () => {
    const cols = [dim("FIRST_NAME", 0), dim("LAST_NAME", 1), measure("SALARY", 2)];
    const sqlMeta = { outputs: [], groupBy: [], hasGroupBy: false, reliable: false, topOne: { desc: true } };
    const ins = deriveInsights(cols, [["Steven", "King", 130000]], sqlMeta);
    expect(ins).toHaveLength(1);
    expect(ins[0].text).toContain("Steven King has the highest salary");
    expect(ins[0].text).toMatch(/130(\.0)?K/);
    expect(ins[0].text).not.toMatch(/across 1/);
  });

  it("narrates a single record without a top-1 order as a plain record", () => {
    const ins = deriveInsights([dim("FIRST_NAME", 0), measure("SALARY", 1)], [["Steven", 130000]], null);
    expect(ins).toHaveLength(1);
    expect(ins[0].text).toMatch(/^Steven — Salary: 130(\.0)?K\.$/);
    expect(ins[0].text).not.toMatch(/across 1/);
  });

  it("avoids 'across 1 <dimension>' for a single-group result", () => {
    const cols = [dim("DEPARTMENT", 0), measure("SALARY", 1, { agg: "sum" })];
    const rows = [
      ["Engineering", 100000],
      ["Engineering", 200000],
    ];
    const total = deriveInsights(cols, rows, null).find((i) => i.kind === "total")!;
    expect(total.text).toMatch(/across 2 rows/);
    expect(total.text).not.toMatch(/1 department/);
  });

  it("narrates an un-aggregated record list by the max — not a sum/share/per-name", () => {
    // "the highest-paid employee in each department" → a list of records, not a
    // groupable distribution. SALARY has no agg → must NOT be summed.
    const cols = [dim("FIRST_NAME", 0), dim("DEPARTMENT", 1), measure("SALARY", 2)];
    const rows = [
      ["Alan", "Engineering", 130000],
      ["Bob", "Sales", 125000],
    ];
    const text = texts(deriveInsights(cols, rows, null)).join(" | ");
    expect(text).toMatch(/Highest salary: 130(\.0)?K — Alan/);
    expect(text).toMatch(/ranges 125(\.0)?K to 130(\.0)?K/);
    expect(text).not.toMatch(/across 2 first names/i);
    expect(text).not.toMatch(/of the total/i);
  });

  it("frames a grouped MAX as 'highest … across N', led by a group, with no share", () => {
    const cols = [dim("DEPARTMENT", 0), measure("SALARY", 1, { type: "currency", agg: "max" })];
    const rows = [
      ["Engineering", 130000],
      ["Sales", 120000],
      ["HR", 90000],
    ];
    const ins = deriveInsights(cols, rows, null);
    expect(ins.find((i) => i.kind === "total")!.text).toBe("Highest salary across 3 departments: $130.0K.");
    const top = ins.find((i) => i.kind === "top")!;
    expect(top.text).toBe("Engineering leads salary at $130.0K.");
    expect(top.text).not.toContain("of the total"); // share is meaningless for a MAX
  });

  it("frames a grouped COUNT as an additive total with a leader share", () => {
    const cols = [dim("STATUS", 0), measure("ORDERS", 1, { isInteger: true, agg: "count" })];
    const rows = [
      ["Open", 600],
      ["Closed", 300],
      ["Cancelled", 100],
    ];
    const ins = deriveInsights(cols, rows, null);
    expect(ins.find((i) => i.kind === "total")!.text).toMatch(/^Orders across 3 statuses: /);
    expect(ins.find((i) => i.kind === "top")!.text).toContain("of the total"); // counts are additive
  });

  it("omits the range when an un-aggregated list has a single distinct value", () => {
    const ins = deriveInsights(
      [dim("NAME", 0), measure("SALARY", 1)],
      [
        ["A", 100000],
        ["B", 100000],
      ],
      null,
    );
    expect(ins).toHaveLength(1);
    expect(ins[0].text).toMatch(/^Highest salary: 100(\.0)?K — A\.$/);
    expect(ins.some((i) => /ranges/.test(i.text))).toBe(false);
  });
});
