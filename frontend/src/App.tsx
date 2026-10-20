import { useEffect, useRef, useState } from 'react';
import type { SupabaseClient } from '@supabase/supabase-js';
import { api, type Attempt, type Config, type Connection, type Draft, type History, type Preview } from './api';
import { connectionEnabled } from './security';

type Props = { config: Config; auth: SupabaseClient };

export function App({ config, auth }: Props) {
  const [token, setToken] = useState('');
  const [email, setEmail] = useState('');
  const [invitation, setInvitation] = useState('');
  const [owner, setOwner] = useState('');
  const [recipient, setRecipient] = useState('');
  const [connection, setConnection] = useState<Connection | null>(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [history, setHistory] = useState<History[]>([]);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const password = useRef<HTMLInputElement>(null);
  const requestBusy = useRef(false);
  const live = config.transport === 'gmail';
  const connectEnabled = connectionEnabled(config, window.location.protocol);

  useEffect(() => {
    const { data } = auth.auth.onAuthStateChange((_event, session) => {
      setToken(session?.access_token || '');
      if (!session) { setOwner(''); setRecipient(''); setConnection(null); setHistory([]); setAttempts([]); setPreview(null); }
    });
    return () => data.subscription.unsubscribe();
  }, [auth]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    api<{ email: string; recipient: string; connection: Connection | null }>('/me', token)
      .then(me => { if (active) { setOwner(me.email); setRecipient(me.recipient); setConnection(me.connection); } })
      .catch(error => { if (active) { setOwner(''); setConnection(null); setMessage(error.message); } });
    return () => { active = false; };
  }, [token]);

  async function run(action: () => Promise<void>) {
    if (requestBusy.current) return;
    requestBusy.current = true;
    setBusy(true); setMessage('');
    try { await action(); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Request failed; refresh history before sending again.'); }
    finally { requestBusy.current = false; setBusy(false); }
  }

  function invalidate() { setPreview(null); setConfirmed(false); }
  function draft(): Draft {
    if (!connection) throw new Error('Reconnect first.');
    return { connection_id: connection.id, recipient, subject, body };
  }
  async function refreshHistory() { setHistory(await api<History[]>('/messages', token)); }

  return <main>
    <header><p className="eyebrow">CONTROLLED DEVELOPMENT PILOT</p><h1>Send one email, deliberately.</h1>
      <p>{live ? 'Gmail SMTP — real email only when enabled and confirmed.' : 'Capture mode — private Postfix → Mailpit. No external delivery.'}</p>
    </header>
    <aside>Only the operator’s test-owned recipient is permitted. No bulk sending, aliases, BCC, attachments or automatic retries. Gmail policy does not permit spam or unsolicited commercial mail.</aside>
    <p role="status" aria-live="polite">{message}</p>
    {!token ? <section><h2>1. Sign in to the app</h2>
      <form onSubmit={event => { event.preventDefault(); void run(async () => {
        const { error } = await auth.auth.signInWithOtp({ email, options: { emailRedirectTo: window.location.origin } });
        if (error) throw new Error('Sign-in email could not be requested. Check Supabase Auth configuration and rate limits.');
        setMessage('Check your email and open the sign-in link in your own browser. An application invitation is also required.');
      }); }}>
        <label htmlFor="login-email">Invited Gmail or Workspace address<input id="login-email" type="email" required value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" /></label>
        <button disabled={busy}>Email sign-in link</button>
      </form>
      <p>Use your own browser for sign-in. No Google account password belongs in this app.</p>
    </section> : <>
      {!owner && <section><h2>Redeem application invitation</h2><form onSubmit={event => { event.preventDefault(); void run(async () => {
        const value = invitation; setInvitation('');
        await api('/invitation', token, 'POST', { invitation: value });
        const me = await api<{ email: string; recipient: string; connection: Connection | null }>('/me', token);
        setOwner(me.email); setRecipient(me.recipient); setConnection(me.connection); setMessage('Application access confirmed.');
      }); }}>
        <label htmlFor="invitation-code">Invitation code<input id="invitation-code" type="password" value={invitation} required onChange={e => setInvitation(e.target.value)} autoComplete="off" /></label>
        <button disabled={busy}>Redeem invitation</button>
      </form></section>}
      {owner && <>
        <section><h2>1. Sending account</h2><p>Verified sender: <strong>{owner}</strong></p>
          <p>From, Reply-To, envelope sender and SMTP username must all match this address.</p>
          {connection ? <><p>Connected{live ? '' : ' for capture only'}. Expires no later than {new Date(connection.expires_at * 1000).toLocaleTimeString()}.</p>
            <button disabled={busy} onClick={() => void run(async () => { await api('/connection', token, 'DELETE'); setConnection(null); invalidate(); })}>Disconnect</button>
          </> : <form onSubmit={event => { event.preventDefault(); void run(async () => {
            const app_password = password.current?.value || '';
            if (password.current) password.current.value = '';
            invalidate();
            setConnection(await api<Connection>('/connection', token, 'POST', { app_password }));
            setMessage(live ? 'Gmail authentication succeeded. No email has been sent.' : 'Capture session ready; no SMTP credentials used.');
          }); }}>
            {live && <label htmlFor="app-password">Google app password<input id="app-password" ref={password} type="password" required disabled={!connectEnabled || busy} autoComplete="off" spellCheck={false} maxLength={32} /></label>}
            <button disabled={busy || !connectEnabled}>{live ? 'Connect Gmail' : 'Start capture session'}</button>
            {live && !config.live_enabled && <p>Live connections are disabled by the operator.</p>}
            {window.location.protocol !== 'https:' && <p>Use the trusted HTTPS application before connecting. Never enter a password on this HTTP development page.</p>}
          </form>}
          <p>Passwords stay in server process memory: 30 minutes idle, two hours maximum. Restart requires reconnecting. Disconnect does not revoke the app password or cancel an in-flight send.</p>
          {live && <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">Create or revoke an app password in your own browser</a>}
        </section>
        <section><h2>2. Compose and review</h2>
          <form onSubmit={event => { event.preventDefault(); void run(async () => { setPreview(await api<Preview>('/preview', token, 'POST', draft())); setConfirmed(false); }); }}>
            <label htmlFor="recipient">Test-owned recipient<input id="recipient" readOnly value={recipient} /></label>
            <label htmlFor="subject">Subject<input id="subject" required maxLength={200} value={subject} disabled={busy} onChange={e => { setSubject(e.target.value); invalidate(); }} /></label>
            <label htmlFor="body">Plain-text message<textarea id="body" required maxLength={10000} rows={8} value={body} disabled={busy} onChange={e => { setBody(e.target.value); invalidate(); }} /></label>
            <button disabled={busy || !connection}>Preview exact email</button>
          </form>
          {preview && <article aria-label="Exact email preview"><h3>Exact email preview</h3><dl><dt>From / Reply-To</dt><dd>{preview.sender}</dd><dt>To</dt><dd>{preview.recipient}</dd><dt>Subject</dt><dd>{preview.subject}</dd></dl><pre>{preview.body}</pre>
            <label className="check"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} />I approve this exact email to the test-owned recipient.</label>
            <button disabled={busy || !confirmed || !connection || !connectEnabled} onClick={() => void run(async () => {
              const review = preview; invalidate();
              const result = await api<{ id: string; attempts?: Attempt[]; detail?: string }>('/send', token, 'POST', { ...draft(), approval: review.approval, expires_at: review.expires_at, confirmed: true });
              setAttempts(result.attempts || []); setMessage(result.detail || 'Submission finished. SMTP acceptance is not inbox delivery.');
              await refreshHistory();
            })}>{live ? 'Send one real email' : 'Capture one email'}</button>
          </article>}
        </section>
        <section><h2>3. Durable status</h2><p>After a timeout or restart, refresh history. Unknown submissions must never be retried automatically. An identical message cannot be submitted again.</p>
          <button disabled={busy} onClick={() => void run(refreshHistory)}>Refresh history</button>
          <ul>{history.map(item => <li key={item.id}><strong>{item.subject}</strong> — {item.test_mode ? 'capture' : 'live'} / {item.status}
            <button disabled={busy} onClick={() => void run(async () => setAttempts(await api<Attempt[]>('/messages/' + item.id, token)))}>View status</button>
            <button disabled={busy} onClick={() => void run(async () => { setAttempts(await api<Attempt[]>('/messages/' + item.id + '/recover', token, 'POST')); await refreshHistory(); })}>Recover interrupted status (after 5 min)</button>
          </li>)}</ul>
          <ul>{attempts.map((attempt, i) => <li key={i}>{attempt.state}: {attempt.detail}</li>)}</ul>
        </section>
      </>}
      <button disabled={busy} onClick={() => void run(async () => {
        await api('/connection', token, 'DELETE');
        const { error } = await auth.auth.signOut();
        if (error) throw new Error('Connection cleared, but Auth sign-out failed. Close this tab and retry sign-out.');
      })}>Disconnect and sign out</button>
    </>}
    <footer>Development pilot only. Not approved for production outreach. No analytics or credential storage in this frontend.</footer>
  </main>;
}
