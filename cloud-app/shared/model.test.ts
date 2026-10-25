import { describe, expect, it } from 'vitest';
import { address, messages, parseContacts, personalize } from './model';
describe('contact import and exact messages', () => {
  it('parses BOM, CRLF, quoted commas, doubled quotes and compound names', () => {
    expect(parseContacts('\uFEFFemail,name\r\na@example.com,"Lee, Ana"\r\nb@example.com,"Jo ""Jay"" Chen"').contacts).toEqual([{ email: 'a@example.com', name: 'Lee, Ana' }, { email: 'b@example.com', name: 'Jo "Jay" Chen' }]);
    expect(parseContacts('first_name,last_name,email\nMary Jane,de la Cruz,Mary@example.com').contacts[0]).toEqual({ email: 'mary@example.com', name: 'Mary Jane de la Cruz' });
  });
  it('deduplicates addresses without collapsing Gmail dot/plus variants', () => {
    const parsed = parseContacts('email,name\nA@example.com,A\na@example.com,B\na+b@example.com,C\na.b@example.com,D');
    expect(parsed.contacts).toHaveLength(3); expect(parsed.warnings).toHaveLength(1);
  });
  it.each(['email,name\na@example.com,"Bad', 'name\nMissing email', 'email,email\na@example.com,b@example.com', 'email,name\na@example.com,A,Extra', 'email,name\nbad,A'])('rejects malformed CSV: %s', value => expect(() => parseContacts(value)).toThrow());
  it('bounds input size, does not silently send more than five contacts', () => {
    expect(() => parseContacts('x'.repeat(262145))).toThrow();
    const parsed = parseContacts('email,name\n' + Array.from({ length: 6 }, (_, i) => `person${i}@example.com,P${i}`).join('\n'));
    expect(parsed.contacts).toHaveLength(6); expect(parsed.warnings[0]).toContain('Select up to 5');
  });
  it('renders only known deterministic template fields', () => {
    expect(personalize('Hello {{first_name}} / {{name}} / {{email}}', { name: 'Ana María Lee', email: 'ana@example.com' })).toBe('Hello Ana / Ana María Lee / ana@example.com');
    expect(() => personalize('{{company}}', { name: '', email: 'a@example.com' })).toThrow();
  });
  it('rejects header injection, invalid addresses and duplicate recipients', () => {
    expect(() => address('a@example.com\r\nBcc:x@y.com')).toThrow(); expect(() => address('a..b@example.com')).toThrow();
    const value = { name: 'Ana', email: 'a@example.com', subject: 'Subject', body: 'Body' };
    expect(() => messages([{ ...value, subject: 'Hello\nBcc: x@y.com' }])).toThrow();
    expect(() => messages([value, value])).toThrow(); expect(() => messages(Array(6).fill(value))).toThrow();
    expect(messages([{ ...value, body: 'Hi\r\nThere' }])[0].body).toBe('Hi\nThere');
  });
});
