import { sign } from './crypto';
export const PROJECT = 'https://gnmimpoeqxeczjhvzrrx.supabase.co';
export interface Env {
  APP_ORIGIN: string;
  SUPABASE_URL: string;
  SUPABASE_PUBLISHABLE_KEY: string;
  CLOUD_MAIL_SIGNING_SECRET: string;
  LIVE_SENDS_ALLOWED?: string;
  ASSETS: Fetcher;
  MAIL_SESSIONS: DurableObjectNamespace;
}
export type Identity = { id: string; email: string; session: string; token: string };
export class Fault extends Error {
  constructor(message: string, public status = 400) { super(message); }
}
export function configured(env: Env): boolean {
  return env.SUPABASE_URL === PROJECT && Boolean(env.SUPABASE_PUBLISHABLE_KEY?.startsWith('sb_publishable_')) && env.CLOUD_MAIL_SIGNING_SECRET?.length >= 64;
}
export async function authenticate(request: Request, env: Env): Promise<Identity> {
  if (!configured(env)) throw new Fault('Application configuration is incomplete. Contact the administrator.', 503);
  const token = request.headers.get('Authorization')?.match(/^Bearer ([A-Za-z0-9_.-]+)$/)?.[1];
  if (!token || token.length > 8192) throw new Fault('Sign in to continue.', 401);
  const response = await fetch(PROJECT + '/auth/v1/user', { headers: { apikey: env.SUPABASE_PUBLISHABLE_KEY, Authorization: 'Bearer ' + token }, signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Fault('Sign-in expired. Request a fresh sign-in link.', 401);
  const user = await response.json() as { id: string; email: string; email_confirmed_at?: string };
  if (!user.email_confirmed_at || !user.id || !user.email) throw new Fault('Verify your email before continuing.', 403);
  // JWT is decoded only AFTER GoTrue verified it; SQL also checks this real session.
  let session: string;
  try { session = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).session_id; } catch { throw new Fault('Invalid sign-in session.', 401); }
  if (!session || !/^[a-f0-9-]{36}$/i.test(session)) throw new Fault('Invalid sign-in session.', 401);
  return { id: user.id, email: user.email.toLowerCase(), session, token };
}
const safeDatabaseErrors = /^(Administrator |Verified |Name and |Invalid |Batch |Daily |A recipient |Duplicate |Live sending |Disable the |Confirm permitted |Connection limit |Content hash |Recipient order |Resolve the |Submission |Debug screen |Unsupported )/;
export class Store {
  constructor(private env: Env, private identity: Identity) {}
  async act<T = unknown>(operation: string, payload: unknown = {}, batch_id: string | null = null): Promise<T> {
    const command = JSON.stringify({ owner: this.identity.id, session: this.identity.session, expires: Math.floor(Date.now() / 1000) + 60, operation, batch_id, payload });
    const response = await fetch(PROJECT + '/rest/v1/rpc/cloud_mail_action', {
      method: 'POST', headers: { apikey: this.env.SUPABASE_PUBLISHABLE_KEY, Authorization: 'Bearer ' + this.identity.token, 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, signature: await sign(this.env.CLOUD_MAIL_SIGNING_SECRET, command) }), signal: AbortSignal.timeout(15000)
    });
    if (!response.ok) {
      let message = '';
      try { message = (await response.json() as { message?: string }).message || ''; } catch { /* Do not expose response bodies. */ }
      if (safeDatabaseErrors.test(message) && message.length < 180) throw new Fault(message, 403);
      throw new Fault('Database operation blocked. Check access and deployment configuration.', 503);
    }
    return await response.json() as T;
  }
}
