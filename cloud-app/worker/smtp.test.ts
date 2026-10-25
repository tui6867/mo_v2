import { describe, expect, it, vi } from 'vitest';
import { mime, submitGmail, testGmail, type Dial } from './smtp';
const message = { name: 'Ana', email: 'ana@example.com', subject: 'A thoughtful introduction ✉', body: 'Hi Ana,\n\n.Unicode: 你好\nThank you.' };
function server(options: { auth?: number; recipient?: number; final?: number; loseFinal?: boolean; malformed?: boolean } = {}) {
  const commands: string[] = []; let controller: ReadableStreamDefaultController<Uint8Array>; let data = false;
  const send = (value: string) => controller.enqueue(new TextEncoder().encode(value));
  const readable = new ReadableStream<Uint8Array>({ start(value) { controller = value; send(options.malformed ? 'BAD GREETING\r\n' : '220 smtp.gmail.com ready\r\n'); } });
  const writable = new WritableStream<Uint8Array>({ write(bytes) {
    const value = new TextDecoder().decode(bytes); commands.push(value);
    if (data) { if (options.loseFinal) controller.close(); else send(`${options.final || 250} queued\r\n`); return; }
    if (value.startsWith('EHLO')) { send('250-smtp.gmail.com\r\n250-AUTH LOGIN PLAIN XOAUTH2\r\n250 SIZE 30000000\r\n'); }
    else if (value.startsWith('AUTH')) send(`${options.auth || 235} auth result\r\n`);
    else if (value.startsWith('MAIL')) send('250 sender ok\r\n');
    else if (value.startsWith('RCPT')) send(`${options.recipient || 250} recipient result\r\n`);
    else if (value === 'DATA\r\n') { data = true; send('354 send content\r\n'); }
  } });
  const dial: Dial = async () => ({ readable, writable, close: async () => { try { controller.close(); } catch { /* Already closed */ } } });
  return { dial, commands };
}
describe('Gmail SMTP protocol', () => {
  it('connect checks authenticate only and do not submit an envelope or content', async () => {
    const fake = server(); expect((await testGmail(fake.dial, 'sender@gmail.com', 'syntheticpassword')).state).toBe('accepted');
    expect(fake.commands).toHaveLength(2); expect(fake.commands.some(value => /MAIL FROM|RCPT TO|^DATA/m.test(value))).toBe(false);
  });
  it('uses fixed authoritative sender/recipient and RFC MIME', async () => {
    const fake = server(); expect((await submitGmail(fake.dial, 'sender@gmail.com', 'syntheticpassword', message, '<abc@gmail.com>')).state).toBe('accepted');
    expect(fake.commands[2]).toBe('MAIL FROM:<sender@gmail.com>\r\n'); expect(fake.commands[3]).toBe('RCPT TO:<ana@example.com>\r\n');
    const content = fake.commands.at(-1)!; expect(content).toContain('Reply-To: sender@gmail.com'); expect(content).toContain('Content-Transfer-Encoding: base64'); expect(content.endsWith('\r\n.\r\n')).toBe(true);
  });
  it('distinguishes pre-DATA rejection, post-DATA loss and known final rejection', async () => {
    for (const options of [{ auth: 535 }, { recipient: 550 }, { final: 550 }, { malformed: true }]) expect((await submitGmail(server(options).dial, 'sender@gmail.com', 'syntheticpassword', message, '<abc@gmail.com>')).state).toBe('failed');
    expect((await submitGmail(server({ loseFinal: true }).dial, 'sender@gmail.com', 'syntheticpassword', message, '<abc@gmail.com>')).state).toBe('unknown');
  });
  it('folds international subjects safely and round-trips UTF-8 body', () => {
    const content = mime('sender@gmail.com', { ...message, subject: '你好世界'.repeat(40) }, '<abc@gmail.com>');
    const [headers, body] = content.split('\r\n\r\n');
    expect(headers.split('\r\n').every(line => line.length < 998)).toBe(true);
    expect(new TextDecoder().decode(Uint8Array.from(atob(body.replace(/\s/g, '')), value => value.charCodeAt(0)))).toBe(message.body.replace(/\n/g, '\r\n'));
  });
  it('never resumes a late connection after the deadline returned', async () => {
    vi.useFakeTimers();
    try {
      const fake = server(); let release!: (value: Awaited<ReturnType<Dial>>) => void;
      const delayed: Dial = () => new Promise(resolve => { release = resolve; });
      const result = submitGmail(delayed, 'sender@gmail.com', 'syntheticpassword', message, '<abc@gmail.com>');
      await vi.advanceTimersByTimeAsync(20001);
      expect((await result).state).toBe('failed');
      release(await fake.dial()); await Promise.resolve(); await Promise.resolve();
      expect(fake.commands).toEqual([]);
    } finally { vi.useRealTimers(); }
  });
});
