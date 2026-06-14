import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConnectionPicker } from "./ConnectionPicker";
import { SessionProvider } from "./session";
import type { ProfilePublic } from "@/lib/api/schemas";

// Mock the API module so the picker's query is fully controlled (no network).
vi.mock("@/lib/api/endpoints", () => ({ getProfiles: vi.fn() }));
import { getProfiles } from "@/lib/api/endpoints";

const PROFILES: ProfilePublic[] = [
  {
    id: "p1",
    name: "Production DB",
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
    service_name: "XEPDB1",
    current_schema: "AOR_DEMO",
    username: "aor_readonly",
    environment: "DEV",
  },
];

function renderPicker() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <ConnectionPicker />
      </SessionProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getProfiles).mockReset();
});
afterEach(cleanup);

describe("ConnectionPicker", () => {
  it("lists profiles and defaults to the first when none is remembered", async () => {
    vi.mocked(getProfiles).mockResolvedValue(PROFILES);
    const user = userEvent.setup();
    renderPicker();

    // Default selection (first profile) lands on the trigger once loaded.
    const trigger = await screen.findByRole("button", { name: /active connection/i });
    expect(trigger).toHaveTextContent("Production DB");
    expect(window.localStorage.getItem("aor.profileId")).toBe("p1");

    // Opening reveals every profile.
    await user.click(trigger);
    const listbox = screen.getByRole("listbox");
    expect(within(listbox).getByText("Production DB")).toBeInTheDocument();
    expect(within(listbox).getByText("XE (read-only)")).toBeInTheDocument();
  });

  it("selecting a profile updates context and persists it", async () => {
    vi.mocked(getProfiles).mockResolvedValue(PROFILES);
    const user = userEvent.setup();
    renderPicker();

    const trigger = await screen.findByRole("button", { name: /active connection/i });
    await user.click(trigger);
    await user.click(within(screen.getByRole("listbox")).getByText("XE (read-only)"));

    // Trigger now reflects the new selection and it is persisted.
    expect(trigger).toHaveTextContent("XE (read-only)");
    expect(trigger).toHaveTextContent("AOR_DEMO");
    expect(window.localStorage.getItem("aor.profileId")).toBe("p2");
    // Dropdown closed after choosing.
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("honours a remembered profile id over the first", async () => {
    window.localStorage.setItem("aor.profileId", "p2");
    vi.mocked(getProfiles).mockResolvedValue(PROFILES);
    renderPicker();

    const trigger = await screen.findByRole("button", { name: /active connection/i });
    expect(trigger).toHaveTextContent("XE (read-only)");
  });

  it("E10 — shows a calm zero-connection state when no profiles exist", async () => {
    vi.mocked(getProfiles).mockResolvedValue([]);
    renderPicker();

    const link = await screen.findByRole("link", { name: /add one in admin/i });
    expect(link).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /active connection/i })).not.toBeInTheDocument();
  });
});
