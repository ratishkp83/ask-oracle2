import { defineConfig } from "vitest/config";
import path from "path";

// Frontend test runner (B7). Mirrors the Vite alias and runs from the space-free
// junction (process.cwd()), same as vite.config.ts.
const ROOT = process.cwd();

export default defineConfig({
  resolve: {
    alias: { "@": path.join(ROOT, "web", "src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [path.join(ROOT, "web", "src", "test", "setup.ts")],
    include: ["web/src/**/*.{test,spec}.{ts,tsx}"],
  },
});
