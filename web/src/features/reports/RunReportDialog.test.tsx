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
  execute: vi.fn(),
  getSchema: vi.fn(),
}));
import { execute, getProfiles, getSchema, runReport } from "@/lib/api/endpoints";
import type { SchemaRecord } from "@/lib/api/schemas";

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

const REPORT_LOOKUP: Report = {
  ...REPORT,
  parameters: [
    {
      name: "dept_id",
      label: "Department",
      type: "number",
      required: true,
      lookup_sql: "SELECT department_id, department_name FROM departments ORDER BY department_name",
    },
  ],
};

// A report whose bind has NO explicit lookup, but whose column is a FK in the schema.
const REPORT_AUTO: Report = {
  ...REPORT,
  sql: "SELECT employee_id, first_name FROM employees WHERE department_id = :dept_id",
  parameters: [{ name: "dept_id", label: "Department", type: "number", required: true }],
};

const SCHEMA: SchemaRecord = {
  id: "s1",
  name: "AOR_DEMO",
  source: "introspection",
  profile_id: null,
  table_count: 2,
  created_at: "x",
  updated_at: "x",
  definition: {
    tables: {
      EMPLOYEES: [
        { column_name: "EMPLOYEE_ID", is_primary_key: true, is_foreign_key: false },
        {
          column_name: "DEPARTMENT_ID",
          is_primary_key: false,
          is_foreign_key: true,
          references_table: "DEPARTMENTS",
          references_column: "DEPARTMENT_ID",
        },
      ],
      DEPARTMENTS: [
        { column_name: "DEPARTMENT_ID", is_primary_key: true, is_foreign_key: false },
        { column_name: "DEPARTMENT_NAME", is_primary_key: false, is_foreign_key: false },
      ],
    },
    relationships: [],
  },
};

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getProfiles).mockReset();
  vi.mocked(runReport).mockReset();
  vi.mocked(execute).mockReset();
  vi.mocked(getSchema).mockReset();
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

  it("exposes the report SQL via a View SQL disclosure", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    const u = user();
    renderDialog(REPORT);

    await u.click(screen.getByRole("button", { name: /^run$/i }));
    await screen.findByRole("dialog");
    expect(screen.getByText(/view sql/i)).toBeInTheDocument();
    expect(screen.getByText(/SELECT \* FROM gl_balances/i)).toBeInTheDocument();
  });

  it("renders a live dropdown for a parameter with a lookup and binds the chosen value", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    vi.mocked(execute).mockResolvedValue({
      columns: ["DEPARTMENT_ID", "DEPARTMENT_NAME"],
      rows: [[20, "Engineering"], [10, "Finance"]],
      elapsed_seconds: 0.01,
      row_count: 2,
      truncated: false,
    });
    vi.mocked(runReport).mockResolvedValue(RESULT);
    const u = user();
    const { onResult } = renderDialog(REPORT_LOOKUP);

    await u.click(screen.getByRole("button", { name: /^run$/i }));
    await screen.findByRole("dialog");

    // The lookup runs via the chokepoint and the options appear in a dropdown.
    await waitFor(() =>
      expect(vi.mocked(execute)).toHaveBeenCalledWith({
        sql: "SELECT department_id, department_name FROM departments ORDER BY department_name",
        profile_id: "p1",
      }),
    );
    const select = await screen.findByLabelText(/department/i);
    expect(await screen.findByRole("option", { name: "Engineering" })).toBeInTheDocument();
    await u.selectOptions(select, "20");
    await u.click(screen.getByRole("button", { name: /run report/i }));

    await waitFor(() =>
      expect(vi.mocked(runReport)).toHaveBeenCalledWith("rep1", { profile_id: "p1", binds: { dept_id: 20 } }),
    );
    expect(onResult).toHaveBeenCalled();
  });

  it("auto-derives a dropdown from a foreign key when the param has no explicit lookup", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    window.localStorage.setItem("aor.schemaId", "s1");
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    vi.mocked(getSchema).mockResolvedValue(SCHEMA);
    vi.mocked(execute).mockResolvedValue({
      columns: ["DEPARTMENT_ID", "DEPARTMENT_NAME"],
      rows: [[20, "Engineering"], [10, "Finance"]],
      elapsed_seconds: 0.01,
      row_count: 2,
      truncated: false,
    });
    const u = user();
    renderDialog(REPORT_AUTO);

    await u.click(screen.getByRole("button", { name: /^run$/i }));
    await screen.findByRole("dialog");

    // The lookup was derived from the FK (no explicit lookup_sql on the report).
    await waitFor(() =>
      expect(vi.mocked(execute)).toHaveBeenCalledWith({
        sql: "SELECT DEPARTMENT_ID, DEPARTMENT_NAME FROM DEPARTMENTS ORDER BY DEPARTMENT_NAME",
        profile_id: "p1",
      }),
    );
    expect(await screen.findByRole("option", { name: "Engineering" })).toBeInTheDocument();
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
