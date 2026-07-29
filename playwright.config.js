// E2E da UI com a ponte pywebview mockada (ver tests-e2e/).
// expect.timeout 10s: padrão da família (CI Windows flake com 5s).
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests-e2e",
  expect: { timeout: 10000 },
  use: { headless: true },
  reporter: [["list"]],
});
