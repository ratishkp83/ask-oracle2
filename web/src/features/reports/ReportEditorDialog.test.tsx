import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReportEditorDialog } from "./ReportEditorDialog";
import type { Report } from "@/lib/api/schemas";

vi.mock("@/lib/api/endpoints", () => ({
  getProfiles: vi.fn(),
  createReport: vi.fn(),
  updateReport: vi.fn(),
}));
import { createReport, getProfiles, updateReport } from "@/lib/api/endpoints";

const user = () => userEvent.setup({ pointerEventsCheck: 0 });

const EXISTING: Report = {
  id: "rep1",
  name: "Monthly AP spend",
  description: "By supplier",
  sql: "SELECT vendor_id, SUM(invoice_amount) FROM ap_invoices_all GROUP BY vendor_id",
  parameters: [{ name: "org_id", label: "Org", type: "number", required: true }],
  default_profile_id: null,
  template_id: null,
  created_at: "x",
  updated_at: "x",
};

function renderEditor(props: Partial<React.ComponentProps<typeof ReportEditorDialog>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onOpenChange = props.onOpenChange ?? vi.fn();
  render(
    <QueryClientProvider client={qc}>
      <ReportEditorDialog open onOpenChange={onOpenChange} {...props} />
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([]);
  vi.mocked(createReport).mockReset();
  vi.mocked(updateReport).mockReset();
});
afterEach(cleanup);

describe("ReportEditorDialog", () => {
  it("creates a report with the entered name + SQL and closes on success", async () => {
    vi.mocked(createReport).mockResolvedValue(EXISTING);
    const u = user();
    const { onOpenChange } = renderEditor();

    expect(screen.getByRole("heading", { name: /new report/i })).toBeInTheDocument();
    const save = screen.getByRole("button", { name: /create report/i });
    expect(save).toBeDisabled(); // name + sql required

    await u.type(screen.getByLabelText("Name"), "AP spend");
    await u.type(screen.getByLabelText(/SQL/i), "SELECT 1 FROM dual");
    expect(save).toBeEnabled();
    await u.click(save);

    await waitFor(() =>
      expect(vi.mocked(createReport)).toHaveBeenCalledWith(
        expect.objectContaining({ name: "AP spend", sql: "SELECT 1 FROM dual", parameters: [] }),
      ),
    );
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("adds a typed parameter that is included in the created report", async () => {
    vi.mocked(createReport).mockResolvedValue(EXISTING);
    const u = user();
    renderEditor();

    await u.type(screen.getByLabelText("Name"), "Param report");
    await u.type(screen.getByLabelText(/SQL/i), "SELECT * FROM t WHERE id = :org_id");
    await u.click(screen.getByRole("button", { name: /^add$/i }));
    await u.type(screen.getByLabelText(/parameter 1 name/i), "org_id");
    await u.click(screen.getByRole("button", { name: /create report/i }));

    await waitFor(() =>
      expect(vi.mocked(createReport)).toHaveBeenCalledWith(
        expect.objectContaining({
          parameters: [expect.objectContaining({ name: "org_id", type: "string", required: true })],
        }),
      ),
    );
  });

  it("pre-fills an existing report and saves via update", async () => {
    vi.mocked(updateReport).mockResolvedValue(EXISTING);
    const u = user();
    renderEditor({ report: EXISTING });

    expect(screen.getByRole("heading", { name: /edit report/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Monthly AP spend");
    expect(screen.getByLabelText(/parameter 1 name/i)).toHaveValue("org_id");

    await u.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() =>
      expect(vi.mocked(updateReport)).toHaveBeenCalledWith("rep1", expect.objectContaining({ name: "Monthly AP spend" })),
    );
  });
});
