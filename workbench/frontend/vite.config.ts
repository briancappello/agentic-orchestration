import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vitest/config";

// Vite runs this file in Node; the frontend's types do not include Node's.
declare const process: { env: Record<string, string | undefined> };

export default defineConfig(({ mode }) => ({
  plugins: [svelte()],
  server: {
    // scripts/dev.sh sets WORKBENCH_BACKEND when the backend runs on another port.
    proxy: { "/api": { target: process.env.WORKBENCH_BACKEND ?? "http://127.0.0.1:8790", changeOrigin: false } },
  },
  resolve: mode === "test" ? { conditions: ["browser"] } : undefined,
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
  },
}));
