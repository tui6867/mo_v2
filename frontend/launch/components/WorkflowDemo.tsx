import { useEffect, useRef, useState } from 'react';
import { BorderBeam } from 'border-beam';
import { content, sampleBody, type Tone } from '../content';
import { Icon, type IconName } from './Icon';
import { useReducedMotion } from './useReducedMotion';

const stepIcons: IconName[] = ['upload', 'shield', 'edit', 'check', 'send'];
const initialDrafts = () => content.demo.recipients.map(person => ({ subject: person.subject, body: sampleBody(person, 'concise') }));
const statusNames = ['Queued', 'Sending', 'Sent', 'Delivered'] as const;

export function WorkflowDemo({ onApply }: { onApply: () => void }) {
  const [step, setStep] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [permissions, setPermissions] = useState({ resume: true, contacts: true });
  const [person, setPerson] = useState(0);
  const [tone, setTone] = useState<Tone>('concise');
  const [drafts, setDrafts] = useState(initialDrafts);
  const [approved, setApproved] = useState(false);
  const [reviewed, setReviewed] = useState<boolean[]>([false, false, false]);
  const [tick, setTick] = useState(0);
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const reduced = useReducedMotion();
  const title = useRef<HTMLHeadingElement>(null);
  const recipient = content.demo.recipients[person];
  const draft = drafts[person];
  const ready = loaded && permissions.resume && permissions.contacts;
  const complete = tick >= 5;
  const allReviewed = reviewed.every(Boolean);

  useEffect(() => {
    if (!running || paused || document.hidden) return;
    const timer = window.setTimeout(() => {
      if (tick >= 4) { setTick(5); setRunning(false); }
      else setTick(value => value + 1);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [running, paused, tick]);

  // Background tabs do not consume the simulation or leave a hidden animation running.
  useEffect(() => {
    const stop = () => { if (document.hidden) setPaused(true); };
    document.addEventListener('visibilitychange', stop);
    return () => document.removeEventListener('visibilitychange', stop);
  }, []);

  // Reduced motion shows the final simulated state immediately; controls stay usable.
  useEffect(() => {
    if (reduced && running) { setTick(5); setRunning(false); }
  }, [reduced, running]);

  function go(next: number) {
    if (next === 3) setReviewed(items => items.map((value, index) => index === person ? true : value));
    setStep(next);
    window.requestAnimationFrame(() => title.current?.focus({ preventScroll: true }));
  }
  function reset() {
    setRunning(false); setPaused(false); setTick(0); setApproved(false); setReviewed([false, false, false]); go(0);
  }
  function updateDraft(key: 'subject' | 'body', value: string) {
    setApproved(false);
    setTick(0);
    setReviewed(items => items.map((value, index) => index === person ? false : value));
    setDrafts(items => items.map((item, index) => index === person ? { ...item, [key]: value } : item));
  }
  function setClosing(next: Tone) {
    if (next === tone) return;
    setTone(next); setApproved(false); setReviewed([false, false, false]); setTick(0);
    // Change only the closing, preserving the visitor's opening and other edits.
    setDrafts(items => items.map(item => ({ ...item, body: item.body.replace(content.demo.closings[tone], content.demo.closings[next]) })));
  }
  function startSimulation() {
    if (!ready || !approved || !allReviewed) return;
    setPaused(false); setTick(reduced ? 5 : 0); setRunning(!reduced); go(4);
  }
  function status(index: number) {
    return statusNames[Math.min(3, Math.max(0, tick - index + 1))];
  }

  return <section id="workflow" className="workflow-section section-shell" aria-labelledby="workflow-heading">
    <div className="section-intro flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div><p className="section-index">01 / THE WORKFLOW</p><h2 id="workflow-heading">{content.demo.title}</h2></div>
      <p className="intro-aside">{content.demo.description}<br /><span>This is a product-vision demo.</span></p>
    </div>
    <div className="workflow-shell glass-panel">
      <div className="workspace-bar flex items-center justify-between gap-3">
        <span className="workspace-name"><span className="workspace-square" aria-hidden="true">m</span> Your outreach workspace <span className="concept-badge">CONCEPT</span></span>
        <button className="icon-button replay-button" type="button" aria-label="Restart demo" onClick={reset}><Icon name="replay" /><span>Restart demo</span></button>
      </div>
      <div className="workspace-layout">
        <nav className="workflow-nav" aria-label="Demo steps">
          {content.demo.stepLabels.map((label, index) => <button key={label} type="button" aria-current={step === index ? 'step' : undefined} disabled={running || (index === 4 && !complete)} onClick={() => go(index)}>
            <span className="step-icon"><Icon name={stepIcons[index]} /></span><span className="step-label">{label}</span><span className="step-number" aria-hidden="true">0{index + 1}</span>
          </button>)}
          <div className="sidebar-note"><Icon name="lock" /><p>Your decisions.<br />Every step of the way.</p></div>
        </nav>
        <div className="workspace-main">
          <div className="stage-heading"><div><p className="stage-kicker">STEP 0{step + 1} <span>/ 05</span></p><h3 ref={title} tabIndex={-1}>{content.demo.steps[step]}</h3></div><span className="sample-label">SAMPLE WORKFLOW</span></div>
          <div className="stage-content" key={step}>
            {step === 0 && <div className="import-layout">
              <div>
                <p className="stage-description">Start with your story and the people you want to meet. We’ll use fictional files for this walkthrough.</p>
                <button className={`sample-dropzone ${loaded ? 'is-loaded' : ''}`} type="button" onClick={() => setLoaded(true)} aria-describedby="sample-file-note">
                  <span className="upload-symbol"><Icon name={loaded ? 'check' : 'upload'} /></span>
                  <strong>{loaded ? 'Sample files ready' : 'Bring your experience in.'}</strong>
                  <span>{loaded ? 'Fictional resume and contact list loaded' : 'Click to load a sample resume + contacts'}</span>
                  <span className="dropzone-formats">PDF + CSV · DEMO FILES ONLY</span>
                </button>
                <p id="sample-file-note" className="field-note">No file picker. No real uploads. Nothing leaves this browser.</p>
              </div>
              <div className="import-context"><p className="context-title">A little context goes a long way.</p><div className="file-stack">
                {content.demo.files.map(file => <div className={`file-item ${loaded ? 'file-ready' : ''}`} key={file.name}><span className="file-extension">{file.type}</span><div><strong>{file.name}</strong><small>{file.detail}</small></div>{loaded && <Icon name="check" />}</div>)}
              </div><div className="context-thread"><span className="thread-node" /><p>Your experience</p><span className="thread-connector" /><span className="thread-node hollow" /><p>Your next conversation</p></div></div>
            </div>}
            {step === 1 && <div>
              <p className="stage-description">Helpful context, with boundaries. Explore the permissions model we’re designing—without connecting an account.</p>
              <div className="permission-list">
                <label><span className="permission-icon"><Icon name="file" /></span><span><strong>Use the sample resume</strong><small>Bring relevant experience into each draft.</small></span><input type="checkbox" checked={permissions.resume} onChange={event => { setPermissions({ ...permissions, resume: event.target.checked }); setApproved(false); }} /></label>
                <label><span className="permission-icon"><Icon name="link" /></span><span><strong>Use the sample contacts</strong><small>Personalize for the people you choose.</small></span><input type="checkbox" checked={permissions.contacts} onChange={event => { setPermissions({ ...permissions, contacts: event.target.checked }); setApproved(false); }} /></label>
                <div className="permission-off"><span className="permission-icon"><Icon name="shield" /></span><span><strong>No inbox access in this demo</strong><small>No mailbox connection or real permissions requested.</small></span><span className="off-label">OFF</span></div>
              </div>
              <p className="permission-footnote"><Icon name="lock" /> Simulated choices only. These are not OAuth permissions.</p>
            </div>}
            {step === 2 && <div className="compose-layout">
              <div className="compose-editor">
                <div className="recipient-tabs" aria-label="Choose a fictional recipient">{content.demo.recipients.map((item, index) => <button key={item.name} type="button" aria-pressed={index === person} onClick={() => setPerson(index)}>{item.name.split(' ')[0]}</button>)}</div>
                <div className="tone-picker"><span>Closing tone</span><button type="button" aria-pressed={tone === 'concise'} onClick={() => setClosing('concise')}>Concise</button><button type="button" aria-pressed={tone === 'warm'} onClick={() => setClosing('warm')}>Warm</button></div>
                <label className="editor-field"><span>Subject</span><input aria-label="Sample email subject" value={draft.subject} maxLength={200} onChange={event => updateDraft('subject', event.target.value)} /></label>
                <label className="editor-field body-field"><span className="sr-only">Sample email body</span><textarea aria-label="Sample email body" rows={9} value={draft.body} maxLength={3000} onChange={event => updateDraft('body', event.target.value)} /></label>
              </div>
              <aside className="relevance-context"><p className="context-title">THE SHARED THREAD</p><div className="person-avatar">{recipient.initials}</div><h4>{recipient.name}</h4><p>{recipient.role}<br />{recipient.company}</p><div className="context-connection"><Icon name="link" /><span>{recipient.connection}</span></div><p className="field-note">Prewritten sample, not AI output. Switch people, change the tone, or edit the words.</p></aside>
            </div>}
            {step === 3 && <div className="review-layout">
              <div className="email-preview"><div className="email-header"><Icon name="mail" /><strong>Your introduction, in full.</strong></div><dl><div><dt>From</dt><dd>{content.demo.senderAddress}</dd></div><div><dt>To</dt><dd>{recipient.email}</dd></div><div><dt>Subject</dt><dd>{draft.subject}</dd></div></dl><pre>{draft.body}</pre></div>
              <aside className="review-controls"><span className="review-count">03</span><h4>People, not a mailing list.</h4><p>Open all three fictional drafts before running the simulation. {reviewed.filter(Boolean).length}/3 reviewed.</p><div className="review-recipient-list">{content.demo.recipients.map((item, index) => <button type="button" key={item.name} aria-pressed={person === index} onClick={() => { setPerson(index); setReviewed(items => items.map((value, current) => current === index ? true : value)); }}><span>{item.name}</span><Icon name={reviewed[index] ? 'check' : 'arrow'} /></button>)}</div>
                <label className="approval-check"><input type="checkbox" checked={approved} disabled={!allReviewed} onChange={event => setApproved(event.target.checked)} /><span>I approve these sample messages for a simulated send.</span></label>{!ready && <p className="field-note">Load the sample files and enable both sample permissions first.</p>}
              </aside>
            </div>}
            {step === 4 && <div className="delivery-layout">
              <div className="delivery-summary"><span className={`delivery-emblem ${complete ? 'complete' : ''}`}><Icon name={complete ? 'check' : 'send'} /></span><h4>{complete ? 'An introduction. A new possibility.' : paused ? 'Simulation paused.' : 'From your story to their inbox.'}</h4><p>{complete ? 'That’s the experience we’re working toward. Personal, considered, and in your control.' : 'A visual illustration of what sending and delivery events could look like.'}</p></div>
              <div className="delivery-route" aria-hidden="true"><span className="route-end"><Icon name="send" /><small>Your workspace</small></span><div className="route-track"><span className="route-progress" style={{ transform: `scaleX(${tick / 5})` }} /><span className="route-packet" style={{ transform: `translateX(${tick * 20}%)` }}><Icon name="mail" /></span></div><span className="route-end"><Icon name="mail" /><small>Sample inbox</small></span></div>
              <div className="delivery-stream" role="status" aria-live="polite" aria-atomic="true">{content.demo.recipients.map((item, index) => <div className="delivery-row" key={item.name}><span className="delivery-avatar">{item.initials}</span><div><strong>{item.name}</strong><small>{item.company}</small></div><span className={`delivery-status status-${status(index).toLowerCase()}`}><span>{status(index) === 'Delivered' && <Icon name="check" />}{status(index)}</span><small>simulated</small></span></div>)}</div>
              <p className="delivery-disclosure">All statuses are simulated. “Sent” and “Delivered” are not real provider events. Actual SMTP acceptance is not proof of delivery.</p>
            </div>}
          </div>
          <div className="stage-footer flex flex-wrap items-center justify-between gap-3">
            <span className="stage-hint">{step === 0 ? 'Your experience is the starting point.' : step === 1 ? 'You choose what the workflow can use.' : step === 2 ? 'Every recipient gets their own words.' : step === 3 ? 'Nothing moves without your approval.' : 'A concept you can help bring to life.'}</span>
            <div className="flex items-center gap-3">
              {step > 0 && step < 4 && <button className="text-button" type="button" onClick={() => go(step - 1)}>Back</button>}
              {step < 3 && <button className="button button-small" type="button" disabled={(step === 0 && !loaded) || (step === 1 && !ready) || (step === 2 && drafts.some(item => !item.subject.trim() || !item.body.trim()))} onClick={() => go(step + 1)}>{step === 0 ? 'Set permissions' : step === 1 ? 'Make it personal' : 'Review messages'}<Icon name="arrow" /></button>}
              {step === 3 && <button className="button button-small" type="button" disabled={!approved || !ready || !allReviewed || drafts.some(item => !item.subject.trim() || !item.body.trim())} onClick={startSimulation}>Simulate sending<Icon name="send" /></button>}
              {step === 4 && running && <button className="button button-small" type="button" onClick={() => setPaused(value => !value)}><Icon name={paused ? 'play' : 'pause'} />{paused ? 'Resume' : 'Pause'} simulation</button>}
              {step === 4 && complete && <button className="button button-small" type="button" onClick={onApply}>Be part of it<Icon name="diagonal" /></button>}
            </div>
          </div>
        </div>
      </div>
      <BorderBeam size="line" theme="dark" colorVariant="ocean" staticColors strength={0.45} duration={3.2} active={running && !paused && !reduced} className="workspace-beam" borderRadius={0}><div className="workspace-disclosure"><span className="disclosure-dot" />{content.demo.disclosure}</div></BorderBeam>
    </div>
    <details className="demo-transcript"><summary>Read the walkthrough without interacting <Icon name="plus" /></summary><p>1. Load a fictional resume and three fictional contacts. 2. Choose which sample context to use; no real permissions are granted. 3. Edit each prewritten introduction and its tone. 4. Review the three messages and explicitly approve the sample batch. 5. Run a browser-only simulation of sending, sent, and delivered states. No network request, upload, AI generation, or actual sending occurs.</p></details>
  </section>;
}
