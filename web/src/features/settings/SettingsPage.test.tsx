import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsPage } from "./SettingsPage";
import { AskPage } from "@/features/ask/AskPage";
import { SessionProvider } from "@/app/session";

vi.mock("@/lib/api/endpoints", () => ({
  nl2sql: vi.fn(),
  execute: vi.fn(),
  getSchemas: vi.fn(),
  getProfiles: vi.fn(),
}));
import { getProfiles, getSchemas, nl2sql } from "@/lib/api/endpoints";

function renderSettings() {
  return render(
    <SessionProvider>
      <SettingsPage />
    </SessionProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(getSchemas).mockResolvedValue([]);
  vi.mocked(getProfiles).mockResolvedValue([]);
  vi.mocked(nl2sql).mockReset();
});
afterEach(cleanup);

describe("SettingsPage", () => {
  it("defaults to the server model with Reset disabled", () => {
    renderSettings();
    expect(screen.getByRole("status")).toHaveTextContent(/using the server.*configured model/i);
    expect(screen.getByRole("button", { name: /reset to server default/i })).toBeDisabled();
  });

  it("setting a model marks the session as overriding, and Reset clears it", async () => {
    const user = userEvent.setup();
    renderSettings();

    await user.type(screen.getByLabelText("Model"), "gpt-4o");
    expect(screen.getByRole("status")).toHaveTextContent(/overriding this session/i);
    expect(screen.getByRole("status")).toHaveTextContent("gpt-4o");
    const reset = screen.getByRole("button", { name: /reset to server default/i });
    expect(reset).toBeEnabled();

    await user.click(reset);
    expect(screen.getByRole("status")).toHaveTextContent(/using the server.*configured model/i);
    expect(screen.getByLabelText("Model")).toHaveValue("");
  });

  it("the override flows into the Ask flow's /nl2sql call", async () => {
    vi.mocked(nl2sql).mockResolvedValue({ sql: "SELECT 1 FROM dual", explanation: null, confidence: null });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={qc}>
        <SessionProvider>
          <SettingsPage />
          <AskPage />
        </SessionProvider>
      </QueryClientProvider>,
    );

    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    await user.type(screen.getByLabelText("Model"), "gpt-4o");

    await user.type(screen.getByPlaceholderText(/Top 10 customers/i), "Revenue by region");
    await user.click(screen.getByRole("button", { name: /generate sql/i }));

    await waitFor(() =>
      expect(vi.mocked(nl2sql)).toHaveBeenCalledWith(
        expect.objectContaining({ natural_language: "Revenue by region", llm: { provider: "openai", model: "gpt-4o" } }),
      ),
    );
  });
});
