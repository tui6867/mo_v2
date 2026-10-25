let token = ''; let owner = '';
export function setAuth(value: string, userId: string) { token = value; owner = userId; }
export async function api<T>(path: string, data?: unknown, method?: string): Promise<T> {
  const requestOwner = owner;
  const response = await fetch('/api' + path, {
    method: method || (data === undefined ? 'GET' : 'POST'),
    headers: { ...(token ? { Authorization: 'Bearer ' + token } : {}), ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }), cache: 'no-store'
  });
  if (owner !== requestOwner) throw new Error('Account changed. Previous response discarded.');
  const result = await response.json() as T & { error?: string; request_id?: string };
  if (!response.ok) throw new Error(result.error || 'Request failed. Refresh durable status before sending again.');
  return result;
}
