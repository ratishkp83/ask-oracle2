import { Outlet } from "react-router-dom";
import { LeftRail } from "./LeftRail";
import { TopBar } from "./TopBar";

// Single-viewport shell (B-3): the frame never scrolls; only an inner results
// region may. h-screen + overflow-hidden enforce it.
export function AppShell() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-canvas text-ink">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <LeftRail />
        <main className="min-w-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
