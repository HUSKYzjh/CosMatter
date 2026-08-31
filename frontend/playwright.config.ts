import { defineConfig } from "@playwright/test";

const edgeExecutable = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

export default defineConfig({
  testDir: "./e2e",
  // The first Vite transform on a cold Windows worktree can exceed 30s; the
  // assertions themselves still retain Playwright's normal short waits.
  timeout: 60_000,
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:5179",
    browserName: "chromium",
    headless: true,
    viewport: { width: 390, height: 844 },
    launchOptions: { executablePath: process.env.COSMATTER_BROWSER_EXECUTABLE ?? edgeExecutable },
  },
  webServer: {
    command: "npm.cmd run dev -- --host 127.0.0.1 --port 5179 --strictPort",
    url: "http://127.0.0.1:5179",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
