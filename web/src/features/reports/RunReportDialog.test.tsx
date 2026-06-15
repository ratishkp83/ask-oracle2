import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RunReportDialog } from "./RunReportDialog";
import { SessionProvider } from "@/app/session";
import type { ExecuteResult, ProfilePublic, Report } from "@/lib/api/schemas";

vi.mock("@/lib/api/endpoints", () => ({
  getProfiles: vi.fn(),
  runReport: vi.fn(),
}));
import { getProfiles, runReport } from "@/lib/api/endpoints";

const user = () => userEvent.setup({ pointerEventsCheck: 0 });

const PROFILE: ProfilePublic = {
  id: "p1",
  name: "XE (read-only)",
  host: "127.0.0.1",
  port: 1521,
  service_name: "XEPDB1",
  current_schema: "AOR_DEMO",
  username: "aor_readonly",
  environment: "DEV",
};

const REPORT: Report = {
  id: "rep1",
  name: "Trial balance",
  description: "",
  sql: "SELECT * FROM gl_balances WHERE ledger_id = :ledger_id",
  parameters: [{ name: "ledger_id", label: "Ledger ID", type: "number", required: true }],
  default_profile_id: null,
  template_id: null,
  created_at: "x",
  updated_at: "x",
};

const RESULT: ExecuteResult = {
  columns: ["LEDGER_ID", "AMOUNT"],
  rows: [[1, 100]],
  elapsed_seconds: 0.02,
  row_count: 1,
  truncated: false,
};

function renderDialog(report: Report, onResult = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <MemoryRouter>
          <RunReportDialog report={report} onResult={onResult} />
        </MemoryRouter>
      </SessionProvider>
    </QueryClientProvider>,
  );
  return { onResult };
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getProfiles).mockReset();
  vi.mocked(runReport).mockReset();
});
afterEach(cleanup);

describe("RunReportDialog", () => {
  it("blocks the run and guides to Connections when none is active", async () => {
    vi.mocked(getProfiles).mockResolvedValue([]);
    const u = user();
    renderDialog(REPORT);

    await u.click(screen.getByRole("button", { name: /^run$/i }));
    await screen.findByRole("dialog");

    expect(screen.getByText(/no active connection/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run report/i })).toBeDisabled();
  });

  it("keeps the run disabled until a required parameter is filled", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    const u = user();
    renderDialog(REPORT);

    await u.click(screen.getByRole("button", { name: /^run$/i }));
    await screen.findByRole("dialog");
    expect(screen.getByRole("button", { name: /run report/i })).toBeDisabled();

    await u.type(screen.getByLabelText(/ledger id/i), "55");
    expect(screen.getByRole("button", { name: /run report/i })).toBeEnabled();
  });

  it("runs with coerced binds and the active profile, then returns the result", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    vi.mocked(runReport).mockResolvedValue(RESULT);
    const u = user();
    const { onResult } = renderDialog(REPORT);

    await u.click(screen.getByRole("button", { name: /^run$/i }));
    await screen.findByRole("dialog");
    await u.type(screen.getByLabelText(/ledger id/i), "55");
    await u.click(screen.getByRole("button", { name: /run report/i }));

    await waitFor(() =>
      expect(vi.mocked(runReport)).toHaveBeenCalledWith("rep1", { profile_id: "p1", binds: { ledger_id: 55 } }),
    );
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(REPORT, RESULT));
  });
});
