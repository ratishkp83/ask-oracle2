import { describe, it, expect } from "vitest";
import { buildCascadeBundle } from "./bundle";
import { resolveCascade, DEFAULT_CASCADE_SPEC } from "./spec";
import { renderBundleHtml } from "./renderHtml";
import { ColumnMeta } from "../derive/columns";

const columns = ["REGION", "AMOUNT"];
const cols: ColumnMeta[] = [
  { name: "REGION", index: 0, type: "category", isMeasure: false, isInteger: false, numericAligned: false },
  { name: "AMOUNT", index: 1, type: "currency", isMeasure: true, isInteger: false, numericAligned: true, agg: "sum" },
];

async function bundle(rows: unknown[][]) {
  const resolved = resolveCascade(DEFAULT_CASCADE_SPEC, columns, cols, null);
  return buildCascadeBundle("SELECT region, SUM(amount) amount FROM s GROUP BY region", { columns, rows }, cols, null, resolved);
}

describe("renderBundleHtml", () => {
  it("produces a self-contained, script-free HTML document", async () => {
    const b = await bundle([
      ["North America", 1000],
      ["EMEA", 600],
      ["APAC", 200],
    ]);
    const html = renderBundleHtml(b, { title: "Outstanding by region", question: "outstanding by region" });
    expect(html.startsWith("<!doctype html>")).toBe(true);
    expect(html).toContain("<style>");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<link");
    expect(html).not.toMatch(/https?:\/\//); // no external assets
    expect(html).toContain("Outstanding by region"); // title
    expect(html).toContain("North America"); // a section
    expect(html).toContain("What stands out"); // insight band
  });

  it("HTML-escapes adversarial data values (P10-R6)", async () => {
    const b = await bundle([
      ["<script>alert(1)</script>", 1000],
      ["Safe & Sound", 500],
    ]);
    const html = renderBundleHtml(b, { title: "X", question: "x" });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).toContain("Safe &amp; Sound");
  });

  it("HTML-escapes the title, SQL disclosure, and column-name/KPI sinks (P10-R6)", async () => {
    // Adversarial column names flow into table headers, the KPI label, and the chart eyebrow.
    const evilCols = ["RE<b>GION", "AM<i>T"];
    const evilMeta: ColumnMeta[] = [
      { name: "RE<b>GION", index: 0, type: "category", isMeasure: false, isInteger: false, numericAligned: false },
      { name: "AM<i>T", index: 1, type: "currency", isMeasure: true, isInteger: false, numericAligned: true, agg: "sum" },
    ];
    const resolved = resolveCascade(DEFAULT_CASCADE_SPEC, evilCols, evilMeta, null);
    const b = await buildCascadeBundle(
      "SELECT 1",
      { columns: evilCols, rows: [["North", 10], ["South", 20]] },
      evilMeta,
      null,
      resolved,
    );
    const html = renderBundleHtml(b, {
      title: "<script>t</script>",
      question: "q",
      sql: "SELECT '<script>' FROM dual",
    });
    // No raw markup from any sink: title, sql, column header, KPI label, chart eyebrow.
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<b>");
    expect(html).not.toContain("<i>");
    // Escaped forms are present.
    expect(html).toContain("&lt;script&gt;t&lt;/script&gt;"); // title
    expect(html).toContain("&lt;b&gt;"); // dimension column header
    expect(html).toContain("&lt;i&gt;"); // measure name (KPI label / chart eyebrow)
  });

  it("includes a source-query disclosure when sql is provided", async () => {
    const b = await bundle([
      ["A", 10],
      ["B", 20],
    ]);
    const html = renderBundleHtml(b, { title: "X", question: "x", sql: "SELECT 1 FROM dual" });
    expect(html).toContain("Source query");
    expect(html).toContain("SELECT 1 FROM dual");
  });
});
