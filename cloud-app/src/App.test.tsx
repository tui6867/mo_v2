// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { SupabaseClient } from '@supabase/supabase-js';
import { App } from './App';
import { api } from './api';
vi.mock('./api', () => ({ api: vi.fn(), setAuth: vi.fn() }));
let me: Record<string, unknown>; let auth: SupabaseClient; let callback: (event: string, session: unknown) => void; let batch: any;
beforeEach(() => {
  me = { id: 'owner', email: 'sender@gmail.com', approved: true, is_admin: false, remaining: 10, daily_limit: 10, live_enabled: true, debug_enabled: false, batch_limit: 5, global_daily_limit: 50, connection: null };
  auth = { auth: { onAuthStateChange: vi.fn((fn: typeof callback) => { callback = fn; queueMicrotask(() => fn('SIGNED_IN', { access_token: 'synthetic', user: { id: 'owner' } })); return { data: { subscription: { unsubscribe: vi.fn() } } }; }), signOut: vi.fn(async () => ({ error: null })) } } as unknown as SupabaseClient;
  vi.mocked(api).mockImplementation(async (path, data: any) => {
    if (path === '/me') return structuredClone(me) as never;
    if (path === '/connection') { me.connection = { id: 'connection', expires_at: Date.now() + 1800000 }; return { connected: true } as never; }
    if (path === '/preview') return { ...data, sender: me.email, receipt: 'synthetic', approval: 'synthetic', expires_at: Date.now() + 600000 } as never;
    if (path === '/batches' && data) { batch = { id: 'batch-id', status: 'active', created_at: new Date().toISOString(), messages: data.messages, attempts: data.messages.map((item: object, ordinal: number) => ({ ...item, ordinal, state: 'pending', detail: 'Waiting', updated_at: new Date().toISOString() })) }; return structuredClone(batch); }
    if (path.endsWith('/next')) { batch.attempts[data.ordinal].state = 'accepted'; batch.attempts[data.ordinal].detail = 'Gmail accepted the message. Inbox delivery is not confirmed.'; if (batch.attempts.every((item: any) => item.state === 'accepted')) batch.status = 'completed'; return structuredClone(batch); }
    if (path === '/batches') return [] as never;
    if (path === '/admin/users') return [] as never;
    if (path === '/admin/settings') { me.debug_enabled = data.debug_enabled; return true as never; }
    return true as never;
  });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });
describe('operational workspace', () => {
  it('imports CSV, edits personal messages, reviews every recipient and submits only after exact confirmation', async () => {
    const user = userEvent.setup(); render(<App auth={auth} transportAvailable />);
    await screen.findByRole('button', { name: /Choose your contact list/ });
    const file = new File(['email,name\nana@example.com,Ana María\nbob@example.com,Bob Lee'], 'contacts.csv', { type: 'text/csv' });
    Object.defineProperty(file, 'text', { value: async () => 'email,name\nana@example.com,Ana María\nbob@example.com,Bob Lee' });
    await user.upload(screen.getByLabelText('Upload contact CSV'), file);
    await screen.findByDisplayValue('Ana María');
    await user.click(screen.getByRole('button', { name: /Connect your account/ }));
    const password = await screen.findByLabelText('Dedicated Google app password');
    await user.type(password, 'abcdefghijklmnop'); await user.click(screen.getByRole('button', { name: /^Connect Gmail/ }));
    await waitFor(() => expect(password).toHaveValue(''));
    await user.click(await screen.findByRole('button', { name: /^Write messages$/ }));
    fireEvent.change(screen.getByLabelText('Starting subject'), { target: { value: 'Hello {{first_name}}' } });
    fireEvent.change(screen.getByLabelText('Starting message'), { target: { value: 'Hi {{name}},\nA personal introduction.' } });
    await user.click(screen.getByRole('button', { name: /Apply to selected/ }));
    await user.click(screen.getByRole('button', { name: /Review exact batch/ }));
    const send = await screen.findByRole('button', { name: /Send 2 real emails/ }); expect(send).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Bob Lee/ }));
    await user.click(screen.getByRole('checkbox', { name: /I am permitted/ })); await user.click(screen.getByRole('checkbox', { name: /I approve these exact/ }));
    expect(api).not.toHaveBeenCalledWith('/batches', expect.anything());
    await user.click(send);
    await waitFor(() => expect(screen.getAllByText('SMTP accepted')).toHaveLength(2));
    expect(vi.mocked(api).mock.calls.filter(([path]) => path.endsWith('/next')).map(([, data]) => data)).toEqual([{ ordinal: 0 }, { ordinal: 1 }]);
    expect(screen.queryByText(/^Delivered$/)).not.toBeInTheDocument(); expect(screen.queryByText(/Simulate sending/)).not.toBeInTheDocument();
  });
  it('keeps unapproved users out of the sending workflow', async () => {
    me.approved = false; me.request_status = 'pending'; render(<App auth={auth} transportAvailable />);
    await screen.findByText(/An administrator must approve/); expect(screen.queryByText('Dedicated Google app password')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Update access request/ })).toBeInTheDocument();
  });
  it('removes debug UI through the protected administrator switch', async () => {
    me.is_admin = true; me.debug_enabled = true; const user = userEvent.setup(); render(<App auth={auth} transportAvailable />);
    await user.click(await screen.findByRole('button', { name: 'Manage access' }));
    await user.click(await screen.findByRole('button', { name: 'Remove debug screen' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Debug' })).not.toBeInTheDocument());
    expect(api).toHaveBeenCalledWith('/admin/settings', { debug_enabled: false });
  });
  it('clears recipient data immediately when the signed-in identity changes', async () => {
    const user = userEvent.setup(); render(<App auth={auth} transportAvailable />);
    await user.click(await screen.findByRole('button', { name: /Add a recipient manually/ }));
    expect(screen.getByLabelText(/^Name for/)).toBeInTheDocument();
    await act(async () => callback('SIGNED_IN', { access_token: 'other', user: { id: 'other' } }));
    expect(screen.queryByLabelText(/^Name for/)).not.toBeInTheDocument();
  });
});
