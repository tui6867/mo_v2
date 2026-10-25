import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './launch/e2e',
  testMatch: '**/*.pw.ts',
  outputDir: './launch-artifacts',
  fullyParallel: true,
  workers: 2,
  reporter: 'list',
  timeout: 45000,
  use: {
    baseURL: 'http://127.0.0.1:5174',
    channel: process.platform === 'win32' ? 'msedge' : 'chromium',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev:launch',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: !process.env.CI,
  },
});
