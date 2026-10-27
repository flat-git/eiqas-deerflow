import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "eiqas-offline.spec.ts",
  use: { browserName: "chromium", headless: true, offline: true },
  reporter: "list",
  outputDir: ".next/eiqas-offline-tests",
});
