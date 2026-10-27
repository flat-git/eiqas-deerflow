import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: ["eiqas-scroll.spec.ts", "eiqas-human-input-layout.spec.ts"],
  use: { browserName: "chromium", headless: true },
  reporter: "list",
  outputDir: ".next/eiqas-layout-tests",
});
