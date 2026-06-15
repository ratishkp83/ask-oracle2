import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConnectionsPage } from "./ConnectionsPage";
import { ApiError } from "@/lib/api/client";
import type { ProfilePublic } from "@/lib/api/schemas";

vi.mock("@/lib/api/endpoints", () => ({
  getProfiles: vi.fn(),
  testProfile: vi.fn(),
  deleteProfile: vi.fn(),
  // Pulled in transitively via AddConnectionDialog.
  createProfile: vi.fn(),
  testConnection: vi.fn(),
}));
import { deleteProfile, getProfiles, testProfile } from "@/lib/api/endpoints";

// Radix Dialog disables body pointer-events while open.
const user = () => userEvent.setup({ pointerEventsCheck: 0 });

const PROFILES: ProfilePublic[] = [
  {
    id: "p1",
    name: "Production GL",
    host: "prod.example.com",
    port: 1521,
    service_name: "ORCL",
    current_schema: "GL",
    username: "aor_ro",
    environment: "PROD",
  },
  {
    id: "p2",
    name: "XE (read-only)",
    host: "127.0.0.1",
    port: 1521,
    sid: "XE",
    current_schema: "AOR_DEMO",
    username: "aor_readonly",
    environment: "DEV",
  },
];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ConnectionsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getProfiles).mockReset();
  vi.mocked(testProfile).mockReset();
  vi.mocked(deleteProfile).mockReset();
});
afterEach(cleanup);

describe("ConnectionsPage", () => {
  it("lists saved connections with account, connect-by, and schema", async () => {
    vi.mocked(getProfiles).mockResolvedValue(PROFILES);
    renderPage();

    expect(await screen.findByText("Production GL")).toBeInTheDocument();
    expect(screen.getByText(/aor_ro@prod\.example\.com:1521/)).toBeInTheDocument();
    expect(screen.getByText(/Service · ORCL/)).toBeInTheDocument();
    expect(screen.getByText(/SID · XE/)).toBeInTheDocument();
    expect(screen.getByText(/Schema AOR_DEMO/)).toBeInTheDocument();
  });

  it("E10 — shows a calm empty state with an add affordance", async () => {
    vi.mocked(getProfiles).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/no connections yet/i)).toBeInTheDocument();
    // Both the header and the empty card offer the same add affordance.
    expect(screen.getAllByRole("button", { name: /add connection/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("surfaces a friendly message when the list can't be reached (network)", async () => {
    vi.mocked(getProfiles).mockRejectedValue(new ApiError("Network error — the API is unreachable.", 0));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(/reach the service.*contact it support/i);
  });

  it("surfaces a sanitized server message with a reference id when the list load errors", async () => {
    vi.mocked(getProfiles).mockRejectedValue(new ApiError("Service temporarily unavailable.", 503, "err_7"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily unavailable.*ref err_7/i);
  });

  it("tests a saved connection and shows the elapsed time", async () => {
    vi.mocked(getProfiles).mockResolvedValue(PROFILES);
    vi.mocked(testProfile).mockResolvedValue({ ok: true, elapsed_seconds: 0.03 });
    const u = user();
    renderPage();

    const row = (await screen.findByText("Production GL")).closest("li")!;
    await u.click(within(row).getByRole("button", { name: /^test$/i }));

    await waitFor(() => expect(vi.mocked(testProfile)).toHaveBeenCalledWith("p1"));
    expect(await within(row).findByText(/connected in 0\.03s/i)).toBeInTheDocument();
  });

  it("shows a sanitized error with a reference id when a test fails", async () => {
    vi.mocked(getProfiles).mockResolvedValue(PROFILES);
    vi.mocked(testProfile).mockRejectedValue(new ApiError("Could not connect to the database.", 502, "err_99"));
    const u = user();
    renderPage();

    const row = (await screen.findByText("Production GL")).closest("li")!;
    await u.click(within(row).getByRole("button", { name: /^test$/i }));

    expect(await within(row).findByText(/could not connect.*ref err_99/i)).toBeInTheDocument();
  });

  it("deletes a connection after confirmation", async () => {
    vi.mocked(getProfiles).mockResolvedValue(PROFILES);
    vi.mocked(deleteProfile).mockResolvedValue(undefined);
    const u = user();
    renderPage();

    const row = (await screen.findByText("XE (read-only)")).closest("li")!;
    await u.click(within(row).getByRole("button", { name: /delete xe \(read-only\)/i }));

    // Confirm dialog → confirm.
    const dialog = await screen.findByRole("dialog");
    await u.click(within(dialog).getByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(vi.mocked(deleteProfile)).toHaveBeenCalledWith("p2"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
