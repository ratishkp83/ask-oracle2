import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SchemaPicker } from "./SchemaPicker";
import { SessionProvider } from "@/app/session";
import type { SchemaSummary } from "@/lib/api/schemas";

vi.mock("@/lib/api/endpoints", () => ({ getSchemas: vi.fn() }));
import { getSchemas } from "@/lib/api/endpoints";

const mk = (id: string, name: string, table_count: number): SchemaSummary => ({
  id,
  name,
  source: "upload",
  profile_id: null,
  table_count,
  created_at: "2026-06-14T00:00:00Z",
  updated_at: "2026-06-14T00:00:00Z",
});

function renderPicker() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <SchemaPicker />
      </SessionProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getSchemas).mockReset();
});
afterEach(cleanup);

describe("SchemaPicker", () => {
  it("lists schemas, shows E11 until one is chosen, then persists the choice", async () => {
    vi.mocked(getSchemas).mockResolvedValue([mk("s1", "AOR_DEMO", 12), mk("s2", "GL_PACK", 30)]);
    const user = userEvent.setup();
    renderPicker();

    // Two schemas, nothing remembered → no auto-default; E11 notice present.
    const trigger = await screen.findByRole("button", { name: /active schema/i });
    expect(trigger).toHaveTextContent("Select…");
    expect(screen.getByRole("note")).toHaveTextContent(/accuracy may be lower/i);

    // Choose one → persisted and the E11 notice clears.
    await user.click(trigger);
    await user.click(within(screen.getByRole("listbox")).getByText("GL_PACK"));
    expect(trigger).toHaveTextContent("GL_PACK");
    expect(window.localStorage.getItem("aor.schemaId")).toBe("s2");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("defaults to the sole schema when exactly one exists", async () => {
    vi.mocked(getSchemas).mockResolvedValue([mk("only", "AOR_DEMO", 12)]);
    renderPicker();

    const trigger = await screen.findByRole("button", { name: /active schema/i });
    expect(trigger).toHaveTextContent("AOR_DEMO");
    expect(window.localStorage.getItem("aor.schemaId")).toBe("only");
    // Auto-selected → no E11 notice.
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("honours a remembered schema id over the sole-schema default boundary", async () => {
    window.localStorage.setItem("aor.schemaId", "s2");
    vi.mocked(getSchemas).mockResolvedValue([mk("s1", "AOR_DEMO", 12), mk("s2", "GL_PACK", 30)]);
    renderPicker();

    const trigger = await screen.findByRole("button", { name: /active schema/i });
    expect(trigger).toHaveTextContent("GL_PACK");
  });

  it("E11 — shows the no-schema notice (no picker) when none exist", async () => {
    vi.mocked(getSchemas).mockResolvedValue([]);
    renderPicker();

    expect(await screen.findByRole("note")).toHaveTextContent(/no schema selected/i);
    expect(screen.getByRole("link", { name: /add one in admin/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /active schema/i })).not.toBeInTheDocument();
  });
});
