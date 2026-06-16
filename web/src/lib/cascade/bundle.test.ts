import { describe, it, expect, vi } from "vitest";
import { buildCascadeBundle } from "./bundle";
import { DEFAULT_CASCADE_SPEC, fromPersistedSpec, resolveCascade, toPersistedSpec } from "./spec";
import { ColumnMeta } from "../derive/columns";

const columns = ["REGION", "CUSTOMER", "AMOUNT"];
const cols: ColumnMeta[] = [
  { name: "REGION", index: 0, type: "category", isMeasure: false, isInteger: false, numericAligned: false },
  { name: "CUSTOMER", index: 1, type: "category", isMeasure: false, isInteger: false, numericAligned: false },
  { name: "AMOUNT", index: 2, type: "currency", isMeasure: true, isInteger: false, numericAligned: true, agg: "sum" },
];
const rows: unknown[][] = [
  ["NA", "Acme", 100],
  ["NA", "Beta", 50],
  ["EU", "Cire", 70],
  ["EU", "Dyne", 30],
  ["APAC", "Echo", 20],
];
const SQL = "SELECT region, customer, SUM(amount) amount FROM sales GROUP BY region, customer";

function resolve(over = {}) {
  return resolveCascade({ ...DEFAULT_CASCADE_SPEC, ...over }, columns, cols, null);
}

describe("resolveCascade", () => {
  it("auto-derives the dimension order and clamps depth/children", () => {
    expect(resolve().dimIndices).toEqual([0, 1]); // REGION, CUSTOMER
    expect(resolve({ depth: 99 }).dimIndices).toEqual([0, 1]); // clamped to available dims
    expect(resolve({ childrenPerLevel: 0 }).childrenPerLevel).toBe(1);
    expect(resolve({ childrenPerLevel: 999 }).childrenPerLevel).toBe(50);
  });
  it("honours an explicit dimension order and drops unknown names", () => {
    expect(resolveCascade({ ...DEFAULT_CASCADE_SPEC, dimensionOrder: ["CUSTOMER", "NOPE", "REGION"] }, columns, cols, null).dimIndices).toEqual([1, 0]);
  });
});

describe("cascade spec persistence mapping (camelCase <-> snake_case)", () => {
  it("round-trips internal <-> persisted", () => {
    const internal = { dimensionOrder: ["REGION", "CUSTOMER"], depth: 2, childrenPerLevel: 8, rowsPerChild: 500 };
    const persisted = toPersistedSpec(internal);
    expect(persisted).toEqual({
      dimension_order: ["REGION", "CUSTOMER"],
      depth: 2,
      children_per_level: 8,
      rows_per_child: 500,
    });
    expect(fromPersistedSpec(persisted)).toEqual(internal);
  });

  it("maps null/absent rows_per_child to undefined and back", () => {
    expect(
      fromPersistedSpec({ dimension_order: [], depth: 2, children_per_level: 8, rows_per_child: null }).rowsPerChild,
    ).toBeUndefined();
    expect(toPersistedSpec({ dimensionOrder: [], depth: 2, childrenPerLevel: 8 }).rows_per_child).toBeNull();
  });
});

describe("buildCascadeBundle (local mode)", () => {
  it("fans out top-N children per level, ranked by the lead measure", async () => {
    const b = await buildCascadeBundle(SQL, { columns, rows }, cols, null, resolve());
    expect(b.queries).toBe(0); // local: no fetches
    expect(b.truncated).toBe(false);
    // Regions ranked by AMOUNT sum: NA 150, EU 100, APAC 20.
    expect(b.root.children.map((c) => c.path[0].value)).toEqual(["NA", "EU", "APAC"]);
    const na = b.root.children[0];
    expect(na.path).toEqual([{ column: "REGION", value: "NA" }]);
    expect(na.rowCount).toBe(2);
    // Its customers are leaf sections with detail rows.
    expect(na.children.map((c) => c.path[1].value)).toEqual(["Acme", "Beta"]);
    expect(na.children[0].path).toEqual([
      { column: "REGION", value: "NA" },
      { column: "CUSTOMER", value: "Acme" },
    ]);
    expect(na.children[0].detailRows).toHaveLength(1);
    expect(na.children[0].children).toHaveLength(0);
  });

  it("respects depth=1 (no grandchildren; level-1 sections are leaves)", async () => {
    const b = await buildCascadeBundle(SQL, { columns, rows }, cols, null, resolve({ depth: 1 }));
    expect(b.root.children).toHaveLength(3);
    expect(b.root.children[0].children).toHaveLength(0);
    expect(b.root.children[0].detailRows).toHaveLength(2);
  });

  it("caps children per level and rolls the rest into Others", async () => {
    const b = await buildCascadeBundle(SQL, { columns, rows }, cols, null, resolve({ childrenPerLevel: 2, depth: 1 }));
    expect(b.root.children.map((c) => c.path[0].value)).toEqual(["NA", "EU"]);
    expect(b.root.othersRollup).toMatchObject({ count: 1 });
    expect(b.root.othersRollup!.label).toContain("region");
  });

  it("returns a flat root (no children) when there is no dimension", async () => {
    const oneCol = ["AMOUNT"];
    const oneMeasure: ColumnMeta[] = [{ name: "AMOUNT", index: 0, type: "currency", isMeasure: true, isInteger: false, numericAligned: true, agg: "sum" }];
    const r = resolveCascade(DEFAULT_CASCADE_SPEC, oneCol, oneMeasure, null);
    expect(r.dimIndices).toHaveLength(0);
    const b = await buildCascadeBundle("SELECT SUM(amount) amount FROM s", { columns: oneCol, rows: [[300]] }, oneMeasure, null, r);
    expect(b.root.children).toHaveLength(0);
    expect(b.root.detailRows).toHaveLength(1);
  });
});

describe("buildCascadeBundle (live mode)", () => {
  it("fetches each child via buildPullDetailSql binds (never interpolated) and counts queries", async () => {
    const run = vi.fn(async (_sql: string, binds: Record<string, unknown>) => {
      const want = Object.values(binds).map(String);
      return { columns, rows: rows.filter((r) => want.every((v) => r.map(String).includes(v))) };
    });
    const b = await buildCascadeBundle(SQL, { columns, rows }, cols, null, resolve({ depth: 1 }), run);
    expect(b.queries).toBeGreaterThan(0);
    // A region fetch wraps the approved SQL and binds the value.
    const calls = run.mock.calls as unknown as Array<[string, Record<string, unknown>]>;
    const naCall = calls.find((c) => c[1].p0 === "NA");
    expect(naCall).toBeTruthy();
    expect(naCall![0]).toMatch(/SELECT \* FROM \(/i);
    expect(naCall![0]).toContain('"REGION" = :p0');
  });

  it("emits IS NULL (no bind) for a null dimension bucket", async () => {
    const withNull: unknown[][] = [...rows, [null, "Zed", 5]];
    const run = vi.fn(async () => ({ columns, rows: [] }));
    await buildCascadeBundle(SQL, { columns, rows: withNull }, cols, null, resolve({ depth: 1 }), run);
    const calls = run.mock.calls as unknown as Array<[string, Record<string, unknown>]>;
    const nullCall = calls.find((c) => /"REGION" IS NULL/.test(c[0]));
    expect(nullCall).toBeTruthy();
    expect(Object.keys(nullCall![1])).toHaveLength(0); // no bind for IS NULL
  });

  it("isolates a failed child as a sanitized error without aborting the bundle", async () => {
    const run = vi.fn(async (_sql: string, binds: Record<string, unknown>) => {
      if (binds.p0 === "EU") throw new Error("boom");
      return { columns, rows: [] };
    });
    const b = await buildCascadeBundle(SQL, { columns, rows }, cols, null, resolve({ depth: 1 }), run);
    const eu = b.root.children.find((c) => c.path[0].value === "EU")!;
    expect(eu.error).toBeTruthy();
    const na = b.root.children.find((c) => c.path[0].value === "NA")!;
    expect(na.error).toBeUndefined();
  });
});
