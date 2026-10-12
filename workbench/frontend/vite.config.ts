import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => ({
  plugins: [svelte()],
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8790", changeOrigin: false } },
  },
  resolve: mode === "test" ? { conditions: ["browser"] } : undefined,
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
  },
}));
