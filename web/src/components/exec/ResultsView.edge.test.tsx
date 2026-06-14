import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ResultsView } from "./ResultsView";
import { ExecuteResult } from "@/lib/api/schemas";

afterEach(cleanup);

describe("ResultsView edge states", () => {
  it("E1 — renders a calm empty state with a refine affordance for 0 rows", () => {
    const result: ExecuteResult = {
      columns: ["REGION", "AMOUNT"],
      rows: [],
      elapsed_seconds: 0.01,
      row_count: 0,
      truncated: false,
    };
    render(
      <ResultsView question="Sales by region" sql="SELECT 1 FROM dual WHERE 1=0" result={result} onPullQuery={() => {}} />,
    );
    expect(screen.getByText("No rows matched")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refine the question/i })).toBeInTheDocument();
    // The SQL disclosure is still available for trust.
    expect(screen.getByRole("button", { name: /view sql/i })).toBeInTheDocument();
  });

  it("E2 — promotes a single value (1×1) to a hero figure", () => {
    const result: ExecuteResult = {
      columns: ["TOTAL"],
      rows: [[4500000]],
      elapsed_seconds: 0.02,
      row_count: 1,
      truncated: false,
    };
    render(<ResultsView question="Total outstanding AR" sql="SELECT SUM(amount) total FROM ar" result={result} />);
    expect(screen.getByText("$4.50M")).toBeInTheDocument(); // currency-aware hero
    expect(screen.getByText("Total")).toBeInTheDocument(); // column label as eyebrow
  });
});
