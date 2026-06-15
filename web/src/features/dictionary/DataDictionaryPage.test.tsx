import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { DataDictionaryPage } from "./DataDictionaryPage";
import { SessionProvider } from "@/app/session";
import { ApiError } from "@/lib/api/client";
import type { EbsPack, SchemaRecord, SchemaSummary } from "@/lib/api/schemas";

vi.mock("@/lib/api/endpoints", () => ({
  getSchemas: vi.fn(),
  getSchema: vi.fn(),
  deleteSchema: vi.fn(),
  getPacks: vi.fn(),
  getPack: vi.fn(),
  // Pulled in transitively via IntrospectDialog.
  getProfiles: vi.fn(),
  introspectSchema: vi.fn(),
}));
import { deleteSchema, getPack, getProfiles, getSchema, getSchemas, getPacks } from "@/lib/api/endpoints";

const user = () => userEvent.setup({ pointerEventsCheck: 0 });

const SCHEMAS: SchemaSummary[] = [
  { id: "s1", name: "AOR_DEMO", source: "introspection", profile_id: "p1", table_count: 2, created_at: "x", updated_at: "x" },
];

const RECORD: SchemaRecord = {
  id: "s1",
  name: "AOR_DEMO",
  source: "introspection",
  profile_id: "p1",
  table_count: 2,
  created_at: "x",
  updated_at: "x",
  definition: {
    tables: {
      CUSTOMERS: [
        { column_name: "ID", data_type: "NUMBER", is_primary_key: true, is_foreign_key: false },
        { column_name: "NAME", data_type: "VARCHAR2", is_primary_key: false, is_foreign_key: false },
      ],
      INVOICES: [
        { column_name: "ID", data_type: "NUMBER", is_primary_key: true, is_foreign_key: false },
        {
          column_name: "CUSTOMER_ID",
          data_type: "NUMBER",
          is_primary_key: false,
          is_foreign_key: true,
          references_table: "CUSTOMERS",
          references_column: "ID",
        },
      ],
    },
    relationships: [
      { from_table: "INVOICES", from_column: "CUSTOMER_ID", to_table: "CUSTOMERS", to_column: "ID", relationship_type: "many-to-one" },
    ],
  },
};

const GL_PACK: EbsPack = {
  module: "GL",
  name: "General Ledger",
  tables: [
    { table: "GL_LEDGERS", description: "Ledger (set of books) definitions.", key_columns: ["ledger_id", "name"], joins: [] },
  ],
  glossary: [{ term: "ledger", table: "GL_LEDGERS", column: null, note: "also 'set of books'" }],
};

const PACKS: EbsPack[] = [GL_PACK, { module: "AP", name: "Accounts Payable", tables: [], glossary: [] }];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <MemoryRouter>
          <DataDictionaryPage />
        </MemoryRouter>
      </SessionProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getSchemas).mockReset();
  vi.mocked(getSchema).mockReset();
  vi.mocked(deleteSchema).mockReset();
  vi.mocked(getPacks).mockReset();
  vi.mocked(getPack).mockReset();
  vi.mocked(getProfiles).mockResolvedValue([]);
});
afterEach(cleanup);

describe("DataDictionaryPage", () => {
  it("lists schemas + packs and defaults to the first schema's detail", async () => {
    vi.mocked(getSchemas).mockResolvedValue(SCHEMAS);
    vi.mocked(getPacks).mockResolvedValue(PACKS);
    vi.mocked(getSchema).mockResolvedValue(RECORD);
    renderPage();

    // Detail of the first schema loads, with both tables and FK reference.
    expect(await screen.findByRole("heading", { name: "AOR_DEMO" })).toBeInTheDocument();
    expect(screen.getByText("CUSTOMERS")).toBeInTheDocument();
    expect(screen.getByText("INVOICES")).toBeInTheDocument();
    expect(screen.getByText(/→ CUSTOMERS\.ID/)).toBeInTheDocument();
    expect(screen.getByLabelText("Foreign key")).toBeInTheDocument();
    // Two PK columns (CUSTOMERS.ID + INVOICES.ID) are both flagged.
    expect(screen.getAllByLabelText("Primary key").length).toBe(2);
    // Packs present in the rail.
    expect(screen.getByRole("button", { name: /General Ledger/i })).toBeInTheDocument();
  });

  it("shows an EBS pack's table notes and glossary when selected", async () => {
    vi.mocked(getSchemas).mockResolvedValue(SCHEMAS);
    vi.mocked(getPacks).mockResolvedValue(PACKS);
    vi.mocked(getSchema).mockResolvedValue(RECORD);
    vi.mocked(getPack).mockResolvedValue(GL_PACK);
    const u = user();
    renderPage();

    await screen.findByRole("heading", { name: "AOR_DEMO" });
    await u.click(screen.getByRole("button", { name: /General Ledger/i }));

    expect(await screen.findByRole("heading", { name: "General Ledger" })).toBeInTheDocument();
    // GL_LEDGERS appears as a table-note heading and again in the glossary row.
    expect(screen.getAllByText("GL_LEDGERS").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Ledger \(set of books\)/)).toBeInTheDocument();
    expect(screen.getByText("ledger")).toBeInTheDocument(); // glossary term
    expect(vi.mocked(getPack)).toHaveBeenCalledWith("GL");
  });

  it("defaults to the first pack when there are no saved schemas", async () => {
    vi.mocked(getSchemas).mockResolvedValue([]);
    vi.mocked(getPacks).mockResolvedValue(PACKS);
    vi.mocked(getPack).mockResolvedValue(GL_PACK);
    renderPage();

    expect(await screen.findByText(/none yet/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "General Ledger" })).toBeInTheDocument();
  });

  it("deletes a saved schema after confirmation", async () => {
    vi.mocked(getSchemas).mockResolvedValue(SCHEMAS);
    vi.mocked(getPacks).mockResolvedValue(PACKS);
    vi.mocked(getSchema).mockResolvedValue(RECORD);
    vi.mocked(deleteSchema).mockResolvedValue(undefined);
    const u = user();
    renderPage();

    await screen.findByRole("heading", { name: "AOR_DEMO" });
    await u.click(screen.getByRole("button", { name: /delete aor_demo/i }));
    const dialog = await screen.findByRole("dialog");
    await u.click(within(dialog).getByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(vi.mocked(deleteSchema)).toHaveBeenCalledWith("s1"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("surfaces a sanitized error when schema detail fails to load", async () => {
    vi.mocked(getSchemas).mockResolvedValue(SCHEMAS);
    vi.mocked(getPacks).mockResolvedValue(PACKS);
    vi.mocked(getSchema).mockRejectedValue(new ApiError("Schema not found.", 404, "err_5"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(/schema not found.*ref err_5/i);
  });
});
