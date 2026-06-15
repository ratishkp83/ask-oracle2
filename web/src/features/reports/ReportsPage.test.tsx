import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ReportsPage } from "./ReportsPage";
import { SessionProvider } from "@/app/session";
import { ApiError } from "@/lib/api/client";
import type { ExecuteResult, ProfilePublic, Report, Template } from "@/lib/api/schemas";

vi.mock("@/lib/api/endpoints", () => ({
  getReports: vi.fn(),
  deleteReport: vi.fn(),
  runReport: vi.fn(),
  getTemplates: vi.fn(),
  createReport: vi.fn(),
  updateReport: vi.fn(),
  getProfiles: vi.fn(),
  // Pulled in via the reused ResultsView / EmailDialog.
  downloadXlsx: vi.fn(),
  emailReport: vi.fn(),
}));
import { deleteReport, getProfiles, getReports, getTemplates, runReport } from "@/lib/api/endpoints";

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

const REPORTS: Report[] = [
  { id: "rep1", name: "Total invoices", description: "Grand total", sql: "SELECT COUNT(*) AS TOTAL FROM ap_invoices_all", parameters: [], default_profile_id: null, template_id: null, created_at: "x", updated_at: "x" },
  { id: "rep2", name: "AP spend", description: "By supplier", sql: "SELECT vendor_id FROM ap_invoices_all", parameters: [{ name: "org_id", label: "Org", type: "number", required: true }], default_profile_id: null, template_id: "ap_x", created_at: "x", updated_at: "x" },
];

const HERO: ExecuteResult = {
  columns: ["TOTAL"],
  rows: [[42]],
  elapsed_seconds: 0.01,
  row_count: 1,
  truncated: false,
};

const TEMPLATE: Template = {
  id: "gl_trial_balance",
  module: "GL",
  name: "GL Trial Balance (by account)",
  description: "Net debit/credit per account.",
  sql: "SELECT 1 FROM gl_balances WHERE ledger_id = :ledger_id",
  parameters: [{ name: "ledger_id", label: "Ledger ID", type: "number", required: true }],
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <MemoryRouter>
          <ReportsPage />
        </MemoryRouter>
      </SessionProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getReports).mockReset();
  vi.mocked(deleteReport).mockReset();
  vi.mocked(runReport).mockReset();
  vi.mocked(getTemplates).mockReset();
  vi.mocked(getProfiles).mockResolvedValue([]);
});
afterEach(cleanup);

describe("ReportsPage", () => {
  it("lists saved reports with parameter counts", async () => {
    vi.mocked(getReports).mockResolvedValue(REPORTS);
    renderPage();

    expect(await screen.findByText("Total invoices")).toBeInTheDocument();
    expect(screen.getByText("AP spend")).toBeInTheDocument();
    expect(screen.getByText(/1 parameter/)).toBeInTheDocument();
  });

  it("shows a calm empty state with a create affordance", async () => {
    vi.mocked(getReports).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/no saved reports yet/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /new report/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("surfaces a sanitized error when the list fails to load", async () => {
    vi.mocked(getReports).mockRejectedValue(new ApiError("The API is unreachable.", 0, "err_3"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(/unreachable.*ref err_3/i);
  });

  it("runs a no-parameter report and shows the executive Results view", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(getReports).mockResolvedValue(REPORTS);
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    vi.mocked(runReport).mockResolvedValue(HERO);
    const u = user();
    renderPage();

    const row = (await screen.findByText("Total invoices")).closest("li")!;
    await u.click(within(row).getByRole("button", { name: /^run$/i }));
    const dialog = await screen.findByRole("dialog");
    await u.click(within(dialog).getByRole("button", { name: /run report/i }));

    await waitFor(() => expect(vi.mocked(runReport)).toHaveBeenCalledWith("rep1", { profile_id: "p1", binds: undefined }));
    // Switched to the executive Results view (the single figure is promoted to a hero).
    expect(await screen.findByText(/\b42\b/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /from template/i })).not.toBeInTheDocument();
  });

  it("deletes a report after confirmation", async () => {
    vi.mocked(getReports).mockResolvedValue(REPORTS);
    vi.mocked(deleteReport).mockResolvedValue(undefined);
    const u = user();
    renderPage();

    const row = (await screen.findByText("AP spend")).closest("li")!;
    await u.click(within(row).getByRole("button", { name: /delete ap spend/i }));
    const dialog = await screen.findByRole("dialog");
    await u.click(within(dialog).getByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(vi.mocked(deleteReport)).toHaveBeenCalledWith("rep2"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("seeds the editor from a chosen template", async () => {
    vi.mocked(getReports).mockResolvedValue(REPORTS);
    vi.mocked(getTemplates).mockResolvedValue([TEMPLATE]);
    const u = user();
    renderPage();

    await screen.findByText("Total invoices");
    await u.click(screen.getByRole("button", { name: /from template/i }));
    await u.click(await screen.findByText("GL Trial Balance (by account)"));

    // Editor opens, pre-filled from the template.
    expect(await screen.findByRole("heading", { name: /new report/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("GL Trial Balance (by account)");
    expect(screen.getByLabelText(/parameter 1 name/i)).toHaveValue("ledger_id");
  });
});
