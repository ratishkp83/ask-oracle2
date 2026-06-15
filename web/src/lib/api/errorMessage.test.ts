import { describe, expect, it } from "vitest";
import { ApiError, errorMessage, friendlyError } from "./client";

// Locks the app-wide error-readability policy (feedback 2026-06-15): users never
// see raw/opaque text — only safe server messages, or a generic "contact IT
// support" line, always preserving the support reference id when present.
describe("friendlyError / errorMessage", () => {
  it("shows a safe server message verbatim with the reference id", () => {
    expect(errorMessage(new ApiError("Profile not found.", 404, "err_1"))).toBe("Profile not found. (ref err_1)");
  });

  it("passes the sanitized database message through (it is already user-facing)", () => {
    const dbMsg = "A database error occurred while running your request. Please try again, or contact IT support with this reference.";
    expect(errorMessage(new ApiError(dbMsg, 400, "err_2"))).toBe(`${dbMsg} (ref err_2)`);
  });

  it("replaces a bodyless HTTP failure with a generic support message + reference", () => {
    const out = friendlyError(new ApiError("Request failed (500).", 500, "err_3"));
    expect(out.message).toMatch(/contact it support/i);
    expect(out.message).not.toMatch(/request failed/i);
    expect(out.errorId).toBe("err_3");
  });

  it("treats a synthesized export failure as opaque too", () => {
    expect(friendlyError(new ApiError("Export failed (502).", 502, "err_4")).message).toMatch(/contact it support/i);
  });

  it("uses a friendly, ref-free message for a network failure (status 0)", () => {
    const out = friendlyError(new ApiError("Network error — the API is unreachable.", 0));
    expect(out.message).toMatch(/reach the service/i);
    expect(out.errorId).toBeUndefined();
  });

  it("falls back to a generic message for a non-ApiError throw", () => {
    expect(errorMessage(new Error("boom"))).toMatch(/contact it support/i);
    expect(errorMessage("nope")).toMatch(/contact it support/i);
  });
});
