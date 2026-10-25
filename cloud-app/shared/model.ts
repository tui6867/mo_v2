export type Contact = { name: string; email: string };
export type Message = Contact & { subject: string; body: string };
export type AttemptState = 'pending' | 'submitting' | 'accepted' | 'failed' | 'unknown' | 'cancelled';
export type Attempt = Contact & { ordinal: number; state: AttemptState; detail: string; message_id: string | null; updated_at: string };
export type Batch = { id: string; status: string; created_at: string; messages: Message[]; attempts: Attempt[] };
export type Access = { id: string; email: string; approved: boolean; is_admin: boolean; request_status: string; full_name: string; purpose: string; daily_limit: number; remaining: number; live_enabled: boolean; debug_enabled: boolean; batch_limit: number; global_daily_limit: number };

export function address(value: string): string {
  const email = value.trim().toLowerCase();
  if (email.length > 254 || !/^[a-z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/.test(email)) throw new Error('Enter a valid ASCII email address.');
  const local = email.split('@')[0];
  if (local.length > 64 || local.startsWith('.') || local.endsWith('.') || local.includes('..')) throw new Error('Enter a valid email address.');
  return email;
}

export function messages(value: unknown): Message[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 5) throw new Error('Choose between 1 and 5 recipients.');
  const seen = new Set<string>();
  return value.map(item => {
    if (!item || typeof item !== 'object' || ['name', 'email', 'subject', 'body'].some(key => typeof item[key] !== 'string')) throw new Error('Each email needs a name, address, subject and body.');
    const email = address(item.email);
    if (seen.has(email)) throw new Error('Remove duplicate recipients before reviewing.');
    seen.add(email);
    const name = item.name.trim(); const subject = item.subject.trim(); const body = item.body.replace(/\r\n?/g, '\n');
    if (name.length > 200 || /[\x00-\x1f\x7f]/.test(name) || !subject || subject.length > 200 || /[\x00-\x1f\x7f]/.test(subject) || !body.trim() || body.length > 10000 || /[\x00\x0b\x0c\x7f]/.test(body)) throw new Error('Check name, subject (200 characters) and body (10,000 characters). Header line breaks are not allowed.');
    return { name, email, subject, body };
  });
}

export function personalize(template: string, contact: Contact): string {
  const values: Record<string, string> = { name: contact.name, first_name: contact.name.trim().split(/\s+/)[0] || '', email: contact.email };
  return template.replace(/\{\{\s*([a-z_]+)\s*\}\}/gi, (_, key: string) => {
    if (!(key.toLowerCase() in values)) throw new Error(`Unknown template field: ${key}. Use name, first_name or email.`);
    return values[key.toLowerCase()];
  });
}

/** RFC4180-style CSV, with BOM/quoted commas/newlines/doubled quotes. Never evals cells. */
export function parseContacts(source: string): { contacts: Contact[]; warnings: string[] } {
  if (new TextEncoder().encode(source).length > 262144) throw new Error('CSV must be smaller than 256 KB.');
  const rows: string[][] = []; let row: string[] = []; let cell = ''; let quoted = false; let closed = false;
  const text = source.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');
  const endCell = () => { row.push(cell); cell = ''; closed = false; };
  const endRow = () => { endCell(); if (row.some(value => value.trim())) rows.push(row); row = []; };
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) { if (char === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else { quoted = false; closed = true; } } else cell += char; }
    else if (char === '"') { if (cell || closed) throw new Error('Malformed CSV quote.'); quoted = true; }
    else if (char === ',') endCell();
    else if (char === '\n') endRow();
    else { if (closed && char.trim()) throw new Error('Unexpected text after CSV quote.'); if (!closed) cell += char; }
  }
  if (quoted) throw new Error('CSV contains an unclosed quote.');
  if (cell || row.length || closed) endRow();
  if (rows.length < 2 || rows.length > 501) throw new Error('Provide a header and 1–500 contact rows.');
  const headers = rows[0].map(value => value.trim().toLowerCase().replace(/[\s_-]/g, ''));
  const emailIndex = headers.findIndex(value => ['email', 'emailaddress', 'e-mail'].includes(value));
  if (emailIndex < 0 || headers.filter(value => ['email', 'emailaddress'].includes(value)).length !== 1) throw new Error('CSV needs exactly one email column. Optional: name, or first_name and last_name.');
  const nameIndex = headers.findIndex(value => ['name', 'fullname'].includes(value)); const first = headers.indexOf('firstname'); const last = headers.indexOf('lastname');
  const seen = new Set<string>(); const contacts: Contact[] = []; const warnings: string[] = [];
  rows.slice(1).forEach((values, index) => {
    if (values.length !== headers.length) throw new Error(`CSV row ${index + 2} has the wrong number of columns.`);
    let email: string;
    try { email = address(values[emailIndex] || ''); } catch { throw new Error(`CSV row ${index + 2} has an invalid email address.`); }
    const name = (nameIndex >= 0 ? values[nameIndex] : [first >= 0 ? values[first] : '', last >= 0 ? values[last] : ''].filter(Boolean).join(' ')).trim();
    if (name.length > 200 || /[\x00-\x1f\x7f]/.test(name)) throw new Error(`CSV row ${index + 2} has an invalid name.`);
    if (seen.has(email)) { warnings.push(`Duplicate address on row ${index + 2} was omitted.`); return; }
    seen.add(email); contacts.push({ name, email });
  });
  if (!contacts.length) throw new Error('No usable recipients in CSV.');
  if (contacts.length > 5) warnings.push('Select up to 5 contacts for this batch. Remaining contacts are not sent or saved.');
  return { contacts, warnings };
}
