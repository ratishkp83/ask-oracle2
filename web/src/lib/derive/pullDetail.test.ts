import { describe, expect, it } from "vitest";
import { buildPullDetailSql } from "./pullDetail";
import { NULL_KEY } from "./cascade";

const APPROVED =
  "SELECT region, customer, SUM(amount) total FROM sales GROUP BY region, customer";

describe("buildPullDetailSql", () => {
  it("wraps the approved SELECT with no WHERE when there are no filters", () => {
    const { sql, binds } = buildPullDetailSql(APPROVED, []);
    expect(sql).toBe(`SELECT * FROM (\n${APPROVED}\n)`);
    expect(sql.startsWith("SELECT * FROM (")).toBe(true); // read-only shape preserved
    expect(binds).toEqual({});
  });

  it("adds a bound equality predicate for a single filter", () => {
    const { sql, binds } = buildPullDetailSql(APPROVED, [{ column: "REGION", value: "North" }]);
    expect(sql).toContain(`SELECT * FROM (\n${APPROVED}\n)`);
    expect(sql).toContain(`WHERE "REGION" = :p0`);
    expect(binds).toEqual({ p0: "North" });
  });

  it("ANDs multiple filters with positional binds", () => {
    const { sql, binds } = buildPullDetailSql(APPROVED, [
      { column: "REGION", value: "North" },
      { column: "CUSTOMER", value: "Acme" },
    ]);
    expect(sql).toContain(`WHERE "REGION" = :p0`);
    expect(sql).toContain(`AND "CUSTOMER" = :p1`);
    expect(binds).toEqual({ p0: "North", p1: "Acme" });
  });

  it("uses IS NULL (no bind) for a NULL bucket and keeps binds positional", () => {
    const { sql, binds } = buildPullDetailSql(APPROVED, [
      { column: "REGION", value: NULL_KEY },
      { column: "CUSTOMER", value: "Acme" },
    ]);
    expect(sql).toContain(`"REGION" IS NULL`);
    expect(sql).not.toContain(":p0");
    expect(sql).toContain(`"CUSTOMER" = :p1`);
    expect(binds).toEqual({ p1: "Acme" }); // no bind for the IS NULL predicate
  });

  it("strips a trailing semicolon/whitespace before nesting", () => {
    const { sql } = buildPullDetailSql(APPROVED + " ;\n", [{ column: "REGION", value: "North" }]);
    expect(sql).toContain(`SELECT * FROM (\n${APPROVED}\n)`);
    expect(sql).not.toContain(";");
  });

  it("escapes embedded double-quotes in an identifier", () => {
    const { sql } = buildPullDetailSql(APPROVED, [{ column: 'WEIRD"COL', value: "x" }]);
    expect(sql).toContain(`"WEIRD""COL" = :p0`);
  });
});
