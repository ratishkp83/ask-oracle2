import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// Phase 9 — the React CXO executive surface. The app lives under web/; the repo
// root stays the npm/Vite project so the already-installed node_modules is reused.
//
// IMPORTANT (space-in-path): the real repo dir is "ask-oracle-reports-main v2"
// (note the space). Vite's dep optimizer crashes on the %20-encoded path. We run
// via the space-free junction (D:\...\aor-v2) and keep Vite on that path by
// (a) deriving roots from process.cwd() — NOT __dirname, which realpaths back to
// the spaced dir — and (b) preserveSymlinks so module resolution never realpaths
// node_modules to the spaced target.
const ROOT = process.cwd();
const API_TARGET = process.env.AOR_API_TARGET || "http://127.0.0.1:8000";
const proxy = { "/v1": { target: API_TARGET, changeOrigin: true } };

export default defineConfig({
  root: path.join(ROOT, "web"),
  resolve: {
    alias: { "@": path.join(ROOT, "web", "src") },
    preserveSymlinks: true,
  },
  plugins: [react()],
  server: { port: 5174, proxy },
  preview: { port: 5174, proxy },
  build: {
    outDir: path.join(ROOT, "dist"),
    emptyOutDir: true,
  },
});
