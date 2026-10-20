"""Shared legal draft; operator review required before publication."""

PRIVACY = """
# Privacy Policy — operator review required
*Last updated: October 11, 2026*

Mass Outreach is an invite-only job outreach application. Supabase provides
email magic-link authentication, invitations and Postgres persistence. A
configured SMTP service processes approved real message content, recipient
addresses and attachments. Actual From is a project-controlled sender;
Reply-To is your verified invited email. No mailbox reading is implemented.

The database stores account UUID/email, invitations (hashed secrets), plan and
quota data, exact rendered batch content and recipients, submission outcomes,
suppression entries and audit events. Attachments remain in active server
session memory; their filename, size, type and content hash are persisted.
Authentication tokens remain in server session memory. Signing out clears
session data, but does not delete durable database records or provider copies.

Fake test mode performs no network email submission. Generated addresses are
guesses, not verified mailboxes. SMTP acceptance is not evidence of delivery.
Access is checked against database authorization for protected operations.

## Production details still to finalize
- Operator identity and support/deletion contact: [OPERATOR / CONTACT TBD].
- SMTP provider and processing location/retention: [PROVIDER TBD].
- Hosting provider and region: [HOSTING TBD].
- Database, audit, invitation and message retention/deletion schedule:
  [RETENTION DURATIONS AND DELETION PROCESS TBD]. No automated retention job
  is currently implemented.
- Legal basis, applicable jurisdiction and required notices: [LEGAL REVIEW TBD].

Do not publish this draft as a finalized privacy policy until placeholders
are resolved. Users should not upload sensitive material before those
decisions are communicated. There is no implemented inbox access, payment,
phone verification, AI generation, scraping or public sending feature.
"""

TERMS = """
# Terms of Service — operator review required
*Last updated: October 11, 2026*

Mass Outreach prepares and submits individually reviewed job outreach emails
for invited, verified users. Access can be revoked by an administrator.
Plan 1 has a configurable default allowance of 300 accepted real submissions
per UTC day, plus batch and application-wide UTC hourly/daily limits.
Pending/unknown submissions may hold quota conservatively until reconciled.
Fake test submissions do not consume real-send allowance.

You must review exact recipients, content, sender, Reply-To, BCC and attachment
before approval. Generated recipient addresses are unverified guesses.
Use only lawful, relevant outreach and honor do-not-contact requests. Add
requested opt-outs to your suppression list. Suppressions are per user, not
a project-wide unsubscribe service. No purchased or scraped lists, spam,
deception, harassment or unlawful content. You are responsible for applicable
anti-spam rules and any required disclosures or consent.

Sending is session-bound with explicit continuation between recipients. The
app records accepted, failed and unknown outcomes; it cannot guarantee
delivery, inbox placement, replies or jobs. Unknown outcomes are not retried
automatically. Closing the session does not undo an in-flight submission.

Only PDF/DOCX attachments are allowed; file checks are not malware scanning.
This release implements no billing or subscriptions.

Operator/contact, eligibility, jurisdiction, liability terms, retention,
provider acceptable-use rules and dispute procedures: [LEGAL DECISIONS TBD].
This is a draft requiring operator/legal review, not a finalized agreement.
"""
