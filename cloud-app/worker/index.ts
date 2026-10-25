import { connect } from 'cloudflare:sockets';
import { messages, type Access, type Batch, type Message } from '../shared/model';
import { digest, sign, signedEqual } from './crypto';
import { authenticate, configured, Fault, PROJECT, Store, type Env, type Identity } from './store';
import { submitGmail, testGmail, type Dial } from './smtp';

const dial: Dial = async () => {
  const socket = connect({ hostname: 'smtp.gmail.com', port: 465 }, { secureTransport: 'on', allowHalfOpen: false });
  socket.opened.catch(() => {});
  socket.closed.catch(() => {});
  return socket;
};
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });
function failure(error: unknown): Response {
  const fault = error instanceof Fault ? error : new Fault('Request failed. Refresh durable status before trying to send again.', 500);
  return json({ error: fault.message, request_id: crypto.randomUUID() }, fault.status);
}
async function body(request: Request): Promise<Record<string, unknown>> {
  if (!request.headers.get('Content-Type')?.startsWith('application/json')) throw new Fault('JSON request required.', 415);
  const reader = request.body?.getReader(); if (!reader) return {};
  const chunks: Uint8Array[] = []; let size = 0;
  while (true) { const result = await reader.read(); if (result.done) break; size += result.value.length; if (size > 120000) { await reader.cancel(); throw new Fault('Request is too large.', 413); } chunks.push(result.value); }
  const bytes = new Uint8Array(size); let offset = 0; for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try { const value = JSON.parse(new TextDecoder().decode(bytes)); if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error(); return value; } catch { throw new Fault('Invalid JSON request.'); }
}
function secure(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set('Content-Security-Policy', `default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self' ${PROJECT}; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`);
  headers.set('Strict-Transport-Security', 'max-age=31536000'); headers.set('X-Content-Type-Options', 'nosniff'); headers.set('Referrer-Policy', 'no-referrer'); headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  return new Response(response.body, { status: response.status, headers });
}
function live(env: Env, access: Access) { if (env.LIVE_SENDS_ALLOWED !== 'true' || !access.live_enabled) throw new Fault('Live sending is disabled by the administrator.', 403); }
function validMessages(value: unknown): Message[] { try { return messages(value); } catch (error) { throw new Fault((error as Error).message); } }

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      const url = new URL(request.url); const path = url.pathname;
      if (!path.startsWith('/api/')) return secure(await env.ASSETS.fetch(request));
      if (request.method === 'OPTIONS') throw new Fault('Cross-origin requests are not supported.', 403);
      if (!['GET', 'POST', 'DELETE'].includes(request.method)) throw new Fault('Method not allowed.', 405);
      if (request.method !== 'GET' && request.headers.get('Origin') !== env.APP_ORIGIN) throw new Fault('Request origin is not allowed.', 403);
      if (request.method === 'GET' && path === '/api/health') return secure(json({ status: 'ok', configured: configured(env), transport: 'gmail', background_sending: false }));
      if (request.method === 'GET' && path === '/api/config') {
        if (!configured(env)) throw new Fault('Application configuration is incomplete. Contact the administrator.', 503);
        return secure(json({ supabase_url: PROJECT, publishable_key: env.SUPABASE_PUBLISHABLE_KEY, live_transport_available: env.LIVE_SENDS_ALLOWED === 'true' }));
      }
      const identity = await authenticate(request, env); const store = new Store(env, identity);
      const payload = request.method === 'GET' || request.method === 'DELETE' ? {} : await body(request);
      if (['/api/me', '/api/connection', '/api/preview', '/api/batches'].includes(path) && !(path === '/api/batches' && request.method === 'GET') || /^\/api\/batches\/[a-f0-9-]{36}\/next$/.test(path)) {
        const allowed: Record<string, string[]> = { '/api/me': ['GET'], '/api/connection': ['POST', 'DELETE'], '/api/preview': ['POST'], '/api/batches': ['POST'] };
        if (allowed[path] && !allowed[path].includes(request.method)) throw new Fault('Method not allowed.', 405);
        if (path.endsWith('/next') && request.method !== 'POST') throw new Fault('Method not allowed.', 405);
        const stub = env.MAIL_SESSIONS.get(env.MAIL_SESSIONS.idFromName(identity.id));
        return secure(await stub.fetch(new Request('https://session.internal' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ identity, method: request.method, payload }) })));
      }
      let result: unknown;
      if (path === '/api/request-access' && request.method === 'POST') result = await store.act('request_access', payload);
      else if (path === '/api/batches' && request.method === 'GET') result = await store.act('list');
      else if (path === '/api/suppressions' && ['GET', 'POST'].includes(request.method)) result = await store.act(request.method === 'GET' ? 'suppressions' : 'suppress', payload);
      else if (path === '/api/admin/users' && request.method === 'GET') result = await store.act('admin_users');
      else if (path === '/api/admin/settings' && request.method === 'POST') {
        if (payload.live_enabled === true && env.LIVE_SENDS_ALLOWED !== 'true') throw new Fault('Gmail transport is disabled in the deployment.', 403);
        result = await store.act('admin_settings', payload);
      }
      else if (/^\/api\/admin\/(approve|revoke|update)$/.test(path) && request.method === 'POST') result = await store.act('admin_' + path.split('/').pop(), payload);
      else if (path === '/api/debug' && request.method === 'GET') result = { ...await store.act<object>('debug'), transport: 'Gmail TLS :465', credential_storage: 'Session object memory only; eviction requires reconnecting.', version: 'cloud-mail-v1', live_transport_available: env.LIVE_SENDS_ALLOWED === 'true' };
      else {
        const match = path.match(/^\/api\/batches\/([a-f0-9-]{36})(?:\/(cancel|recover))?$/);
        if (!match || (match[2] ? request.method !== 'POST' : request.method !== 'GET')) throw new Fault('Endpoint not found.', 404);
        result = await store.act(match[2] || 'get', {}, match[1]);
      }
      return secure(json(result));
    } catch (error) { return secure(failure(error)); }
  }
};

type Credential = { id: string; owner: string; session: string; password: string; created: number; used: number };
type Receipt = { owner: string; session: string; connection: string; hash: string; expires: number };
export class MailSession {
  private credential?: Credential;
  private connecting?: { owner: string; session: string };
  private generation = 0;
  private busy = false;
  constructor(private state: DurableObjectState, private env: Env) {}
  private active(identity: Identity, touch = false): Credential | undefined {
    const item = this.credential; const now = Date.now();
    if (item && (now - item.created >= 7200000 || now - item.used >= 1800000)) this.credential = undefined;
    const current = this.credential;
    if (!current || current.owner !== identity.id || current.session !== identity.session) return undefined;
    if (touch) current.used = now;
    return current;
  }
  async alarm() { this.credential = undefined; this.generation++; }
  async fetch(request: Request): Promise<Response> {
    let locked = false;
    try {
      const internal = await body(request); const identity = internal.identity as Identity; const payload = internal.payload as Record<string, unknown>;
      const path = new URL(request.url).pathname; const method = internal.method;
      const store = new Store(this.env, identity); const access = await store.act<Access>('me');
      if (access.id !== identity.id || access.email !== identity.email) throw new Fault('Account identity changed. Sign in again.', 401);
      if (path === '/api/me') {
        if (!access.approved) { this.credential = undefined; this.generation++; }
        const current = this.active(identity);
        return json({ ...access, live_enabled: access.live_enabled && this.env.LIVE_SENDS_ALLOWED === 'true', connection: current ? { id: current.id, expires_at: Math.min(current.created + 7200000, current.used + 1800000) } : null });
      }
      if (path === '/api/connection' && method === 'DELETE') {
        if (this.active(identity) || (this.connecting?.owner === identity.id && this.connecting?.session === identity.session)) { this.credential = undefined; this.generation++; }
        return json({ disconnected: true, submission_may_be_in_flight: this.busy });
      }
      if (!access.approved) { this.credential = undefined; this.generation++; throw new Fault('Administrator approval required or access revoked.', 403); }
      if (this.busy) throw new Fault('A request is already in progress. Refresh status before continuing.', 409);
      this.busy = true; locked = true;
      if (path === '/api/connection') {
        live(this.env, access); await store.act('connect_attempt');
        const password = String(payload.app_password || '').replace(/\s/g, '');
        if (!/^[a-zA-Z0-9]{16}$/.test(password)) throw new Fault('Enter a 16-character Google app password, not your account password.');
        this.credential = undefined;
        const generation = ++this.generation; this.connecting = { owner: identity.id, session: identity.session };
        const result = await testGmail(dial, identity.email, password);
        this.connecting = undefined;
        if (generation !== this.generation) throw new Fault('Gmail connection was cancelled. No email was sent.', 409);
        if (result.state !== 'accepted') throw new Fault('Gmail connection failed. Check app-password eligibility and the dedicated app password. No email was sent.', 422);
        const now = Date.now(); this.credential = { id: crypto.randomUUID(), owner: identity.id, session: identity.session, password, created: now, used: now };
        await this.state.storage.setAlarm(now + 1800000);
        return json({ connected: true, expires_at: now + 1800000 });
      }
      const current = this.active(identity, true); if (!current) throw new Fault('Gmail session expired or was evicted. Reconnect; approved batches are preserved.', 409);
      await this.state.storage.setAlarm(Math.min(current.created + 7200000, current.used + 1800000));
      if (path === '/api/preview') {
        const rendered = validMessages(payload.messages); const hash = await digest(JSON.stringify(rendered));
        const expires = Date.now() + 600000;
        const receipt = JSON.stringify({ owner: identity.id, session: identity.session, connection: current.id, hash, expires });
        return json({ sender: identity.email, messages: rendered, expires_at: expires, receipt, approval: await sign(this.env.CLOUD_MAIL_SIGNING_SECRET, receipt) });
      }
      if (path === '/api/batches') {
        live(this.env, access);
        if (payload.confirmed !== true || payload.policy_ack !== true) throw new Fault('Review the exact messages and confirm permitted use before sending.');
        const receiptText = String(payload.receipt || '');
        if (receiptText.length > 2000 || !await signedEqual(this.env.CLOUD_MAIL_SIGNING_SECRET, receiptText, String(payload.approval || ''))) throw new Fault('Preview approval is invalid. Review again.');
        let receipt: Receipt; try { receipt = JSON.parse(receiptText); } catch { throw new Fault('Preview approval is invalid.'); }
        const rendered = validMessages(payload.messages); const hash = await digest(JSON.stringify(rendered));
        if (receipt.owner !== identity.id || receipt.session !== identity.session || receipt.connection !== current.id || receipt.hash !== hash || !Number.isFinite(receipt.expires) || receipt.expires < Date.now() || receipt.expires > Date.now() + 600001) throw new Fault('Preview expired or content/account changed. Review again.');
        const started = await store.act<{ id: string; existing: boolean }>('start', { messages: rendered, content_hash: hash }, crypto.randomUUID());
        return json({ ...await store.act<object>('get', {}, started.id), existing: started.existing });
      }
      const match = path.match(/^\/api\/batches\/([a-f0-9-]{36})\/next$/);
      if (!match) throw new Fault('Endpoint not found.', 404);
      live(this.env, access);
      const batch = await store.act<Batch>('get', {}, match[1]);
      if (!Number.isInteger(payload.ordinal) || Number(payload.ordinal) < 0 || Number(payload.ordinal) > 4) throw new Fault('Choose the intended recipient before continuing.');
      const next = batch.attempts.find(item => item.ordinal === payload.ordinal);
      // A replay of the same HTTP request may only refer to the same recipient.
      if (!next || next.state !== 'pending') return json(batch);
      const messageId = '<' + crypto.randomUUID() + '@' + identity.email.split('@')[1] + '>';
      const claim = await store.act<{ ordinal: number; claim_token: string; sender: string; message: Message } | null>('claim', { ordinal: next.ordinal, message_id: messageId }, batch.id);
      if (!claim) return json(await store.act('get', {}, batch.id));
      // Durable claim committed above. The immutable persisted message, not browser data, is submitted.
      const result = this.active(identity)?.id === current.id
        ? await submitGmail(dial, claim.sender, current.password, claim.message, messageId)
        : { state: 'failed' };
      try { return json(await store.act('finish', { ordinal: claim.ordinal, claim_token: claim.claim_token, state: result.state }, batch.id)); }
      catch { throw new Fault('Submission may have completed but final status could not be saved. Do not resend. Refresh status; recover after five minutes if needed.', 503); }
    } catch (error) { return failure(error); }
    finally { if (locked) { this.busy = false; this.connecting = undefined; } }
  }
}
