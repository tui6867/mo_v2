// LOCAL TEST ENTRY ONLY. Not imported by index.html or the production Worker.
// No real Auth link, app password, SMTP operation or remote database is used.
import { createRoot } from 'react-dom/client';
import type { SupabaseClient } from '@supabase/supabase-js';
import '@fontsource-variable/manrope';
import { App } from '../src/App';
import '../src/styles.css';
const email = 'operator@example.com';
const me = { id: 'fixture', email, approved: true, is_admin: true, remaining: 10, daily_limit: 10, live_enabled: true, debug_enabled: true, batch_limit: 5, global_daily_limit: 50, connection: { id: 'fixture', expires_at: Date.now() + 1800000 } };
let batch: any;
window.fetch = async (input, init) => {
  const path = String(input).replace(/^\/api/, '');
  if (!String(input).startsWith('/api/')) throw new Error('External access is forbidden in this fixture');
  const data = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown = true;
  if (path === '/me') result = me;
  else if (path === '/preview') result = { sender: email, ...data, expires_at: Date.now() + 600000, receipt: 'fixture', approval: 'fixture' };
  else if (path === '/batches' && init?.method === 'POST') result = batch = { id: 'fixture-batch', status: 'active', created_at: new Date().toISOString(), messages: data.messages, attempts: data.messages.map((message: object, ordinal: number) => ({ ...message, ordinal, state: 'pending', detail: 'Waiting for approval.', updated_at: new Date().toISOString() })) };
  else if (path.endsWith('/next')) { batch.attempts[data.ordinal].state = 'accepted'; batch.attempts[data.ordinal].detail = 'Gmail accepted the message. Inbox delivery is not confirmed.'; batch.status = batch.attempts.every((item: any) => item.state === 'accepted') ? 'completed' : 'active'; result = batch; }
  else if (path === '/batches') result = [];
  else if (path.startsWith('/batches/')) result = batch;
  else if (path === '/admin/users') result = [{ id: 'applicant', email: 'applicant@example.com', active: false, is_admin: false, full_name: 'An Applicant', purpose: 'Permitted personal introductions.', admin_notes: '', daily_limit: 10, status: 'pending' }];
  else if (path === '/admin/settings') { if ('debug_enabled' in data) me.debug_enabled = data.debug_enabled; if ('live_enabled' in data) me.live_enabled = data.live_enabled; }
  else if (path === '/suppressions') result = [];
  else if (path === '/debug') result = { database: 'test fixture', credential_storage: 'No credentials present' };
  return Response.json(result);
};
const auth = { auth: { onAuthStateChange(fn: Function) { queueMicrotask(() => fn('SIGNED_IN', { access_token: 'fixture-not-a-real-token', user: { id: 'fixture' } })); return { data: { subscription: { unsubscribe() {} } } }; } } } as unknown as SupabaseClient;
createRoot(document.getElementById('root')!).render(<App auth={auth} transportAvailable />);
