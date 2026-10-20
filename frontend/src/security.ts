import type { Config } from './api';

export function connectionEnabled(config: Config, protocol: string): boolean {
  return protocol === 'https:' && (config.transport === 'capture' || config.live_enabled);
}
