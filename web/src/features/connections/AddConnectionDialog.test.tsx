import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddConnectionDialog } from "./AddConnectionDialog";
import { ApiError } from "@/lib/api/client";

// Mock the endpoints module so create/test are fully controlled (no network).
vi.mock("@/lib/api/endpoints", () => ({
  createProfile: vi.fn(),
  testConnection: vi.fn(),
}));
import { createProfile, testConnection } from "@/lib/api/endpoints";

// Radix Dialog disables body pointer-events while open; turn off userEvent's
// pointer-events guard so clicks inside the portal register in jsdom.
const user = () => userEvent.setup({ pointerEventsCheck: 0 });

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AddConnectionDialog />
    </QueryClientProvider>,
  );
}

// Open the dialog and fill the minimum required fields (service-name path).
async function openAndFill(u: ReturnType<typeof user>) {
  await u.click(screen.getByRole("button", { name: /add connection/i }));
  await screen.findByRole("dialog");
  await u.type(screen.getByLabelText("Name"), "Reporting DB");
  await u.type(screen.getByLabelText("Host"), "db.example.com");
  await u.type(screen.getByLabelText("Service name"), "ORCLPDB1");
  await u.type(screen.getByLabelText("Username"), "aor_ro");
  await u.type(screen.getByLabelText("Password"), "s3cret");
}

beforeEach(() => {
  vi.mocked(createProfile).mockReset();
  vi.mocked(testConnection).mockReset();
});
afterEach(cleanup);

describe("AddConnectionDialog", () => {
  it("keeps Save disabled until required fields are filled", async () => {
    const u = user();
    renderDialog();
    await u.click(screen.getByRole("button", { name: /add connection/i }));
    await screen.findByRole("dialog");

    const save = screen.getByRole("button", { name: /save connection/i });
    expect(save).toBeDisabled();

    await u.type(screen.getByLabelText("Name"), "Reporting DB");
    await u.type(screen.getByLabelText("Host"), "db.example.com");
    await u.type(screen.getByLabelText("Service name"), "ORCLPDB1");
    await u.type(screen.getByLabelText("Username"), "aor_ro");
    expect(save).toBeDisabled(); // still missing the password
    await u.type(screen.getByLabelText("Password"), "s3cret");
    expect(save).toBeEnabled();
  });

  it("tests an unsaved connection and shows the elapsed time", async () => {
    vi.mocked(testConnection).mockResolvedValue({ ok: true, elapsed_seconds: 0.04 });
    const u = user();
    renderDialog();
    await openAndFill(u);

    await u.click(screen.getByRole("button", { name: /test connection/i }));

    await waitFor(() =>
      expect(vi.mocked(testConnection)).toHaveBeenCalledWith(
        expect.objectContaining({
          host: "db.example.com",
          port: 1521,
          service_name: "ORCLPDB1",
          sid: null,
          username: "aor_ro",
          password: "s3cret",
        }),
      ),
    );
    expect(await screen.findByText(/connected in 0\.04s/i)).toBeInTheDocument();
  });

  it("saves the profile (with default schema + environment) and closes the dialog", async () => {
    vi.mocked(createProfile).mockResolvedValue({
      id: "p1",
      name: "Reporting DB",
      host: "db.example.com",
      port: 1521,
      service_name: "ORCLPDB1",
      current_schema: "AOR_DEMO",
      username: "aor_ro",
      environment: "PROD",
    });
    const u = user();
    renderDialog();
    await openAndFill(u);
    await u.type(screen.getByLabelText(/default schema/i), "AOR_DEMO");
    await u.click(screen.getByRole("button", { name: "PROD" }));

    await u.click(screen.getByRole("button", { name: /save connection/i }));

    await waitFor(() =>
      expect(vi.mocked(createProfile)).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Reporting DB",
          host: "db.example.com",
          service_name: "ORCLPDB1",
          sid: null,
          current_schema: "AOR_DEMO",
          username: "aor_ro",
          password: "s3cret",
          environment: "PROD",
        }),
      ),
    );
    // Dialog closes on success.
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("toggling to SID swaps the connect field", async () => {
    const u = user();
    renderDialog();
    await u.click(screen.getByRole("button", { name: /add connection/i }));
    await screen.findByRole("dialog");

    expect(screen.getByLabelText("Service name")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "SID" }));
    expect(screen.getByLabelText("SID")).toBeInTheDocument();
    expect(screen.queryByLabelText("Service name")).not.toBeInTheDocument();
  });

  it("shows a sanitized error with a reference id when save fails", async () => {
    vi.mocked(createProfile).mockRejectedValue(new ApiError("A profile named 'Reporting DB' already exists.", 409, "err_42"));
    const u = user();
    renderDialog();
    await openAndFill(u);

    await u.click(screen.getByRole("button", { name: /save connection/i }));

    expect(await screen.findByText(/already exists.*ref err_42/i)).toBeInTheDocument();
    // Dialog stays open so the user can fix the name.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
