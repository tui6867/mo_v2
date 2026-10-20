# Mass Outreach — project context

Prepared: October 11, 2026.

## Product objective

Build a dependable, invite-only product for job seekers to prepare,
review, and send personalized outreach about specific job openings.

Current owner decisions:
- The initial audience is job seekers.
- Access is through individual invitations tied to approved email
  addresses.
- Sending will use a non-Google email provider.
- Google authentication, Gmail connections, and Google OAuth application
  verification are not required for the current phase.
- Stripe connections, subscriptions, paid plans, and billing-based trials
  are not required for the current phase.
- Dependencies and tools should be added only when their benefits exceed
  complexity, maintenance, and effects on usability or efficiency.

The sending provider, authentication method, and sender identity model
have not yet been selected. Do not assume messages will come from users'
personal mailboxes.

This document defines the intended direction. It does not claim the
existing application already implements the pivot.

## Current scope

Included:
- Individual invitations bound to approved email addresses.
- Authentication that verifies control of the invited address.
- Restricted access to application data and sending actions.
- Manual and CSV recipient input.
- Preservation of explicit email addresses.
- Candidate address generation using a chosen organization format.
- Template personalization and optional resume attachments.
- Final recipient and message review.
- Explicit approval before sending.
- Sending through a selected non-Google provider.
- Accurate per-recipient outcomes and exportable send logs.
- Operational sending limits independent of billing.

Deferred or outside the agreed MVP:
- Google sign-in, Gmail authorization, and Google verification.
- Stripe payments, subscriptions, billing entitlements, and paid trials.
- Phone verification unless separately justified and approved.
- Public self-service registration.
- A frontend rewrite.
- Inbox reading, scraping, CRM features, AI-generated messages, and
  automated follow-ups.

Invite-only access does not remove the need for secure authentication,
privacy controls, or reliable sending behavior.

## Intended workflow

1. Receive an individual invitation for an approved email address.
2. Verify control of that address and establish an authenticated session.
3. Enter a job URL, company, job title, and sender details.
4. Add recipients manually or from CSV.
5. Preserve explicit email addresses where available.
6. Otherwise generate candidate addresses using a selected organization
   format, such as flast@company.com.
7. Personalize a template and optionally attach a resume.
8. Review the final recipients, sender details, and rendered messages.
9. Explicitly approve the exact batch to be sent.
10. Send through the configured non-Google provider.
11. Display per-recipient outcomes and allow send-log export.

Generated addresses are guesses, not verified mailboxes.
An address such as jsmith@company.com cannot establish a full first name.

Later, the product may infer formats or names from examples.
That feature's exact inputs and outputs have not been agreed.

## Invitation and authentication requirements

- Bind each invitation to an approved email address.
- Verify control of that address before granting access.
- Do not treat knowledge of an approved address as authentication.
- Enforce access checks on protected data and actions, including sending.
- Make invitations expiring, revocable, and single-use on redemption.
- Prevent redemption by a different authenticated identity.
- Support revocation of an existing user's access.
- Restrict invitation issuance and access administration to authorized
  administrators.
- Keep invitation secrets and authentication credentials out of logs.
- Use stable internal user identifiers for ownership and send records.

The authentication mechanism is undecided. An existing identity service
or passwordless flow may be appropriate; do not invent a custom
authentication system without evaluating maintained options.

Invitation or login email delivery is distinct from outreach sending,
even if both eventually use the same provider.

## Sending provider and sender identity

Before implementing live sending, decide:
- Which non-Google provider will send messages?
- Will messages come from user-connected mailboxes or a project-controlled
  sending domain?
- Where should recipient replies go?
- What sender/domain verification and authentication does the provider
  require?
- What quotas, acceptable-use requirements, and delivery-status
  capabilities apply?

Use only sender identities the application is authorized to use.
If a project-controlled domain is selected, clearly show the From and
Reply-To details before approval.

Keep provider-specific behavior behind a service adapter.

Distinguish:
- Not attempted.
- Submission in progress.
- Accepted by the provider.
- Definitely failed.
- Unknown outcome.

Provider acceptance is not proof of delivery.
Report delivered, bounced, or other later states only when supported by
actual provider evidence.

Do not promise exactly-once delivery. A timeout after provider acceptance
can leave an unknown outcome; do not blindly retry.

## Sending provider direction

Prefer an open-source or privacy-friendly email solution.
Choose the simplest dependable option after evaluating maintenance,
deliverability, data retention, and cost.

Start with a provider-independent SMTP adapter so the application can
use a hosted SMTP service or a self-hosted mail server without changing
recipient and template logic.

Open-source software and SMTP do not by themselves guarantee privacy.
Evaluate who processes message content, what they retain, and how
credentials and logs are protected.

Self-hosting is optional, not an MVP requirement.

Proposed initial sender model:
- Use a verified project-controlled sending domain.
- Clearly display the From address before sending.
- Set Reply-To to the invited user's verified email address.
- Do not imply that messages were sent from the user's personal mailbox.

The exact service remains an implementation decision.
Google and Stripe connections remain outside current scope.

## Current implementation — historical baseline

Previously reviewed application directory: outreach-desk-main/

- app.py: Streamlit UI, configuration, custom Google OAuth, recipient
  parsing, templates, Gmail requests, sending loop, and billing UI.
  Previously reported as 806 lines.
- billing.py: Supabase account/trial storage, Stripe subscriptions,
  and optional Twilio phone verification.
- legal.py: shared privacy policy and terms, plus Streamlit pages.
- build_site.py: generates static legal HTML.
- patch_streamlit_html.py: modifies installed Streamlit index.html.
- requirements.txt: Streamlit, pandas, and requests with open-ended
  versions.
- SETUP.md and GOOGLE_VERIFICATION.md: setup/review instructions.

These describe the previous implementation, not the target architecture.

Previous coverage reported site/, BILLING_SETUP.md,
secrets.toml.example, tests/, and .github/ missing.
Recheck the filesystem before concluding they are absent.

Documented hosting:
- Application: https://mass-outreach.com
- Public homepage/legal pages: https://www.mass-outreach.com
- Render and Cloudflare Pages are mentioned.

Actual deployment, ownership, and configuration were not verified.

## Evidence and completed work

The previous audit was static source inspection through codebase-memory.
Terminal commands did not complete.
No successful test run, live deployment check, or integration test was
performed. Graph freshness warnings require current-source verification.

The audit and repository research did not implement fixes or install
recommended dependencies. Do not inherit a claim that those tasks are
done.

Existing foundations to preserve where verified:
- Test mode enabled by default.
- Message preview and explicit send confirmation.
- Escaped preview content.
- Credentials loaded from configuration.

The prior Gmail send-only scope is historical context, not a current
integration requirement.

## Configuration and existing services

The invite-only application must not require Google, Stripe, or Twilio
credentials to start or operate.

Remove those integrations from the active access and sending paths.
Missing billing configuration must never result in unrestricted access.

Required configuration will depend on the chosen:
- Invitation and authentication mechanism.
- Email provider and authorized sender identities.
- Persistence layer.
- Operational limits and deployment environment.

Document exact setting names after these choices are made.
Never put actual secrets in this document.

Supabase may be retained if it remains useful for authentication,
invitations, or durable send records. Invite-only access does not itself
require replacing the database.

Previously described tables:
- users(email primary key, phone_hash)
- phones(phone_hash primary key, trial_email, trial_sends_used)

Production schemas, constraints, policies, and migrations were not
checked. These legacy trial structures are not an agreed invitation or
send-record design.

The former 10-send trial and weekly, monthly, and quarterly subscriptions
are outside current scope. Do not enforce them as current product policy.

Do not delete historical records or alter external subscriptions merely
because billing is being removed from the application.

## Priority work

1. Verify the current baseline
Inspect files, instructions, Git changes, dependencies, and deployment
artifacts. Confirm historical findings against current source.

2. Implement restricted access
Add email-bound invitations, identity verification, session handling,
revocation, and authorization checks. Production must fail closed when
required access configuration is missing.

3. Replace the active Google and billing flows
Remove Google sign-in, Gmail authorization, checkout, subscription gates,
and trial counters from the current workflow. Add the selected
non-Google sending adapter after provider decisions are resolved.

4. Preserve structured recipient input
Keep names and explicit addresses as structured records.
Fix CSV address loss and define manual/CSV combination behavior.

5. Validate the exact approved batch
Normalize and deduplicate final edited recipients.
Validate BCC, sender details, links, placeholders, and attachments.
Require renewed approval after changes to the approved batch.

6. Track sending durably
Record attempts incrementally, retain provider message IDs, prevent
accidental duplicate submissions, and preserve partial progress.
Handle definite failures and unknown outcomes separately.

7. Enforce operational limits
Apply account-level limits across batches and sessions.
Use atomic reservations where concurrent requests could exceed limits.
These controls are operational safeguards, not paid entitlements.

8. Handle failures safely
Catch timeouts and connection errors.
Return structured outcomes and useful recovery instructions.
Retry only when safe for the provider operation and failure category.

9. Preserve name and message correctness
Preserve compound and non-Latin names.
Expose address-generation limitations.
Block sending when required message validation fails.

10. Make builds and deployment reproducible
Declare complete dependencies and configuration examples.
Verify static-site build dependencies and output-directory creation.
Replace runtime Streamlit package mutation with reproducible assets.

11. Align privacy and operational documentation
Document actual retention, deletion, access controls, and provider use.
Verify claims before publishing them.
Review suppression/do-not-contact behavior and spreadsheet-safe exports.

Historical OAuth, Google identity, subscription-refresh, and paid-trial
defects are deferred unless those integrations are reintroduced.
They must not be mistaken for resolved defects.

## Implementation direction

Keep Streamlit initially.
Extract pure recipient/template logic and service adapters.
Prefer small, independently testable changes.

Explicit addresses take precedence over guesses.
Revalidate the exact batch the user approves.

Use synthetic data and mocked services for automated tests.
Do not send outreach, charge cards, send SMS, or deploy production
changes merely to test code.

Evaluate the existing database for invitations, attempts, and
transactional limits before adding another service.

Retain only the message content, attachments, and credentials needed
for the chosen execution model, with explicit retention and deletion
rules.

## Owner decisions still needed

- Which non-Google sending provider should be used?
- Should messages come from individual mailboxes or a project-controlled
  sending domain, and where should replies go?
- Which non-Google authentication method should invited users use?
- Who may issue invitations, and when should invitations expire?
- Must sending continue after the browser closes?
- What per-user and application-wide sending limits should apply?
- How long should send metadata, messages, and attachments be retained?
- Should manual and CSV inputs combine by default or require a choice?
- Which hosting accounts and domains are currently deployed?

Background sending requires deliberate credential/content retention,
protection, expiry, and deletion. Session-bound sending requires clear
interruption behavior.

These decisions should not block independent parsing, validation, and
mocked test work.

## Dependencies — evaluate before adding

Potential needs:
- Maintained authentication/invitation tooling.
- The selected email provider's official SDK, where useful.
- Email syntax and normalization validation.
- pytest and HTTP mocking tools.
- Dependency locking and lightweight linting.

No new dependencies are approved merely by appearing here.
Check current compatibility and maintenance before selecting them.

Google OAuth and Stripe libraries are not current implementation needs.

## Implementation sequence

A. Verify current source, environment, instructions, Git changes, and
deployment artifacts. Establish reproducible tests.
Do not import app.py casually: top-level code performs side effects.

B. Fix structured recipient import, explicit-address precedence,
final edited-list validation, and rendered-message checks.

C. Implement invitations, verified authentication, authorization, and
explicit environment configuration. Remove active billing dependencies.

D. Select the sending provider and sender model. Replace Gmail sending
with a tested provider adapter.

E. Resolve retention and execution decisions. Implement send tracking,
atomic operational limits, progress, cancellation, and recovery.

F. Complete deployment reproducibility, operational controls, and
accurate privacy/setup documentation for the invite-only release.

## Acceptance tests

- Application operates without Google, Stripe, or Twilio credentials.
- Uninvited users cannot access protected data or send messages.
- An invitation cannot be redeemed by a different identity.
- Expired, revoked, and replayed invitations are rejected.
- Revoked users cannot continue protected actions.
- Users cannot access another user's recipients, attachments, or logs.
- CSV containing names and explicit email preserves the email.
- Email-only, blank, malformed, Unicode, and compound-name inputs.
- Duplicate addresses introduced through table editing.
- Invalid BCC, sender details, links, and unresolved placeholders.
- Changes after approval require renewed approval.
- Duplicate Send clicks and interrupted batches.
- Two sessions competing for remaining operational allowance.
- Provider accepts a message but its response is lost.
- Database finalization fails after submission.
- Provider rejection, throttling, and credential failures.
- Attachment and total message size limits.
- Sensitive session cleanup when accounts change.
- Spreadsheet-safe CSV exports.
- Clean environment installation and static-site build.

Record exact checks and actual results. Never report tests as passing
unless they ran successfully.

## Continuing across sessions

Maintain HANDOFF_STATUS.md with:
date; branch/commit if applicable; completed work; checks and results;
decisions; unresolved issues; next concrete task.

Read this document and that status file at the start of each new session.
