# Launch boundary and future backend

## Implemented now

- A separate React/Vite entry, Tailwind build, self-hosted type, and pinned `border-beam`.
- Explicit local states for import, permissions, per-person editing, review,
  approval, and simulated delivery. All three sample drafts must be opened before
  approval; editing invalidates approval. Restart cancels the current simulation.
- A native waitlist dialog with an injected `WaitlistGateway` interface. Its only
  implemented adapter is `previewWaitlist`: validation, no I/O, `stored: false`.
- No Supabase writes, migrations, functions, keys, Auth changes, mailbox
  credentials, uploads, analytics, or prototype network calls.
- Cloudflare headers with `connect-src 'none'`, making that boundary fail closed
  on the deployed preview. The beam uses component-injected styles, requiring
  inline styles; scripts remain same-origin without `unsafe-inline`.

## Later: real waitlist (requires separate approval)

Do not connect the public UI directly to the prototype or its private schemas.
Do not open up existing authenticated RPCs to anonymous visitors.

1. Confirm the approved Supabase project and inspect its current schema, grants,
   policies and advisors. Preserve existing migrations and pilot records.
2. Approve a real privacy notice, data controller/contact details, purpose, retention,
   deletion process, consent wording and collection fields. A waitlist application
   is not an invitation, user account, or authorization to use the product.
3. Add a separate private waitlist table with RLS and restricted grants; no public
   SELECT, UPDATE, DELETE, or enumeration of applications. Use a reviewed migration,
   not an ad-hoc modification of old migrations.
4. Add an isolated Edge Function accepting bounded POST JSON (email, optional
   goal, consent version, source). Enforce server-side validation, request-size
   limits, an origin allowlist, bot verification (e.g. Turnstile), durable rate
   limiting, and a non-enumerating response for repeat applications. CORS and a
   publishable key are not bot protection or authorization.
5. Keep any privileged key in server secrets only. Minimize logs and stored IP
   data; do not retain resume content. No email confirmation or marketing mail
   should be sent without a separate approved delivery setup and consent review.
6. Implement a Supabase waitlist gateway, inject it, and update preview-specific
   UI copy and result states together. Do not simply remove “preview” notices.
7. Change Pages CSP to allow only the exact approved endpoint and any required
   bot-verification script/frame origins. No broad Supabase wildcard.
8. Test valid/invalid input, consent, throttling, bot rejection, duplicates,
   network failures, PII isolation, grants and RLS. Run advisors and a test query.
9. Deploy a staging version and verify it before opening public collection.

## Later: prototype connection (not authorized here)

`services/prototype-contract.ts` is vocabulary, not a claim of existing API
compatibility. It intentionally has no implementation or configured endpoint.

An integration must preserve verified invite access, ownership checks, private
credentials, exact previews, explicit approval, sending gates, quotas and unknown
outcome recovery. A public waitlist application must never create sending access.
Do not retry an unknown SMTP submission automatically. Delivery status must be
backed by identifiable provider evidence; never translate acceptance into delivery.

AI drafts, resume relevance, and job-contact discovery require their own product,
data-permission, source-evidence, privacy and provider-policy decisions. They are
clearly marked product vision here and are not implemented by this launch page.
