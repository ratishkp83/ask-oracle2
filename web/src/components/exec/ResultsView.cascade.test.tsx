import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultsView } from "./ResultsView";
import { ExecuteResult } from "@/lib/api/schemas";

// Recharts doesn't lay out in jsdom (ResponsiveContainer measures to 0), so the
// DriverChart is mocked to a button per bar that calls onBarClick. This exercises
// ResultsView's cascade state machine (drill stack, breadcrumb, re-scoping,
// bottom-out) deterministically, without depending on chart rendering.
vi.mock("./DriverChart", () => ({
  DriverChart: ({ spec, onBarClick }: any) => (
    <div data-testid="chart">
      <span data-testid="chart-dim">{spec.dimensionName}</span>
      {spec.data.map((d: any) => (
        <button key={d.label} type="button" onClick={() => onBarClick?.(d.label)}>
          {d.label}
        </button>
      ))}
    </div>
  ),
}));

afterEach(cleanup);

const SQL = "SELECT region, customer, SUM(amount) total FROM t GROUP BY region, customer";
const RESULT: ExecuteResult = {
  columns: ["region", "customer", "total"],
  rows: [
    ["North", "Acme", 10],
    ["North", "Beta", 20],
    ["South", "Gamma", 30],
  ],
  elapsed_seconds: 0.01,
  row_count: 3,
  truncated: false,
};

describe("ResultsView — multi-level cascade", () => {
  it("descends region → customer → leaf, growing a breadcrumb, then offers pull", async () => {
    const user = userEvent.setup();
    const onPullQuery = vi.fn();
    render(<ResultsView question="Sales by region and customer" sql={SQL} result={RESULT} onPullQuery={onPullQuery} />);

    // Level 0: the breakdown groups by the first GROUP BY dimension (region).
    expect(screen.getByTestId("chart-dim")).toHaveTextContent("region");

    // Drill into a region → breadcrumb appears and the chart re-scopes to customer.
    await user.click(screen.getByRole("button", { name: "North" }));
    const crumbs = screen.getByRole("navigation");
    expect(within(crumbs).getByText("North")).toBeInTheDocument();
    expect(screen.getByTestId("chart-dim")).toHaveTextContent("customer");

    // Drill into a customer → single record left → no further breakdown → pull.
    await user.click(screen.getByRole("button", { name: "Acme" }));
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
    const pull = screen.getByRole("button", { name: /pull acme data/i });
    await user.click(pull);
    expect(onPullQuery).toHaveBeenCalledWith("Show all detail for Acme");
  });

  it("breadcrumb 'Report' resets to the top level", async () => {
    const user = userEvent.setup();
    render(<ResultsView question="Sales" sql={SQL} result={RESULT} />);

    await user.click(screen.getByRole("button", { name: "North" }));
    expect(screen.getByTestId("chart-dim")).toHaveTextContent("customer");

    await user.click(screen.getByRole("button", { name: /report/i }));
    expect(screen.getByTestId("chart-dim")).toHaveTextContent("region");
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  // Regression: the top-level ResultScope must receive reportSql/reportRows so the
  // cascading-report dialog builds a bundle (instead of throwing on undefined rows),
  // and the Download action produces an HTML blob.
  it("builds a cascading report and downloads it as HTML from the top level", async () => {
    const user = userEvent.setup();
    const blobs: Blob[] = [];
    const origCreate = URL.createObjectURL;
    const origRevoke = URL.revokeObjectURL;
    (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL = (b: Blob) => {
      blobs.push(b);
      return "blob:x";
    };
    (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = () => {};
    try {
      render(<ResultsView question="Sales by region" sql={SQL} result={RESULT} />);
      await user.click(await screen.findByRole("button", { name: /^report$/i }));
      // The dialog builds the bundle (local mode) and then offers Download.
      await user.click(await screen.findByRole("button", { name: /download html/i }));
      await waitFor(() => expect(blobs.length).toBeGreaterThan(0));
      expect(blobs[0].type).toContain("text/html");
      expect(screen.queryByText(/couldn’t build/i)).not.toBeInTheDocument();
    } finally {
      URL.createObjectURL = origCreate;
      URL.revokeObjectURL = origRevoke;
    }
  });
});
