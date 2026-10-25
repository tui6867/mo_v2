# Separate Cloudflare workspace

**Hosted URL:** https://mass-outreach-app.gamingtui94.workers.dev

The operational app lives in `cloud-app/`. `/frontend` (including its launch page),
the older `mo-v2` Worker and the WSL/Postfix/Mailpit pilot are not replaced.
The repository-root `wrangler.jsonc` explicitly selects the **new** Worker entry
point and assets, fixing the missing-entry-point problem for this separate target.
Do not repoint the original Worker's build pipeline to this target accidentally.

## Current release checkpoint — 2026-10-25

- Worker/API, static assets and SQLite-backed `MailSession` Durable Object deployed
  using Cloudflare MCP. No plan upgrade or paid subscription was requested.
  Billing information could not be read with the current OAuth connection.
- Additive migration `20261025052211_cloud_mail_app.sql` applied through Supabase
  MCP to **`gnmimpoeqxeczjhvzrrx` only**; local filename matches hosted history.
- Existing active users/administrator retained. `gamingtui94@gmail.com` remains
  administrator; application approval never grants administrator rights.
- Cloudflare → Gmail TLS connection/greeting verified **without authentication,
  envelope submission or sending**. The temporary public probe was replaced.
- **Live sending starts paused in `outreach.cloud_settings`.** Older legacy/pilot
  live gates also remain off. Hosted authenticated and real-send acceptance are
  pending user-operated login, Gmail connection and final approval.
- The earlier pilot still has its one real Gmail acceptance; this deployment has
  not authorized or performed an additional real email send.

## Finish hosted sign-in

In [Supabase Authentication → URL Configuration](https://supabase.com/dashboard/project/gnmimpoeqxeczjhvzrrx/auth/url-configuration):

1. Set **Site URL** to `https://mass-outreach-app.gamingtui94.workers.dev`.
2. Add that same URL to **Redirect URLs**. Keep existing valid entries, including
   `https://localhost:8443` if the old pilot is still used.
3. Use the **hosted app** to request a fresh sign-in email, then open it yourself.
   Links are single-use. Do not paste links, tokens or passwords into chat.

Reported error: `400 Client sent an HTTP request to an HTTPS server` after opening
a sign-in email. Auth logs showed `http://localhost:8443` in the sign-in flow.
Port 8443 expects HTTPS; that HTTP URL is not a valid hosted-app callback. Correct
the configuration above and request a new link rather than replaying the old one.
The MCP connection has no Auth-config update tool, and the browser dashboard was
signed out; no login flow was automated.

The user subsequently reported an apparently blank message and identified its
subject as a **sign-in/magic-link email**, not an outreach email. At investigation,
cloud batches/acceptances/submitting attempts were all zero and all live gates
were off. The user confirmed the Magic Link template has content; repeated Gmail
thread content may be collapsed/trimmed. This explanation has not been verified
in the mailbox. Expand the newest message and any “Show trimmed content” control,
then open only a fresh link yourself after correcting HTTPS redirects. The Auth
template and SMTP credentials have **not** been overwritten or rotated.

## Use the workspace

1. Verify your email and submit your name/intended use if not already approved.
2. Administrator: **Manage access** → review requests → approve/revoke, edit name,
   private notes and daily limit (1–10). Email/sender identity is not editable.
3. Administrator: review permitted purposes before enabling live sending. Gmail
   prohibits spam/unsolicited commercial email. CSV ownership does not establish
   consent or policy compliance; the user's precise cold-outreach purpose remains
   unresolved. Do not treat this implementation as approval for arbitrary lists.
4. Import a CSV (`email` plus optional `name`, or `first_name`/`last_name`), edit
   recipients and select at most five. UTF-8 BOM, quoted names, commas and doubled
   quotes are supported. Duplicates are reported/omitted, not silently sent twice.
5. Connect the **same verified Google account** with a dedicated Google app
   password in the trusted HTTPS app. The account must support app passwords and
   satisfy Google's 2-Step Verification/organizational policies. Never use a normal
   Google password. There is no Google OAuth application or OAuth review flow.
6. Write exact plain-text subjects/bodies. Optional deterministic placeholders:
   `{{name}}`, `{{first_name}}`, `{{email}}`. No AI rewriting or fabricated fields.
7. Open every recipient's preview; confirm the exact content/recipients and
   permitted use yourself. This is the final real-send approval.
8. Keep the app visible/open for sequential sends. Hidden tabs pause between
   recipients. A started SMTP submission may finish and cannot be recalled.

The animation follows actual application status; it does **not** simulate inbox
delivery. `SMTP accepted` means Gmail returned final acceptance after DATA, not
that the recipient received/read it. `Not accepted` covers rejection or a known
pre-acceptance failure. `Uncertain` means do not resend; check Gmail Sent manually.
There is no automatic retry. The same approved content hash returns its existing
batch, including after a lost HTTP response; it does not create another send.

## Controls and security boundaries

- Caps: **5/batch, 10/user/UTC day, 50/global/UTC day**. Unresolved holds count
  across days; prior pilot real acceptances/holds are included conservatively.
- Atomic quota reservations/claims, ordered recipients and immutable approved
  content live in private Supabase tables. Authenticated users cannot read those
  tables or invoke the mail RPC without the Worker-only HMAC signature.
- Every sensitive SQL operation checks a confirmed Auth user, matching
  `auth.sessions` row, owner and session. Live claims recheck current approval,
  sender, quota, suppression and global switch; JWT role metadata is not trusted.
- Revocation cancels unclaimed cloud recipients. Already-claimed/in-flight
  outcomes may finalize, but cannot authorize another claim. One request replay
  can refer only to its original recipient ordinal.
- Global kill switch is in **Manage access**. Deployment variable
  `LIVE_SENDS_ALLOWED=false` is an independent operator stop. Database switches
  for the older live transports must remain off while using this cloud transport.
- Gmail credentials are held only in a per-owner Durable Object's **memory**, bound
  to the real Auth session. They are not written to Supabase, Durable Object
  storage, logs, localStorage, sessionStorage or cookies. The input is cleared on
  submission; immutable JavaScript strings cannot promise physical heap zeroing.
- Idle expiry: 30 minutes; absolute expiry: two hours. Eviction, deployment,
  restart, expiry or disconnect requires reconnecting. Only an expiration alarm,
  not a credential, is stored in the Durable Object. No background sending alarm.
- Auth tokens are also memory-only; reload can require a fresh sign-in link.
- SMTP host/port are fixed to `smtp.gmail.com:465` over verified implicit TLS.
  No arbitrary destination/port, domain impersonation or local relay access.
- The debug tab is administrator-only, shows sanitized deployment/database facts,
  and can be disabled using **Remove debug screen**. Its API is then blocked too.
- Unknown submissions retain quota holds and are never retried. After five minutes,
  **Recover interrupted status** changes stale `submitting` rows to `unknown`.
  Cancellation releases only unclaimed queued recipients. Operator investigation
  is required for unresolved outcomes; no unsafe “retry all” or erase-history UI.
- Worker observability/logpush/tail consumers are disabled; no credential/body
  logging is implemented. A private signing key is stored in Supabase and as a
  Cloudflare secret, never in build artifacts. The publishable key is public.

Supabase advisors flag the exposed `SECURITY DEFINER` RPC and RLS-without-policy
private tables. These are intentional: direct table grants are revoked and the
RPC enforces HMAC + Auth session + owner/admin checks. See the
[function advisory](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable)
and [private-table advisory](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
Existing project findings also include
[disabled leaked-password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection)
and pre-existing foreign-key index notices. Do not call the project advisory-free.

## Development and deployment

```powershell
npm --prefix cloud-app ci --ignore-scripts
npm --prefix cloud-app run build
npm --prefix cloud-app test
npm --prefix cloud-app run test:browser
```

First browser run: `cd cloud-app`, then `npx playwright install chromium`.
The browser tests use `tests/visual.html`, a **local synthetic UI fixture** with
no real authentication, password or network transport. It is not included in
`dist/` or the deployed app. Unit, protocol and SQL tests are separate from real
hosted acceptance; synthetic screenshots are not evidence of real delivery.

Real PostgreSQL tests use disposable, network-isolated Docker containers:

```powershell
$env:MAIL_RUN_DB_TESTS='1'
uv run pytest tests/test_cloud_mail_postgres.py tests/test_mail_postgres.py -q
```

`npm --prefix cloud-app run deploy` invokes the root Wrangler configuration;
it needs a user-configured Cloudflare CLI login or appropriately scoped CI secret.
Install dependencies first; the custom Wrangler build compiles but does not run
`npm ci` inside an already-running Wrangler process. For a new Cloudflare Git build,
use repository root, build command `npm --prefix cloud-app ci --ignore-scripts`,
and deploy command `npm --prefix cloud-app run deploy`. Target the separate
`mass-outreach-app` Worker, not the original `mo-v2` pipeline.
Do not send credentials in chat. Supabase migrations must be installed first.
Worker `CLOUD_MAIL_SIGNING_SECRET` must match the private database key; the MCP
deployment transferred it internally without printing it or saving a local copy.
Do not expose `service_role` keys or store any Gmail password as a Worker secret.

For local Worker preview, copy `cloud-app/.dev.vars.example` privately to the
repository root `.dev.vars` beside `wrangler.jsonc`. Keep live transport disabled.
The HTTP Vite development page intentionally disables Gmail-password entry.

`bundle:mcp` prepares a no-secret script/asset manifest under ignored
`cloud-app/.mcp-deploy/`. `tools/serve-mcp.mjs` is a read-only loopback artifact
bridge with a ten-minute lifetime, used for the MCP upload; it never reads private
configuration or receives credentials. Do not expose it on a public interface.

## Remaining acceptance gates

- User confirms the HTTPS redirect change and successfully signs in to the hosted
  app; verify protected admin/debug/owner routes against that real session.
- User specifies a provider-permitted message purpose and approves enabling live
  sending. No claim that arbitrary cold commercial outreach is Gmail-compliant.
- User connects Gmail and personally confirms any real test batch. The assistant
  must not enter credentials, open Auth links or click final send approval.
- Verify resulting durable statuses; recipient delivery/SPF/DKIM/DMARC remain
  unverified without recipient-side evidence. Do not resend just to investigate.
- Dedicated old `Mail pilot frontend test` app-password revocation is still an
  account-owner task. Do not confuse it with `Supabase Auth development`, which
  is the separate existing sign-in SMTP credential.

## Verification completed

- Cloud app/Worker unit, component and SMTP tests: **28 passed**.
- Browser UI fixture: **3 passed** (desktop, 390px mobile, reduced motion), covering
  import/edit/review/explicit approval/status/admin/debug removal, no page errors
  or document overflow. These are synthetic sends only, not hosted acceptance.
- Full Python regression suite with real isolated PostgreSQL enabled:
  **132 passed, 2 optional separate-stack smoke tests skipped**. This includes
  7 new cloud SQL tests and 11 existing pilot SQL tests.
- Existing `/frontend` suite: **17 passed**; no files in `/frontend` edited.
- TypeScript frontend/Worker checks, Vite build and root-Wrangler deployment
  dry-run pass. Dependencies audited with **zero reported vulnerabilities**.
- Final cloud deployment `21be97e6eaac4ba68a0d07b3a96b4fdc`: HTML, JS, CSS,
  public config and health return 200; unauthenticated `/api/me` returns 401;
  security headers present. Fonts are same-origin, not CSP-blocked data URLs.
- Final remote check: cloud live false, zero cloud batches/submitting attempts,
  original one real pilot acceptance retained, legacy/pilot live gates false.
- No assistant commit or push. No issue/PR was supplied or opened to link.
