import { describe, expect, it } from "vitest";
import { ProfileListSchema, SchemaSummaryListSchema } from "./schemas";

// ITM-027 / P9B-R1-F3 — enum drift must not fail the WHOLE list parse and blank
// the picker; an unexpected value degrades to a default instead of throwing.
describe("Zod boundary — graceful enum degradation", () => {
  it("keeps the profile list when an environment value drifts (defaults it)", () => {
    const parsed = ProfileListSchema.parse([
      { id: "p1", name: "Prod", host: "h", port: 1521, username: "u", environment: "PROD" },
      { id: "p2", name: "Odd", host: "h", port: 1521, username: "u", environment: "STAGING" },
    ]);
    expect(parsed).toHaveLength(2);
    expect(parsed[0].environment).toBe("PROD");
    expect(parsed[1].environment).toBe("DEV"); // drift → default, list intact
  });

  it("keeps the schema list when a source value drifts (defaults it)", () => {
    const parsed = SchemaSummaryListSchema.parse([
      { id: "s1", name: "A", source: "weird", table_count: 3, created_at: "x", updated_at: "y" },
    ]);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].source).toBe("upload");
  });
});
