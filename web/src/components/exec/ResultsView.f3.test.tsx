import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultsView } from "./ResultsView";
import { ExecuteResult } from "@/lib/api/schemas";

// Recharts doesn't lay out in jsdom — stub the chart but echo its type so the test
// can confirm a trend LINE was chosen (the F3 dead-end case).
vi.mock("./DriverChart", () => ({
  DriverChart: ({ spec }: any) => <div data-testid="chart" data-type={spec.type} />,
}));

afterEach(cleanup);

// A date dimension ("MONTH") + measure → pickChart yields a non-drillable trend line.
const SQL = "SELECT month, SUM(amount) revenue FROM sales GROUP BY month";
const RESULT: ExecuteResult = {
  columns: ["MONTH", "REVENUE"],
  rows: [
    ["Jan", 100],
    ["Feb", 220],
    ["Mar", 180],
  ],
  elapsed_seconds: 0.01,
  row_count: 3,
  truncated: false,
};

describe("ResultsView — F3 trend path-to-detail", () => {
  it("offers Pull-live-detail beside a non-drillable trend line (live mode)", async () => {
    const user = userEvent.setup();
    const onPullDetail = vi.fn();
    render(<ResultsView question="Revenue by month" sql={SQL} result={RESULT} onPullDetail={onPullDetail} />);

    // A trend line was chosen (the case that used to dead-end).
    expect(screen.getByTestId("chart")).toHaveAttribute("data-type", "line");

    // F3: the pull affordance is present and pulls the current (top-level) scope.
    const pull = screen.getByRole("button", { name: /pull live detail/i });
    await user.click(pull);
    expect(onPullDetail).toHaveBeenCalledWith([]); // top level → no filters → whole detail
  });

  it("falls back to a fresh-question pull in demo mode (onPullQuery)", async () => {
    const user = userEvent.setup();
    const onPullQuery = vi.fn();
    render(<ResultsView question="Revenue by month" sql={SQL} result={RESULT} onPullQuery={onPullQuery} />);

    await user.click(screen.getByRole("button", { name: /pull live detail/i }));
    expect(onPullQuery).toHaveBeenCalledWith("Show all detail");
  });

  it("shows no pull affordance when there is no pull handler", () => {
    render(<ResultsView question="Revenue by month" sql={SQL} result={RESULT} />);
    expect(screen.getByTestId("chart")).toHaveAttribute("data-type", "line");
    expect(screen.queryByRole("button", { name: /pull live detail/i })).not.toBeInTheDocument();
  });

  it("F2 — disables the live pull when the result has duplicate column names", () => {
    // Duplicate output column ("REVENUE") would make the wrap's inline view
    // ambiguous (ORA-00918), so the live pull is withheld (ITM-032).
    const dup: ExecuteResult = {
      columns: ["MONTH", "REVENUE", "REVENUE"],
      rows: [
        ["Jan", 100, 1],
        ["Feb", 220, 2],
        ["Mar", 180, 3],
      ],
      elapsed_seconds: 0.01,
      row_count: 3,
      truncated: false,
    };
    render(
      <ResultsView question="Revenue by month" sql={SQL} result={dup} onPullDetail={vi.fn()} />,
    );
    // The trend line still renders; the live-pull affordance does not.
    expect(screen.getByTestId("chart")).toHaveAttribute("data-type", "line");
    expect(screen.queryByRole("button", { name: /pull live detail/i })).not.toBeInTheDocument();
  });
});
