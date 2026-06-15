import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "./ConfirmDialog";
import { ApiError } from "@/lib/api/client";

const user = () => userEvent.setup({ pointerEventsCheck: 0 });

function renderCD(onConfirm: () => Promise<unknown>) {
  const onConfirmed = vi.fn();
  render(
    <ConfirmDialog
      triggerAriaLabel="Delete Widget"
      triggerClassName="trigger"
      triggerChildren={<span>del</span>}
      title="Delete widget"
      description="Remove it?"
      onConfirm={onConfirm}
      onConfirmed={onConfirmed}
    />,
  );
  return { onConfirmed };
}

afterEach(cleanup);

describe("ConfirmDialog", () => {
  it("runs the action, fires onConfirmed, and closes on success", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const u = user();
    const { onConfirmed } = renderCD(onConfirm);

    await u.click(screen.getByRole("button", { name: "Delete Widget" }));
    await screen.findByRole("dialog");
    await u.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalled());
    await waitFor(() => expect(onConfirmed).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows a sanitized error and stays open when the action fails", async () => {
    const onConfirm = vi.fn().mockRejectedValue(new ApiError("The database is busy.", 503, "err_z"));
    const u = user();
    const { onConfirmed } = renderCD(onConfirm);

    await u.click(screen.getByRole("button", { name: "Delete Widget" }));
    await screen.findByRole("dialog");
    await u.click(screen.getByRole("button", { name: /^delete$/i }));

    expect(await screen.findByText(/the database is busy.*ref err_z/i)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onConfirmed).not.toHaveBeenCalled();
  });

  it("cancels without running the action", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const u = user();
    renderCD(onConfirm);

    await u.click(screen.getByRole("button", { name: "Delete Widget" }));
    await screen.findByRole("dialog");
    await u.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
