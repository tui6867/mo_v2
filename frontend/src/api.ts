export type Config = { supabase_url: string; publishable_key: string; transport: 'capture' | 'gmail'; live_enabled: boolean };
export type Connection = { id: string; email: string; expires_at: number };
export type Draft = { connection_id: string; recipient: string; subject: string; body: string };
export type Preview = { sender: string; reply_to: string; recipient: string; subject: string; body: string; approval: string; expires_at: number };
export type Attempt = { state: string; detail: string; email: string };
export type History = { id: string; subject: string; test_mode: boolean; status: string };

export async function api<T>(path: string, token = '', method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method,
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Request blocked. Refresh history before trying again.');
  return data as T;
}
