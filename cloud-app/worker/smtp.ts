import type { Message } from '../shared/model';
export type SocketLike = { readable: ReadableStream<Uint8Array>; writable: WritableStream<Uint8Array>; close(): Promise<void> };
export type Dial = () => Promise<SocketLike>;
export type Submission = { state: 'accepted' | 'failed' | 'unknown' };
const encoder = new TextEncoder();
const base64 = (value: string) => btoa(Array.from(encoder.encode(value), byte => String.fromCharCode(byte)).join(''));
function subjectHeader(subject: string): string {
  const chunks: string[] = []; let current = '';
  for (const character of subject) { if (encoder.encode(current + character).length > 42) { chunks.push(current); current = ''; } current += character; }
  if (current) chunks.push(current);
  return chunks.map(value => '=?UTF-8?B?' + base64(value) + '?=').join('\r\n ');
}
export function mime(sender: string, message: Message, messageId: string, date = new Date()): string {
  const encodedBody = base64(message.body.replace(/\r\n?/g, '\n').replace(/\n/g, '\r\n')).match(/.{1,76}/g)?.join('\r\n') || '';
  return [`From: ${sender}`, `Reply-To: ${sender}`, `To: ${message.email}`, `Subject: ${subjectHeader(message.subject)}`, `Date: ${date.toUTCString()}`, `Message-ID: ${messageId}`, 'MIME-Version: 1.0', 'Content-Type: text/plain; charset=UTF-8', 'Content-Transfer-Encoding: base64', '', encodedBody, ''].join('\r\n');
}
class ProtocolError extends Error {}
class Client {
  private reader: ReadableStreamDefaultReader<Uint8Array>;
  private writer: WritableStreamDefaultWriter<Uint8Array>;
  private buffer = '';
  private decoder = new TextDecoder();
  constructor(socket: SocketLike, private assertActive: () => void) { this.reader = socket.readable.getReader(); this.writer = socket.writable.getWriter(); }
  async reply(): Promise<{ code: number; lines: string[] }> {
    const lines: string[] = []; let code = 0; let size = 0;
    for (let i = 0; i < 100; i++) {
      this.assertActive();
      while (!this.buffer.includes('\r\n')) {
        if (this.buffer.length > 8192) throw new ProtocolError();
        const chunk = await this.reader.read();
        this.assertActive();
        if (chunk.done) throw new ProtocolError();
        this.buffer += this.decoder.decode(chunk.value, { stream: true });
      }
      const end = this.buffer.indexOf('\r\n'); const line = this.buffer.slice(0, end); this.buffer = this.buffer.slice(end + 2);
      size += line.length; if (size > 32768) throw new ProtocolError();
      const match = line.match(/^(\d{3})([ -])(.*)$/);
      if (!match || (code && code !== Number(match[1]))) throw new ProtocolError();
      code = Number(match[1]); lines.push(match[3]);
      if (match[2] === ' ') return { code, lines };
    }
    throw new ProtocolError();
  }
  write(value: string) { this.assertActive(); return this.writer.write(encoder.encode(value)); }
  async command(value: string) { await this.write(value + '\r\n'); return this.reply(); }
}

/** Fixed Gmail TLS endpoint supplied by index.ts. Never accepts a client SMTP host. */
async function transact(dial: Dial, sender: string, password: string, message?: Message, messageId?: string): Promise<Submission> {
  let socket: SocketLike | undefined; let dataStarted = false; let stopped = false; let timeout: ReturnType<typeof setTimeout> | undefined;
  const assertActive = () => { if (stopped) throw new ProtocolError(); };
  const session = async (): Promise<Submission> => {
    socket = await dial();
    // A delayed connection must never resume authentication/submission after the
    // outer deadline has returned. It may not have existed during finally.
    if (stopped) { await socket.close().catch(() => {}); throw new ProtocolError(); }
    const client = new Client(socket, assertActive);
    if ((await client.reply()).code !== 220) throw new ProtocolError();
    const hello = await client.command('EHLO mass-outreach.invalid');
    if (hello.code !== 250 || !hello.lines.some(line => /^AUTH\b.*\bPLAIN\b/i.test(line))) throw new ProtocolError();
    const auth = await client.command('AUTH PLAIN ' + base64('\0' + sender + '\0' + password));
    if (auth.code !== 235) return { state: 'failed' };
    if (!message || !messageId) return { state: 'accepted' }; // Authentication only: no envelope or DATA.
    if ((await client.command('MAIL FROM:<' + sender + '>')).code !== 250) return { state: 'failed' };
    const recipient = await client.command('RCPT TO:<' + message.email + '>');
    if (![250, 251].includes(recipient.code)) return { state: 'failed' };
    if ((await client.command('DATA')).code !== 354) return { state: 'failed' };
    dataStarted = true; // Any disconnect from here is uncertain unless a final response says otherwise.
    await client.write(mime(sender, message, messageId) + '.\r\n');
    const final = await client.reply();
    if (final.code === 250) return { state: 'accepted' };
    if (final.code >= 400 && final.code <= 599) return { state: 'failed' };
    return { state: 'unknown' };
  };
  try {
    return await Promise.race([session(), new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new ProtocolError()), 20000); })]);
  } catch { return { state: dataStarted ? 'unknown' : 'failed' }; }
  finally { stopped = true; if (timeout) clearTimeout(timeout); if (socket) await socket.close().catch(() => {}); }
}
export const testGmail = (dial: Dial, sender: string, password: string) => transact(dial, sender, password);
export const submitGmail = (dial: Dial, sender: string, password: string, message: Message, messageId: string) => transact(dial, sender, password, message, messageId);
