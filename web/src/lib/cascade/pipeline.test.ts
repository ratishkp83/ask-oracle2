import { describe, it, expect } from "vitest";
import { SAMPLE_RESULT, SAMPLE_SQL, SAMPLE_QUESTION } from "@/features/ask/sampleResult";
import { classifyColumns } from "../derive/columns";
import { parseSelectMeta } from "../derive/sql";
import { resolveCascade, DEFAULT_CASCADE_SPEC } from "./spec";
import { buildCascadeBundle } from "./bundle";
import { renderBundleHtml } from "./renderHtml";

describe("cascade bundle on the sample result (repro)", () => {
  it("builds + renders without throwing", async () => {
    const sqlMeta = parseSelectMeta(SAMPLE_SQL);
    const cols = classifyColumns(SAMPLE_RESULT.columns, SAMPLE_RESULT.rows, sqlMeta);
    const resolved = resolveCascade(DEFAULT_CASCADE_SPEC, SAMPLE_RESULT.columns, cols, sqlMeta);
    const bundle = await buildCascadeBundle(
      SAMPLE_SQL,
      { columns: SAMPLE_RESULT.columns, rows: SAMPLE_RESULT.rows },
      cols,
      sqlMeta,
      resolved,
    );
    const html = renderBundleHtml(bundle, { title: SAMPLE_QUESTION, question: SAMPLE_QUESTION, sql: SAMPLE_SQL });
    expect(html.startsWith("<!doctype html>")).toBe(true);
    expect(bundle.root.children.length).toBeGreaterThan(0);
  });
});
