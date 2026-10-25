import { defineConfig } from 'vitest/config';
export default defineConfig({
  test: {
    include: ['shared/**/*.test.ts', 'worker/**/*.test.ts', 'src/**/*.test.tsx'],
    alias: { 'cloudflare:sockets': new URL('./tests/socket-stub.ts', import.meta.url).pathname },
    environmentOptions: { jsdom: { url: 'https://app.test/', pretendToBeVisual: true } }
  }
});
