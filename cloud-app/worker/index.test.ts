import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { connect } from 'cloudflare:sockets';
import worker, { MailSession } from './index';
import { sign } from './crypto';
import type { Env } from './store';
import type { Access, Batch, Message } from '../shared/model';
vi.mock('cloudflare:sockets', () => ({ connect: vi.fn() }));
const SECRET = 'synthetic-cloud-key-' + 's'.repeat(64);
const owner = '00000000-0000-4000-8000-000000000001'; const session = '00000000-0000-4000-8000-000000000002';
const identity = { id: owner, email: 'sender@gmail.com', session, token: 'synthetic' };
const token = 'header.' + btoa(JSON.stringify({ session_id: session })).replace(/=/g, '') + '.signature';
const message: Message = { name: 'Ana', email: 'ana@example.com', subject: 'Approved subject', body: 'Approved content.' };
const access: Access = { id: owner, email: identity.email, approved: true, is_admin: true, full_name: 'Sender', purpose: 'Tests', request_status: 'approved', daily_limit: 10, remaining: 10, live_enabled: true, debug_enabled: true, batch_limit: 5, global_daily_limit: 50 };
let env: Env; let me: Access; let events: string[]; let stored: Batch; let failFinish: boolean; let authDelay: Promise<void> | undefined;
function fakeSocket() {
  let controller: ReadableStreamDefaultController<Uint8Array>; let sending = false;
  const reply = (value: string) => controller.enqueue(new TextEncoder().encode(value));
  return {
    opened: Promise.resolve({}), closed: Promise.resolve(), close: async () => { try { controller.close(); } catch { /* Closed */ } },
    readable: new ReadableStream<Uint8Array>({ start(value) { controller = value; reply('220 Gmail\r\n'); } }),
    writable: new WritableStream<Uint8Array>({ async write(bytes) {
      const value = new TextDecoder().decode(bytes); events.push('smtp:' + (value.startsWith('AUTH') ? 'AUTH' : value.split('\r\n')[0]));
      if (sending) reply('250 accepted\r\n');
      else if (value.startsWith('EHLO')) reply('250-Gmail\r\n250 AUTH PLAIN\r\n');
      else if (value.startsWith('AUTH')) { if (authDelay) await authDelay; reply('235 authenticated\r\n'); }
      else if (value.startsWith('DATA')) { sending = true; reply('354 continue\r\n'); }
      else reply('250 ok\r\n');
    } })
  };
}
function objectRequest(path: string, payload: unknown = {}, method = 'POST', who = identity) {
  return new Request('https://session.internal/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ identity: who, payload, method }) });
}
function object() { return new MailSession({ storage: { setAlarm: vi.fn(async () => {}) } } as unknown as DurableObjectState, env); }
beforeEach(() => {
  events = []; me = { ...access }; failFinish = false; authDelay = undefined;
  stored = { id: '00000000-0000-4000-8000-000000000003', status: 'active', created_at: new Date().toISOString(), messages: [message], attempts: [{ ...message, ordinal: 0, state: 'pending', detail: '', message_id: null, updated_at: new Date().toISOString() }] };
  env = { APP_ORIGIN: 'https://app.test', SUPABASE_URL: 'https://gnmimpoeqxeczjhvzrrx.supabase.co', SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_synthetic', CLOUD_MAIL_SIGNING_SECRET: SECRET, LIVE_SENDS_ALLOWED: 'true', ASSETS: { fetch: vi.fn(async () => new Response('<html>Application</html>')) } } as unknown as Env;
  vi.mocked(connect).mockImplementation(fakeSocket as never);
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/auth/v1/user')) return Response.json({ id: owner, email: identity.email, email_confirmed_at: '2026-01-01' });
    const { command, signature } = JSON.parse(String(init?.body));
    expect(signature).toBe(await sign(SECRET, command)); const cmd = JSON.parse(command); events.push('db:' + cmd.operation);
    if (cmd.operation === 'me') return Response.json(me);
    if (cmd.operation === 'connect_attempt') return Response.json(true);
    if (cmd.operation === 'get') return Response.json(stored);
    if (cmd.operation === 'claim') { stored.attempts[0].state = 'submitting'; return Response.json({ ordinal: 0, claim_token: session, sender: identity.email, message }); }
    if (cmd.operation === 'finish') {
      if (failFinish) return Response.json({ message: 'Unknown database internal failure with private diagnostic' }, { status: 500 });
      stored.attempts[0].state = cmd.payload.state; stored.status = 'completed'; return Response.json(stored);
    }
    return Response.json(true);
  }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); vi.useRealTimers(); });
describe('Worker security boundaries and session-only credentials', () => {
  it('serves health safely and blocks wrong origins before touching credentials or Auth', async () => {
    const response = await worker.fetch(new Request('https://app.test/api/health'), env);
    expect(response.headers.get('Content-Security-Policy')).toContain("frame-ancestors 'none'");
    expect(await response.json()).not.toHaveProperty('secret');
    const blocked = await worker.fetch(new Request('https://app.test/api/connection', { method: 'POST', headers: { Origin: 'https://evil.test', 'Content-Type': 'application/json' }, body: JSON.stringify({ app_password: 'syntheticpassword' }) }), env);
    expect(blocked.status).toBe(403); expect(fetch).not.toHaveBeenCalled(); expect(connect).not.toHaveBeenCalled();
    expect((await worker.fetch(new Request('https://app.test/api/me'), env)).status).toBe(401);
  });
  it('does not expose the backend key in public config and fails closed on a wrong project', async () => {
    const response = await worker.fetch(new Request('https://app.test/api/config'), env); expect(await response.text()).not.toContain(SECRET);
    env.SUPABASE_URL = 'https://other.supabase.co'; expect((await worker.fetch(new Request('https://app.test/api/config'), env)).status).toBe(503);
  });
  it('bounds streamed request bodies and rejects non-JSON writes', async () => {
    const make = (contentType: string, body: string) => new Request('https://app.test/api/request-access', { method: 'POST', headers: { Origin: env.APP_ORIGIN, Authorization: 'Bearer ' + token, 'Content-Type': contentType }, body });
    expect((await worker.fetch(make('application/json', JSON.stringify({ text: 'x'.repeat(120001) })), env)).status).toBe(413);
    expect((await worker.fetch(make('text/plain', '{}'), env)).status).toBe(415);
  });
  it('requires current approval and both live gates for connecting', async () => {
    const sessionObject = object(); me.approved = false;
    expect((await sessionObject.fetch(objectRequest('/connection', { app_password: 'abcdefghijklmnop' }))).status).toBe(403);
    me.approved = true; me.live_enabled = false;
    expect((await sessionObject.fetch(objectRequest('/connection', { app_password: 'abcdefghijklmnop' }))).status).toBe(403);
    me.live_enabled = true; env.LIVE_SENDS_ALLOWED = 'false';
    expect((await sessionObject.fetch(objectRequest('/connection', { app_password: 'abcdefghijklmnop' }))).status).toBe(403);
    expect(connect).not.toHaveBeenCalled();
  });
  it('authentication sends no mail; another Auth session cannot reuse or delete the credential', async () => {
    const sessionObject = object(); const response = await sessionObject.fetch(objectRequest('/connection', { app_password: 'abcd efgh ijkl mnop' }));
    expect(response.status).toBe(200); expect(events.some(value => value.startsWith('smtp:MAIL'))).toBe(false);
    const wrongSession = { ...identity, session: '00000000-0000-4000-8000-000000000099' };
    const view = await sessionObject.fetch(objectRequest('/me', {}, 'GET', wrongSession)); expect(await view.json()).toHaveProperty('connection', null);
    await sessionObject.fetch(objectRequest('/connection', {}, 'DELETE', wrongSession));
    expect(await (await sessionObject.fetch(objectRequest('/me', {}, 'GET'))).json()).not.toHaveProperty('connection', null);
    // Re-instantiation has no saved password to restore, even with the same object ID/storage.
    expect(await (await object().fetch(objectRequest('/me', {}, 'GET'))).json()).toHaveProperty('connection', null);
    expect(connect).toHaveBeenCalledWith({ hostname: 'smtp.gmail.com', port: 465 }, { secureTransport: 'on', allowHalfOpen: false });
  });
  it('binds previews to content, connection and session, and expires credentials', async () => {
    const sessionObject = object(); await sessionObject.fetch(objectRequest('/connection', { app_password: 'abcdefghijklmnop' }));
    const preview = await (await sessionObject.fetch(objectRequest('/preview', { messages: [message] }))).json() as object;
    const changed = await sessionObject.fetch(objectRequest('/batches', { ...preview, messages: [{ ...message, body: 'Changed after approval' }], confirmed: true, policy_ack: true }));
    expect(changed.status).toBe(400); expect(events).not.toContain('db:start');
    vi.useFakeTimers(); vi.setSystemTime(Date.now() + 1800001);
    expect(await (await sessionObject.fetch(objectRequest('/me', {}, 'GET'))).json()).toHaveProperty('connection', null);
  });
  it('disconnect during authentication cannot restore a cancelled credential later', async () => {
    let release!: () => void;
    authDelay = new Promise(resolve => { release = resolve; });
    const sessionObject = object();
    const connecting = sessionObject.fetch(objectRequest('/connection', { app_password: 'abcdefghijklmnop' }));
    await vi.waitFor(() => expect(events).toContain('smtp:AUTH'));
    await sessionObject.fetch(objectRequest('/connection', {}, 'DELETE'));
    release(); expect((await connecting).status).toBe(409);
    expect(await (await sessionObject.fetch(objectRequest('/me', {}, 'GET'))).json()).toHaveProperty('connection', null);
    expect(events.some(event => event.startsWith('smtp:MAIL'))).toBe(false);
  });
  it('commits a claim before SMTP and never advances a replay to another recipient', async () => {
    const sessionObject = object(); await sessionObject.fetch(objectRequest('/connection', { app_password: 'abcdefghijklmnop' })); events.length = 0;
    const result = await sessionObject.fetch(objectRequest('/batches/' + stored.id + '/next', { ordinal: 0 }));
    expect(result.status).toBe(200); expect(events.indexOf('db:claim')).toBeLessThan(events.findIndex(value => value.startsWith('smtp:MAIL')));
    expect(events.indexOf('db:finish')).toBeGreaterThan(events.findIndex(value => value === 'smtp:DATA'));
    const calls = vi.mocked(connect).mock.calls.length;
    await sessionObject.fetch(objectRequest('/batches/' + stored.id + '/next', { ordinal: 0 })); expect(connect).toHaveBeenCalledTimes(calls);
  });
  it('reports finalization uncertainty without leaking diagnostics or retrying SMTP', async () => {
    const sessionObject = object(); await sessionObject.fetch(objectRequest('/connection', { app_password: 'abcdefghijklmnop' })); failFinish = true;
    const response = await sessionObject.fetch(objectRequest('/batches/' + stored.id + '/next', { ordinal: 0 }));
    const text = await response.text(); expect(response.status).toBe(503); expect(text).toContain('Do not resend'); expect(text).not.toContain('private diagnostic'); expect(text).not.toContain(SECRET);
    const calls = vi.mocked(connect).mock.calls.length;
    await sessionObject.fetch(objectRequest('/batches/' + stored.id + '/next', { ordinal: 0 })); expect(connect).toHaveBeenCalledTimes(calls);
  });
});
