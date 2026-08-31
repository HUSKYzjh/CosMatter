import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";
import solid from "vite-plugin-solid";

export default defineConfig({
  base: "./",
  plugins: [solid()],
  test: {
    environment: "node",
    // Playwright owns browser scenarios under e2e/; Vitest must not import
    // those files as unit suites.
    exclude: [...configDefaults.exclude, "e2e/**"],
  }
});
