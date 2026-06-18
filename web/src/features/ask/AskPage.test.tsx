import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AskPage } from "./AskPage";
import { SessionProvider } from "@/app/session";
import { ApiError } from "@/lib/api/client";
import type { ExecuteResult, SchemaSummary } from "@/lib/api/schemas";

// Control the whole API surface the Ask tree touches.
vi.mock("@/lib/api/endpoints", () => ({
  nl2sql: vi.fn(),
  execute: vi.fn(),
  getSchemas: vi.fn(),
  downloadXlsx: vi.fn(),
  emailReport: vi.fn(),
}));
// Recharts doesn't lay out in jsdom — stub the chart with a clickable button per bar
// (same approach as the cascade test) so drill-down can be exercised.
vi.mock("@/components/exec/DriverChart", () => ({
  DriverChart: ({ spec, onBarClick }: any) => (
    <div data-testid="chart">
      {spec.data.map((d: any) => (
        <button key={d.label} type="button" onClick={() => onBarClick?.(d.label)}>
          {d.label}
        </button>
      ))}
    </div>
  ),
}));

import { nl2sql, execute, getSchemas } from "@/lib/api/endpoints";

const SCHEMA: SchemaSummary = {
  id: "s1",
  name: "AOR_DEMO",
  source: "upload",
  profile_id: null,
  table_count: 12,
  created_at: "2026-06-14T00:00:00Z",
  updated_at: "2026-06-14T00:00:00Z",
};

const PROPOSAL = {
  sql: "SELECT region, SUM(amount) total FROM sales GROUP BY region",
  explanation: "Totals revenue by region.",
  confidence: { level: "High", reasons: ["Schema match on SALES.REGION"] },
};

const RESULT: ExecuteResult = {
  columns: ["REGION", "TOTAL"],
  rows: [
    ["North", 100],
    ["South", 200],
  ],
  elapsed_seconds: 0.02,
  row_count: 2,
  truncated: false,
};

function renderAsk() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <AskPage />
      </SessionProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(nl2sql).mockReset();
  vi.mocked(execute).mockReset();
  vi.mocked(getSchemas).mockReset().mockResolvedValue([SCHEMA]);
});
afterEach(cleanup);

describe("AskPage state machine", () => {
  it("generates SQL with the session schema_id, then shows the editable review + confidence", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    vi.mocked(nl2sql).mockResolvedValue(PROPOSAL);
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));

    // Review step: editable SQL + confidence + explanation.
    const sqlBox = await screen.findByRole("textbox", { name: /proposed sql/i });
    expect(sqlBox).toHaveValue(PROPOSAL.sql);
    expect(screen.getByText(/High confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Totals revenue by region/i)).toBeInTheDocument();

    // nl2sql carried the schema_id from session context.
    expect(nl2sql).toHaveBeenCalledWith(
      expect.objectContaining({ natural_language: "Revenue by region", schema_id: "s1" }),
    );
  });

  it("shows the model's interpreted question (typo-corrected) in review and results", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    vi.mocked(nl2sql).mockResolvedValue({ ...PROPOSAL, interpreted_question: "Revenue by region?" });
    vi.mocked(execute).mockResolvedValue(RESULT);
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "rev by regn");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));

    // Review headline is the interpreted question; the raw typed text is shown beneath.
    expect(await screen.findByRole("heading", { name: /Revenue by region\?/i })).toBeInTheDocument();
    expect(screen.getByText(/You asked:/i)).toBeInTheDocument();
    expect(screen.getByText(/rev by regn/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /run query/i }));

    // Results correlate to intent: "Showing results for" + the interpreted question.
    expect(await screen.findByText(/Showing results for/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Revenue by region\?/i })).toBeInTheDocument();
  });

  it("runs the (edited) SQL via /execute with the session profile_id and renders results", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    vi.mocked(nl2sql).mockResolvedValue(PROPOSAL);
    vi.mocked(execute).mockResolvedValue(RESULT);
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));

    const sqlBox = await screen.findByRole("textbox", { name: /proposed sql/i });
    await user.clear(sqlBox);
    await user.type(sqlBox, "SELECT region, SUM(amount) total FROM sales GROUP BY region -- edited");
    await user.click(screen.getByRole("button", { name: /run query/i }));

    // /execute received the edited SQL + the session connection (never a secret).
    expect(execute).toHaveBeenCalledWith(
      expect.objectContaining({ profile_id: "p1", sql: expect.stringContaining("-- edited") }),
    );

    // Real result flowed into the executive view: detail row count + the result's
    // own columns reached the grid header. (Grid rows are virtualized → not laid
    // out in jsdom, so we assert on the non-virtualized header + count.)
    const grid = await screen.findByText(/Detail ·/i);
    expect(grid).toHaveTextContent(/2 rows/i);
    expect(screen.getByRole("columnheader", { name: "REGION" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "TOTAL" })).toBeInTheDocument();
  });

  it("surfaces an nl2sql failure as a sanitized error_id banner and stays on the form", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(nl2sql).mockRejectedValue(new ApiError("The model is temporarily unavailable.", 503, "REQ-abc123"));
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/temporarily unavailable/i)).toBeInTheDocument();
    expect(within(alert).getByText(/REQ-abc123/)).toBeInTheDocument();
    // Back on the form, not the review.
    expect(screen.getByRole("button", { name: /generate sql/i })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /proposed sql/i })).not.toBeInTheDocument();
  });

  it("disables Run with no connection (E10) and never calls /execute", async () => {
    // No profileId in session.
    window.localStorage.setItem("aor.schemaId", "s1");
    vi.mocked(nl2sql).mockResolvedValue(PROPOSAL);
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));

    const runBtn = await screen.findByRole("button", { name: /run query/i });
    expect(runBtn).toBeDisabled();
    expect(screen.getByText(/select a connection above to run/i)).toBeInTheDocument();
    await user.click(runBtn);
    expect(execute).not.toHaveBeenCalled();
  });

  it("pulls live detail: drill to a leaf → review the wrapped SQL + binds → execute", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    vi.mocked(nl2sql).mockResolvedValue(PROPOSAL);
    vi.mocked(execute).mockResolvedValue(RESULT); // aggregated result, then the detail
    const user = userEvent.setup();
    renderAsk();

    // Ask → review → run → aggregated results.
    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));
    await user.click(await screen.findByRole("button", { name: /run query/i }));

    // Drill the only dimension to a leaf, then pull its live detail.
    await user.click(await screen.findByRole("button", { name: "North" }));
    await user.click(await screen.findByRole("button", { name: /pull north data/i }));

    // Re-approval review for the deterministic wrap: wrapped SQL + bound value shown.
    const sqlBox = (await screen.findByRole("textbox", { name: /proposed sql/i })) as HTMLTextAreaElement;
    expect(sqlBox.value).toContain("SELECT * FROM (");
    expect(sqlBox.value).toContain('WHERE "REGION" = :p0');
    expect(screen.getByText(/bound values/i)).toBeInTheDocument();
    expect(screen.getByText(/:p0 = North/)).toBeInTheDocument();
    expect(screen.getByText(/review live-detail query/i)).toBeInTheDocument();

    // Approve → /execute runs the wrapped SQL with the bound value + session profile.
    vi.mocked(execute).mockClear();
    await user.click(screen.getByRole("button", { name: /run query/i }));
    expect(execute).toHaveBeenCalledWith(
      expect.objectContaining({
        profile_id: "p1",
        binds: { p0: "North" },
        sql: expect.stringContaining('WHERE "REGION" = :p0'),
      }),
    );
  });

  it("auto-run: asking goes straight to results without a review step", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    window.localStorage.setItem("aor.autoRun", "1");
    vi.mocked(nl2sql).mockResolvedValue(PROPOSAL);
    vi.mocked(execute).mockResolvedValue(RESULT);
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    // Seamless: results render; the manual review step was never shown.
    expect(await screen.findByText(/Detail ·/i)).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /proposed sql/i })).not.toBeInTheDocument();
    expect(nl2sql).toHaveBeenCalled();
    expect(execute).toHaveBeenCalledWith(
      expect.objectContaining({ profile_id: "p1", sql: PROPOSAL.sql }),
    );
  });

  it("off-topic: shows a notice and runs nothing, even with Auto-run on", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    window.localStorage.setItem("aor.autoRun", "1");
    vi.mocked(nl2sql).mockResolvedValue({
      sql: "",
      explanation: null,
      confidence: null,
      answerable: false,
      message: "I can only answer questions about your Oracle data.",
    });
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "how to swim");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    // Calm notice on the ask form; nothing proposed, nothing executed.
    expect(await screen.findByRole("status")).toHaveTextContent(/only answer questions about your oracle data/i);
    expect(execute).not.toHaveBeenCalled();
    expect(screen.queryByText(/Detail ·/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /proposed sql/i })).not.toBeInTheDocument();
  });

  it("auto-run falls back to the review step when no connection is set", async () => {
    window.localStorage.setItem("aor.schemaId", "s1");
    window.localStorage.setItem("aor.autoRun", "1"); // on, but no profileId
    vi.mocked(nl2sql).mockResolvedValue(PROPOSAL);
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    // No connection → can't auto-run; show the editable review with Run disabled.
    expect(await screen.findByRole("textbox", { name: /proposed sql/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run query/i })).toBeDisabled();
    expect(execute).not.toHaveBeenCalled();
  });

  it("Edit SQL: pull the query up from results, edit, and re-run", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    vi.mocked(nl2sql).mockResolvedValue(PROPOSAL);
    vi.mocked(execute).mockResolvedValue(RESULT);
    const user = userEvent.setup();
    renderAsk();

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));
    await user.click(await screen.findByRole("button", { name: /run query/i }));

    // From results, pull the query up to edit + re-run.
    await user.click(await screen.findByRole("button", { name: /edit sql/i }));
    const sqlBox = await screen.findByRole("textbox", { name: /proposed sql/i });
    await user.clear(sqlBox);
    await user.type(sqlBox, "SELECT region, SUM(amount) total FROM sales GROUP BY region -- v2");
    vi.mocked(execute).mockClear();
    await user.click(screen.getByRole("button", { name: /run query/i }));
    expect(execute).toHaveBeenCalledWith(
      expect.objectContaining({ profile_id: "p1", sql: expect.stringContaining("-- v2") }),
    );
  });

  it("the Auto-run toggle persists its state", async () => {
    const user = userEvent.setup();
    renderAsk();
    const sw = screen.getByRole("switch", { name: /auto-run/i });
    expect(sw).toHaveAttribute("aria-checked", "false");
    await user.click(sw);
    expect(sw).toHaveAttribute("aria-checked", "true");
    expect(window.localStorage.getItem("aor.autoRun")).toBe("1");
  });

  it("still shows the no-DB sample result on demand", async () => {
    const user = userEvent.setup();
    renderAsk();

    await user.click(screen.getByRole("button", { name: /see a sample result/i }));
    expect(await screen.findByText(/New question/i)).toBeInTheDocument();
    expect(nl2sql).not.toHaveBeenCalled();
    expect(execute).not.toHaveBeenCalled();
  });
});
