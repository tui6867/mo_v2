/** EDIT HERE: marketing copy and fictional examples. No credentials or real resumes. */
export const content = {
  brand: 'Mass Outreach',
  hero: {
    label: 'For the next generation of job seekers',
    headingLead: 'The future of',
    headingAccent: 'networking.',
    supporting: 'Your experience. The right people. A better first conversation.',
    description: 'We’re building a more intentional way to turn your experience into personal introductions. Less busywork. More reasons to connect.',
    cta: 'Apply for early access',
  },
  demo: {
    title: 'Your next chapter starts with an introduction.',
    description: 'Step inside the workflow we’re building. Make it yours.',
    disclosure: 'Interactive concept · Fictional data · No real sending',
    steps: ['Your starting point', 'Your permissions', 'Make it personal', 'Review & approve', 'Follow the journey'],
    stepLabels: ['Import', 'Permissions', 'Personalize', 'Review', 'Track'],
    sender: 'Alex Morgan',
    senderAddress: 'alex@candidate.example',
    files: [
      { name: 'alex-morgan-resume.pdf', detail: 'Sample resume · Product & design', type: 'PDF' },
      { name: 'people-to-connect.csv', detail: '3 fictional contacts · Curated by you', type: 'CSV' },
    ],
    recipients: [
      { name: 'Jordan Lee', initials: 'JL', role: 'Product Lead', company: 'Forma Labs', email: 'jordan@forma.example', work: 'Making onboarding feel human', connection: 'Your onboarding redesign → Jordan’s product work', subject: 'A shared interest in thoughtful onboarding', opening: 'Your work on making onboarding more human at Forma Labs caught my attention. In my recent product project, I redesigned a first-run experience with a similar goal: helping people feel confident from the first click.' },
      { name: 'Sam Rivera', initials: 'SR', role: 'Design Engineer', company: 'Northstar Studio', email: 'sam@northstar.example', work: 'Bridging design and engineering', connection: 'Your interactive portfolio → Sam’s design systems work', subject: 'Where thoughtful design meets engineering', opening: 'I enjoyed reading about your design systems work at Northstar Studio. Building my interactive portfolio gave me a real appreciation for the space between a strong design idea and a polished, accessible implementation.' },
      { name: 'Casey Chen', initials: 'CC', role: 'Early Careers Lead', company: 'Orbit Works', email: 'casey@orbit.example', work: 'Opening doors for emerging talent', connection: 'Your project-led experience → Casey’s early-career program', subject: 'An introduction beyond my application', opening: 'Your focus on emerging talent at Orbit Works stood out to me. My experience has grown through hands-on product projects, and I’d love to learn how that kind of project-led background could contribute to your team.' },
    ],
    signature: 'Thanks for your time,\nAlex',
    closings: {
      concise: 'Would you be open to a brief conversation about your team’s approach?',
      warm: 'I’d love to hear more about what you’re building, and share a little of my work if it’s relevant. Would you be open to connecting?',
    },
  },
  capabilities: [
    { id: 'relevance', number: '01', title: 'An actual reason to reach out.', short: 'Context, not just a first name.', description: 'The vision: connect the projects on your resume to the work someone actually does. Surface the shared thread, then help you write an introduction worth reading.', input: 'Your experience', inputDetail: 'Onboarding redesign · UX research · Prototyping', output: 'Their work', outputDetail: 'Jordan Lee · Human-centered product onboarding', result: 'A shared interest in helping new users find their feet.', tag: 'Resume-to-recipient relevance' },
    { id: 'voice', number: '02', title: 'Assisted by AI. Still entirely you.', short: 'A different introduction for every person.', description: 'The vision: AI-assisted drafts grounded in your real experience, with tone, context, and wording you can change. Your story stays yours. Every message stays subject to your review.', input: 'Your direction', inputDetail: 'Warm tone · A specific project · A genuine question', output: 'An individual draft', outputDetail: 'A relevant opening, not a mail-merge greeting', result: 'Review the connection. Refine the words. Approve the message.', tag: 'Human-controlled personalization' },
    { id: 'people', number: '03', title: 'Look beyond the apply button.', short: 'Find the people behind the opportunity.', description: 'The vision: explore relevant team members associated with a job posting, understand their work, and choose who to contact. Suggested contacts would need source evidence and your review—not guessed certainty.', input: 'A role you care about', inputDetail: 'Associate Product Designer · Fictional example', output: 'Relevant people to explore', outputDetail: 'Product team · Design team · Early careers', result: 'People with context. A path to a more thoughtful introduction.', tag: 'Job-to-team discovery' },
  ],
  proof: {
    heading: 'An ambitious vision. A working foundation.',
    description: 'We’re early, and we’ll be precise about what that means.',
    working: ['Verified, invite-only prototype access', 'Compose, preview, and explicit approval', 'Controlled SMTP submission and private capture', 'Durable submission history'],
    planned: ['AI-assisted, person-specific drafts', 'Resume-to-recipient context matching', 'Job-posting contact discovery', 'Provider-backed delivery events'],
    note: 'The current prototype is a controlled development pilot, not a public outreach service. SMTP acceptance does not establish inbox delivery. The concept above is not connected to that prototype.',
  },
  faq: [
    { question: 'Who is Mass Outreach for?', answer: 'We’re designing for students, recent graduates, and early-career job seekers who want to make thoughtful professional connections around the work they care about.' },
    { question: 'Is this a working product or a concept?', answer: 'There is a working, invite-only mail pilot with composition, preview, approval, and controlled submission. This launch page demonstrates a broader product vision. AI assistance, relevance matching, contact discovery, and delivery tracking shown here are planned—not available features.' },
    { question: 'Does the interactive demo upload files or send email?', answer: 'No. All files, people, permission settings, messages, and delivery events are fictional examples running in your browser. No resume is uploaded, no mailbox is connected, and no email is sent. “Delivered” is a simulated visual state, not a delivery claim.' },
    { question: 'Will AI send messages without my approval?', answer: 'That is not the direction we’re building toward. Our intended workflow keeps drafting, review, and approval separate. AI assistance is planned, and the goal is to support your judgment—not quietly send on your behalf.' },
    { question: 'What happens when I apply for early access?', answer: 'For this template, you can preview the application flow only. Nothing is submitted or stored, and you are not added to a waitlist. Before real collection opens, we’ll connect a protected waitlist service and publish the appropriate privacy and contact information.' },
    { question: 'When will access open, and what will it cost?', answer: 'We haven’t announced a public launch date or pricing. Early access will be deliberate and limited while we evaluate the workflow, provider requirements, and reliability. This page does not promise access, results, or a response timeline.' },
  ],
  waitlist: {
    title: 'Be part of what comes next.',
    description: 'Help shape a more thoughtful way to connect. Tell us where you want to go.',
    disclosure: 'Template preview. Applications are not being collected yet.',
    consent: 'When applications open, I’d like to hear about early access to Mass Outreach.',
    success: 'Application preview complete.',
    successDetail: 'Nothing was submitted or saved. You have not been added to a waitlist. This is the experience we’re preparing for launch.',
  },
};

export type Recipient = typeof content.demo.recipients[number];
export type Tone = keyof typeof content.demo.closings;

export function sampleBody(recipient: Recipient, tone: Tone) {
  return `Hi ${recipient.name.split(' ')[0]},\n\n${recipient.opening}\n\n${content.demo.closings[tone]}\n\n${content.demo.signature}`;
}
