import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { IntrospectDialog } from "./IntrospectDialog";
import { SessionProvider } from "@/app/session";
import { ApiError } from "@/lib/api/client";
import type { ProfilePublic } from "@/lib/api/schemas";

vi.mock("@/lib/api/endpoints", () => ({
  getProfiles: vi.fn(),
  introspectSchema: vi.fn(),
}));
import { getProfiles, introspectSchema } from "@/lib/api/endpoints";

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

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <MemoryRouter>
          <IntrospectDialog />
        </MemoryRouter>
      </SessionProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getProfiles).mockReset();
  vi.mocked(introspectSchema).mockReset();
});
afterEach(cleanup);

describe("IntrospectDialog", () => {
  it("blocks introspection and guides to Connections when none is active", async () => {
    vi.mocked(getProfiles).mockResolvedValue([]);
    const u = user();
    renderDialog();

    await u.click(screen.getByRole("button", { name: /introspect schema/i }));
    await screen.findByRole("dialog");

    expect(screen.getByText(/no active connection/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /add or select one/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /introspect & save/i })).toBeDisabled();
  });

  it("introspects + saves the schema via the active connection and shows the count", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    vi.mocked(introspectSchema).mockResolvedValue({
      table_count: 12,
      warnings: [],
      truncated: false,
      saved: { id: "s9", name: "AOR_DEMO", source: "introspection", profile_id: "p1", table_count: 12, created_at: "x", updated_at: "x" },
    });
    const u = user();
    renderDialog();

    await u.click(screen.getByRole("button", { name: /introspect schema/i }));
    await screen.findByRole("dialog");

    const owner = screen.getByLabelText(/schema \/ owner/i);
    await u.clear(owner);
    await u.type(owner, "AOR_DEMO");
    await u.click(screen.getByRole("button", { name: /introspect & save/i }));

    await waitFor(() =>
      expect(vi.mocked(introspectSchema)).toHaveBeenCalledWith(
        expect.objectContaining({ profile_id: "p1", owner: "AOR_DEMO", save: true, table_like: "%", name: null }),
      ),
    );
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
    expect(screen.getByText(/12 tables/i)).toBeInTheDocument();
  });

  it("shows a sanitized error with a reference id when introspection fails", async () => {
    window.localStorage.setItem("aor.profileId", "p1");
    vi.mocked(getProfiles).mockResolvedValue([PROFILE]);
    vi.mocked(introspectSchema).mockRejectedValue(new ApiError("Could not reach the database.", 502, "err_88"));
    const u = user();
    renderDialog();

    await u.click(screen.getByRole("button", { name: /introspect schema/i }));
    await screen.findByRole("dialog");
    const owner = screen.getByLabelText(/schema \/ owner/i);
    await u.clear(owner);
    await u.type(owner, "AOR_DEMO");
    await u.click(screen.getByRole("button", { name: /introspect & save/i }));

    expect(await screen.findByText(/could not reach.*ref err_88/i)).toBeInTheDocument();
  });
});
