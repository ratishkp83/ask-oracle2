import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// Frontend test runner (B7). Mirrors the Vite alias and runs from the space-free
// junction (process.cwd()), same as vite.config.ts. The React plugin gives .tsx
// component tests the same JSX transform as the app.
const ROOT = process.cwd();

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.join(ROOT, "web", "src") },
    // Mirror vite.config: keep Vite on the space-free junction so the dev
    // dep-optimizer doesn't canonicalize to the %20 spaced path (P9B-R1-F1).
    preserveSymlinks: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [path.join(ROOT, "web", "src", "test", "setup.ts")],
    include: ["web/src/**/*.{test,spec}.{ts,tsx}"],
  },
});
