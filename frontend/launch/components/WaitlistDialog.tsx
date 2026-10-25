import { useEffect, useRef, useState, type FormEvent } from 'react';
import { content } from '../content';
import { previewWaitlist, type WaitlistGateway, type WaitlistResult } from '../services/waitlist';
import { BrandMark, Icon } from './Icon';

export function WaitlistDialog({ open, onClose, gateway = previewWaitlist }: { open: boolean; onClose: () => void; gateway?: WaitlistGateway }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const [email, setEmail] = useState('');
  const [goal, setGoal] = useState('');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<WaitlistResult | null>(null);
  const [error, setError] = useState('');
  const request = useRef(false);
  const lifecycle = useRef(0);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open) {
      element.showModal();
      const overflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = overflow; element.close(); };
    }
  }, [open]);

  useEffect(() => { if (result) heading.current?.focus(); }, [result]);

  function close() {
    lifecycle.current += 1;
    request.current = false;
    setEmail(''); setGoal(''); setConsent(false); setResult(null); setError(''); setBusy(false);
    onClose();
  }

  async function apply(event: FormEvent) {
    event.preventDefault();
    if (request.current) return;
    request.current = true;
    const version = lifecycle.current;
    setBusy(true); setError('');
    try {
      const outcome = await gateway.apply({ email: email.trim(), goal: goal.trim(), consent });
      if (version !== lifecycle.current) return;
      setResult(outcome);
      setEmail(''); setGoal(''); setConsent(false);
    } catch {
      if (version === lifecycle.current) setError('We couldn’t complete this preview. Check the fields and try again.');
    } finally {
      if (version === lifecycle.current) { request.current = false; setBusy(false); }
    }
  }

  return <dialog ref={dialog} className="waitlist-dialog" aria-labelledby="waitlist-title" aria-describedby="waitlist-disclosure" onKeyDown={event => {
    if (event.key !== 'Tab') return;
    const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), a[href]')].filter(element => element.getClientRects().length > 0);
    const first = controls[0];
    const last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }} onCancel={event => { event.preventDefault(); close(); }} onClick={event => { if (event.target === dialog.current) { const bounds = dialog.current.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close(); } }}>
    <div className="dialog-inner">
      <div className="flex items-center justify-between"><span className="dialog-brand"><BrandMark />{content.brand}</span><button className="icon-button" type="button" aria-label="Close application" onClick={close}><Icon name="close" /></button></div>
      <div className="dialog-heading"><p className="section-index">EARLY ACCESS / APPLICATION</p><h2 ref={heading} tabIndex={-1} id="waitlist-title">{result ? content.waitlist.success : content.waitlist.title}</h2><p>{result ? content.waitlist.successDetail : content.waitlist.description}</p></div>
      <p className="preview-notice" id="waitlist-disclosure"><Icon name="shield" />{content.waitlist.disclosure}</p>
      {result ? <div className="application-result" role="status"><span className="result-check"><Icon name="check" /></span><p>Preview only. No signup, no email, no storage.</p><button className="button" type="button" onClick={close}>Back to exploring<Icon name="arrow" /></button></div> : <form onSubmit={apply} aria-busy={busy}>
        <label className="form-field" htmlFor="waitlist-email">Your email<input id="waitlist-email" type="email" required maxLength={254} autoComplete="email" placeholder="you@your-next-chapter.com" value={email} disabled={busy} onChange={event => setEmail(event.target.value)} /></label>
        <label className="form-field" htmlFor="waitlist-goal">Where do you want to go? <span>Optional</span><textarea id="waitlist-goal" rows={3} maxLength={300} placeholder="A first design role. A career pivot. A team you believe in." value={goal} disabled={busy} onChange={event => setGoal(event.target.value)} /></label>
        <label className="consent-field"><input type="checkbox" required checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} /><span>{content.waitlist.consent}</span></label>
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="button application-button" type="submit" disabled={busy}>{busy ? 'Preparing preview…' : 'Preview my application'}<Icon name="diagonal" /></button>
        <p className="field-note">For this preview, use a fictional email. Form values are kept only while this drawer is open and cleared when it closes. No analytics or tracking.</p>
      </form>}
      <p className="dialog-bottom">A better introduction can change what comes next.</p>
    </div>
  </dialog>;
}
