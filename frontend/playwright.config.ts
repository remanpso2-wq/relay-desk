import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8010", trace: "retain-on-failure" },
  webServer: {
    command: "python ../backend/tests/e2e_server.py",
    url: "http://127.0.0.1:8010/api/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
