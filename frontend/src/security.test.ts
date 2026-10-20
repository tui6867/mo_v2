import { expect, it } from 'vitest';
import { connectionEnabled } from './security';
import type { Config } from './api';

const gmail = { transport: 'gmail', live_enabled: true } as Config;
it('requires HTTPS even when live sending is enabled', () => {
  expect(connectionEnabled(gmail, 'http:')).toBe(false);
  expect(connectionEnabled(gmail, 'https:')).toBe(true);
});
it('requires the operator live gate and never enables HTTP capture connections', () => {
  expect(connectionEnabled({ ...gmail, live_enabled: false }, 'https:')).toBe(false);
  expect(connectionEnabled({ ...gmail, transport: 'capture' }, 'https:')).toBe(true);
  expect(connectionEnabled({ ...gmail, transport: 'capture' }, 'http:')).toBe(false);
});
