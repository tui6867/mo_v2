import { useState } from 'react';
import { content } from './content';
import { BrandMark, Icon } from './components/Icon';
import { WorkflowDemo } from './components/WorkflowDemo';
import { WaitlistDialog } from './components/WaitlistDialog';

export function LaunchPage() {
  const [applicationOpen, setApplicationOpen] = useState(false);
  const [capability, setCapability] = useState(0);
  const selected = content.capabilities[capability];
  const apply = () => setApplicationOpen(true);

  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header section-shell flex items-center justify-between gap-4">
      <a className="brand" href="#" aria-label="Mass Outreach home"><BrandMark /><span>{content.brand}</span></a>
      <nav className="desktop-nav flex items-center gap-8" aria-label="Main navigation"><a href="#workflow">The workflow</a><a href="#vision">The vision</a><a href="#questions">Questions</a></nav>
      <button type="button" className="header-apply" onClick={apply}>Get early access<Icon name="diagonal" /></button>
    </header>
    <main id="main">
      <section className="hero section-shell" aria-labelledby="hero-title">
        <div className="hero-topline"><span className="hero-signal" aria-hidden="true" /><span>{content.hero.label}</span><span className="hero-edition">PRODUCT VISION / EARLY ACCESS</span></div>
        <div className="hero-grid">
          <div className="hero-headline"><h1 id="hero-title">{content.hero.headingLead}<br /><span>{content.hero.headingAccent}</span></h1></div>
          <div className="hero-support"><p className="hero-supporting">{content.hero.supporting}</p><p className="hero-description">{content.hero.description}</p><button type="button" className="button hero-cta" onClick={apply}>{content.hero.cta}<Icon name="diagonal" /></button><p className="hero-footnote">Help shape what comes next. <span>Preview application.</span></p></div>
        </div>
        <div className="hero-baseline flex items-center justify-between"><a className="explore-link" href="#workflow"><span className="explore-icon"><Icon name="arrow" /></span>Don’t just read about it. Try the idea.</a><span className="hero-caption">PERSONAL BY DESIGN. HUMAN BY DEFAULT.</span></div>
      </section>

      <WorkflowDemo onApply={apply} />

      <section className="vision-section section-shell" id="vision" aria-labelledby="vision-title">
        <div className="section-intro"><p className="section-index">02 / THE BIGGER PICTURE</p><h2 id="vision-title">Not just another email.<br /><span>A reason to connect.</span></h2><p className="vision-intro">The best introductions start with something real. Here’s the deeper context we’re designing for.</p></div>
        <div className="vision-grid">
          <div className="vision-options" aria-label="Explore planned capabilities">{content.capabilities.map((item, index) => <button className={index === capability ? 'is-active' : ''} key={item.id} type="button" aria-pressed={index === capability} aria-controls="capability-detail" onClick={() => setCapability(index)}><span className="vision-number">{item.number}</span><span><strong>{item.title}</strong><small>{item.short}</small></span><Icon name="diagonal" /></button>)}</div>
          <div className="capability-panel glass-panel" id="capability-detail" aria-live="polite" aria-atomic="true">
            <div className="flex items-center justify-between gap-3"><span className="context-title">{selected.tag}</span><span className="concept-badge">PRODUCT VISION</span></div>
            <div className="relevance-map" key={selected.id}><div className="map-endpoint"><span className="map-node" /><div><span>{selected.input}</span><strong>{selected.inputDetail}</strong></div></div><div className="map-path"><span className="path-label">FIND THE SHARED THREAD</span><Icon name="link" /></div><div className="map-endpoint"><span className="map-node outlined" /><div><span>{selected.output}</span><strong>{selected.outputDetail}</strong></div></div><p className="map-result">“{selected.result}”</p></div>
            <p className="capability-description">{selected.description}</p>
          </div>
        </div>
        <p className="vision-disclaimer">These are planned capabilities, illustrated with prewritten examples—not live AI, contact discovery, or verified matching.</p>
      </section>

      <section className="foundation-section section-shell" id="foundation" aria-labelledby="foundation-title">
        <div className="foundation-intro"><p className="section-index">03 / BUILT WITH INTENTION</p><h2 id="foundation-title">{content.proof.heading}</h2><p>{content.proof.description}</p></div>
        <div className="foundation-grid"><div><h3><span className="foundation-dot" />Working in the controlled pilot</h3><ul>{content.proof.working.map(item => <li key={item}><Icon name="check" />{item}</li>)}</ul></div><div><h3><span className="foundation-dot outlined" />Where we’re heading</h3><ul>{content.proof.planned.map(item => <li key={item}><Icon name="plus" />{item}</li>)}</ul></div></div>
        <p className="foundation-note"><Icon name="shield" />{content.proof.note}</p>
      </section>

      <section className="faq-section section-shell" id="questions" aria-labelledby="faq-title"><div><p className="section-index">04 / A FEW GOOD QUESTIONS</p><h2 id="faq-title">A little clarity<br />goes a long way.</h2><p>We’d rather be specific<br /> than make a bigger promise.</p></div><div className="faq-list">{content.faq.map(item => <details key={item.question}><summary>{item.question}<Icon name="plus" /></summary><p>{item.answer}</p></details>)}</div></section>

      <section className="closing-section section-shell" aria-labelledby="closing-title"><div className="closing-rule"><BrandMark /><span>YOUR NEXT CHAPTER ISN’T A FORM FIELD.</span></div><div className="closing-grid"><h2 id="closing-title">Good things start<br />with <span>“hello.”</span></h2><div><p>Let’s build a better way to make the first move.</p><button className="button" type="button" onClick={apply}>{content.hero.cta}<Icon name="diagonal" /></button><span className="closing-note">Waitlist flow preview. No applications collected yet.</span></div></div></section>
    </main>
    <footer className="site-footer section-shell"><a className="brand" href="#"><BrandMark /><span>{content.brand}</span></a><p>Thoughtful outreach. Real possibility.</p><span>© 2026 Mass Outreach</span><button type="button" className="text-button" onClick={apply}>Preview & data notice<Icon name="diagonal" /></button></footer>
    <WaitlistDialog open={applicationOpen} onClose={() => setApplicationOpen(false)} />
  </>;
}
