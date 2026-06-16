import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CascadeReportDialog } from "./CascadeReportDialog";
import { ColumnMeta } from "@/lib/derive/columns";

vi.mock("@/lib/api/endpoints", () => ({
  emailBundle: vi.fn(),
  createReport: vi.fn(),
}));
import { createReport, emailBundle } from "@/lib/api/endpoints";

const user = () => userEvent.setup({ pointerEventsCheck: 0 });

const columns = ["REGION", "AMOUNT"];
const cols: ColumnMeta[] = [
  { name: "REGION", index: 0, type: "category", isMeasure: false, isInteger: false, numericAligned: false },
  { name: "AMOUNT", index: 1, type: "currency", isMeasure: true, isInteger: false, numericAligned: true, agg: "sum" },
];
const rows: unknown[][] = [
  ["NA", 100],
  ["EU", 60],
  ["APAC", 20],
];

function renderDialog(savable = true) {
  return render(
    <CascadeReportDialog
      reportSql="SELECT region, SUM(amount) amount FROM s GROUP BY region"
      columns={columns}
      reportRows={rows}
      cols={cols}
      sqlMeta={null}
      reportTitle="AR by region"
      savable={savable}
    />,
  );
}

beforeEach(() => {
  vi.mocked(emailBundle).mockReset();
  vi.mocked(createReport).mockReset();
});
afterEach(cleanup);

describe("CascadeReportDialog", () => {
  it("builds the bundle on open and downloads it as a single HTML file", async () => {
    const u = user();
    const blobs: Blob[] = [];
    const oc = URL.createObjectURL;
    const orv = URL.revokeObjectURL;
    (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL = (b: Blob) => {
      blobs.push(b);
      return "blob:x";
    };
    (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = () => {};
    try {
      renderDialog();
      await u.click(screen.getByRole("button", { name: /^report$/i }));
      await u.click(await screen.findByRole("button", { name: /download html/i }));
      await waitFor(() => expect(blobs.length).toBeGreaterThan(0));
      expect(blobs[0].type).toContain("text/html");
    } finally {
      URL.createObjectURL = oc;
      URL.revokeObjectURL = orv;
    }
  });

  it("emails the bundle through /reports/email-bundle (the html, not row data)", async () => {
    vi.mocked(emailBundle).mockResolvedValue({ status: "ok", message: "Sent to 1 recipient" });
    const u = user();
    renderDialog();
    await u.click(screen.getByRole("button", { name: /^report$/i }));
    await screen.findByRole("button", { name: /download html/i }); // wait for the build
    await u.click(screen.getByRole("button", { name: /^email$/i }));
    await u.type(screen.getByPlaceholderText(/name@company/i), "cfo@corp.io");
    await u.click(screen.getByRole("button", { name: /send to 1 recipient/i }));
    await waitFor(() => expect(vi.mocked(emailBundle)).toHaveBeenCalledTimes(1));
    const arg = vi.mocked(emailBundle).mock.calls[0][0];
    expect(arg.to).toBe("cfo@corp.io");
    expect(arg.html).toContain("<!doctype html>");
    expect(await screen.findByText(/sent to 1 recipient/i)).toBeInTheDocument();
  });

  it("saves a cascading report carrying the cascade spec", async () => {
    vi.mocked(createReport).mockResolvedValue({
      id: "r1",
      name: "AR by region",
      description: "",
      sql: "",
      parameters: [],
      created_at: "x",
      updated_at: "x",
    });
    const u = user();
    renderDialog(true);
    await u.click(screen.getByRole("button", { name: /^report$/i }));
    await screen.findByRole("button", { name: /download html/i });
    await u.click(screen.getByRole("button", { name: /^save$/i }));
    await u.click(screen.getByRole("button", { name: /save report/i }));
    await waitFor(() => expect(vi.mocked(createReport)).toHaveBeenCalledTimes(1));
    const arg = vi.mocked(createReport).mock.calls[0][0];
    expect(arg.name).toBe("AR by region");
    expect(arg.cascade?.dimension_order).toEqual(["REGION"]);
  });

  it("hides Save when not savable", async () => {
    const u = user();
    renderDialog(false);
    await u.click(screen.getByRole("button", { name: /^report$/i }));
    await screen.findByRole("button", { name: /download html/i });
    expect(screen.queryByRole("button", { name: /^save$/i })).not.toBeInTheDocument();
  });
});
