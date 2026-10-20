import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { SupabaseClient } from '@supabase/supabase-js';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { api, type Config } from './api';

vi.mock('./api', () => ({ api: vi.fn() }));
const request = vi.mocked(api);
const config: Config = { supabase_url: 'https://gnmimpoeqxeczjhvzrrx.supabase.co', publishable_key: 'synthetic', transport: 'capture', live_enabled: false };

function auth(signedIn = true) {
  return { auth: {
    onAuthStateChange: (callback: (event: string, session: unknown) => void) => {
      queueMicrotask(() => callback('INITIAL_SESSION', signedIn ? { access_token: 'synthetic-token' } : null));
      return { data: { subscription: { unsubscribe: vi.fn() } } };
    },
    signInWithOtp: vi.fn().mockResolvedValue({ error: null }),
    signOut: vi.fn().mockResolvedValue({ error: null }),
  } } as unknown as SupabaseClient;
}

beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async path => {
    if (path === '/me') return { email: 'alice@gmail.com', recipient: 'test@example.com', connection: null };
    if (path === '/connection') return { id: 'synthetic-connection', email: 'alice@gmail.com', expires_at: 9999999999 };
    if (path === '/preview') return { sender: 'alice@gmail.com', reply_to: 'alice@gmail.com', recipient: 'test@example.com', subject: 'Test', body: 'Body', approval: 'a'.repeat(64), expires_at: 9999999999 };
    if (path === '/messages') return [];
    if (path === '/send') return { id: 'synthetic-id', attempts: [{ state: 'accepted', detail: 'Capture only' }] };
    return {};
  });
});

async function compose() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Start capture session' }));
  await user.type(screen.getByLabelText('Subject'), 'Test');
  await user.type(screen.getByLabelText('Plain-text message'), 'Body');
  await user.click(screen.getByRole('button', { name: 'Preview exact email' }));
  await screen.findByRole('article', { name: 'Exact email preview' });
  return user;
}

describe('controlled mail UI', () => {
  it('requires a connection, exact review and confirmation; duplicate clicks send once', async () => {
    render(<App config={config} auth={auth()} />);
    expect(await screen.findByRole('button', { name: 'Preview exact email' })).toBeDisabled();
    const user = await compose();
    const send = screen.getByRole('button', { name: 'Capture one email' });
    expect(send).toBeDisabled();
    await user.click(screen.getByRole('checkbox'));
    await user.dblClick(send);
    await screen.findByText('accepted: Capture only');
    expect(request.mock.calls.filter(([path]) => path === '/send')).toHaveLength(1);
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  });

  it('invalidates approval when content changes', async () => {
    render(<App config={config} auth={auth()} />);
    const user = await compose();
    await user.type(screen.getByLabelText('Subject'), '!');
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
    expect(request.mock.calls.some(([path]) => path === '/send')).toBe(false);
  });

  it('clears the password before a failing connect and never stores it', async () => {
    request.mockImplementation(async path => {
      if (path === '/me') return { email: 'alice@gmail.com', recipient: 'test@example.com', connection: null };
      throw new Error('Credentials rejected');
    });
    const local = vi.spyOn(Storage.prototype, 'setItem');
    render(<App config={{ ...config, transport: 'gmail', live_enabled: true }} auth={auth()} />);
    const user = userEvent.setup();
    const field = await screen.findByLabelText('Google app password');
    await user.type(field, 'synthetic-password');
    await user.click(screen.getByRole('button', { name: 'Connect Gmail' }));
    await screen.findByText('Credentials rejected');
    expect(field).toHaveValue('');
    expect(local).not.toHaveBeenCalled();
    local.mockRestore();
  });

  it('disables Gmail credential entry when the operator gate is off', async () => {
    render(<App config={{ ...config, transport: 'gmail' }} auth={auth()} />);
    expect(await screen.findByLabelText('Google app password')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Connect Gmail' })).toBeDisabled();
  });

  it('shows finalization uncertainty without retrying', async () => {
    const base = request.getMockImplementation()!;
    request.mockImplementation(async (...args) => args[0] === '/send' ? { id: 'id', detail: 'Do not resend; database finalization failed.' } : base(...args));
    render(<App config={config} auth={auth()} />);
    const user = await compose();
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Capture one email' }));
    await screen.findByText('Do not resend; database finalization failed.');
    expect(request.mock.calls.filter(([path]) => path === '/send')).toHaveLength(1);
  });

  it('offers sign-in rather than credential entry for anonymous users', async () => {
    render(<App config={config} auth={auth(false)} />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Email sign-in link' })).toBeEnabled());
    expect(screen.queryByLabelText('Google app password')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Capture one email' })).not.toBeInTheDocument();
  });
});
