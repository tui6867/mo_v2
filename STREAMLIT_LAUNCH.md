# First launch — Streamlit Community Cloud

## What is ready, and what is not

The repository is set up for Community Cloud, using the official Python UI,
navigation, secrets and connection APIs. Community Cloud deploys from GitHub;
the Streamlit API reference is **not a remote deployment REST API**. No separate
frontend, custom server, deployment token or service-role database key is needed.

With missing backend settings the app starts as a **locked setup shell**, not
a usable invite-only service. This is safe for an operator deployment, but do
not announce availability until the checks below are complete. In this session
the owner reported an existing GitHub-connected Supabase project and confirmed
outreach.users, outreach.settings and the access RPC are present. Remaining
backend/auth/sender settings have not been verified. Built-in-browser sign-in
is unavailable: deployment must be performed in your regular browser.

## 1. Publish the tested files to GitHub

Target: https://github.com/tui6867/mass-outreach-branch

Ensure the tested changes have been committed and pushed to `main`; Community
Cloud reads GitHub, not `C:\Users\isaia\Documents\mass_outreach\outreach-desk-main`.
Review `git status` before committing. Never stage `.env`, `.streamlit/secrets.toml`,
provider credentials, session exports, uploaded resumes or recipient files.
Keep `pyproject.toml` and `uv.lock` together in the repository root. Current
Community Cloud documentation recognizes `uv.lock` before other dependency
manifests; a redundant requirements.txt is neither needed nor desired.

## 2. Deploy in your regular browser

1. Sign in at https://share.streamlit.io/ and connect the GitHub account with
   administrative access to this repository. Review any requested permissions
   yourself; no agent will accept account terms/permissions on your behalf.
2. Create app → use an existing app/repository.
3. Repository: `tui6867/mass-outreach-branch`; branch: `main`; main file: `app.py`.
4. Choose an available `.streamlit.app` subdomain, or accept the generated one.
5. Advanced settings: select **Python 3.12**. The local .python-version file
   does not replace choosing the Python version in the Cloud UI.
6. Secrets: use `.streamlit/secrets.toml.example` as a template. Blank values
   intentionally block access. Do not paste real secrets into chat, GitHub or logs.
7. Deploy. Prefer private/operator-only access during setup if your Cloud account
   offers it; platform privacy is additional to the app's Supabase authorization.
8. Copy the actual application URL and use it consistently for authentication.

No custom build command is required. Cloud installs the uv lock and starts
app.py. No external `packages.txt` dependencies are needed. The obsolete Gmail,
billing and Streamlit-package-patching scripts are not deployment steps.

## 3. Configure Supabase (operator-controlled, no automatic migrations)

For the existing project `iaubupnvesznnxxerimx`, the dashboard is
`https://supabase.com/dashboard/project/iaubupnvesznnxxerimx` (not the app or API).
Confirm the API URL in Connect/API settings; its usual URL is
`https://iaubupnvesznnxxerimx.supabase.co`.

**Existing schema: do not rerun the initial migration blindly.** First run
`supabase/launch_checks.sql` in SQL Editor. It is read-only and prints schema,
grants, quota settings and an admin count, not credentials or user data. Expect:
- Nine named tables present, RLS enabled, no direct anon/authenticated table or
  private-schema access.
- Four public RPCs, SECURITY DEFINER with search_path=pg_catalog, authenticated
  execute true and anon execute false.
- Three checkpoint/provider columns present; plan_1 daily limit 300 (or your
  deliberate configured allowance).
- Required sender/limits set, real_sends_enabled=false during setup, at least
  one active verified administrator before invitations are issued.

If results differ or some objects are missing, stop and reconcile the installed
schema against the migration; do not drop tables or overwrite production records.
Run each query separately if SQL Editor displays only the last result set.

The owner reported the schema/grants checks match but setup is missing. For that
case, use this order:
1. Push/deploy the local code yourself to obtain the actual Cloud app URL.
2. In Supabase, configure that URL and auth mail as described below.
3. Verify a project-controlled outreach sender domain with your chosen SMTP
   provider. Do not set either verified flag just to make the app start.
4. In Authentication → Users, locate a **genuinely email-confirmed** user UUID
   for the first administrator. Your Supabase dashboard/GitHub login is not
   automatically a user of this project's Auth service. If none exists, you can
   use Supabase's **Invite user** action for your own address and follow the Auth
   confirmation email in your regular browser. This is an operator setup action
   that sends an authentication email, not an automated code test or outreach.
   Keep its default Supabase confirmation behavior; after confirmation, use a
   fresh app magic link for sign-in. Do not manually mark an address confirmed.
   Supabase Auth invitations alone never grant product access to other users.
5. Copy `supabase/launch_setup.example.sql` into SQL Editor and fill only the
   three declared values: verified_admin_id, project_sender, domain_is_verified.
   The default template refuses to write. Filled correctly, it transactionally
   sets the suggested limits, keeps real sending off, bootstraps/promotes the
   verified admin and records an audit event. It refuses to reactivate revoked
   accounts or change mismatched identities. Review/adjust the caps first if
   your deliberate operator limits differ.
6. Fill Cloud Secrets with the same sender/caps and confirmed actual app root URL.
   Run the read-only checks again, then sign in as the administrator using an
   app magic link and issue a **product** invitation in the app's Admin section.
   Test only with synthetic recipients in fake mode.

Create/select a Supabase project. Review and test
`supabase/migrations/202610110001_invite_outreach.sql` in an isolated project,
then apply it through your normal migration process. It creates private outreach
tables and four authenticated public RPCs without changing legacy billing tables.
Expose only the intended public RPC schema in the Data API, not `outreach` tables.

Configure Email Auth, auth-email delivery, rate limits and unused-provider
disablement. **Supabase's default auth mail service is not production-ready:**
its documented limit is currently two messages/hour and it sends only to project
team addresses. Configure custom SMTP in Authentication → Email/SMTP before
inviting non-team users. Auth mail settings are separate from the app's outreach
SMTP settings; prefer separate sending subdomains/reputations, and confirm the
outreach provider's acceptable-use rules permit this product's use. Do not turn
off email confirmation to work around delivery restrictions. Product access remains invite-only even if uninvited Supabase Auth
accounts exist. Set Site URL and exact allowed redirect URL to the **actual Cloud
app root URL**, not localhost or the historical domain. In the magic-link email
template, use (also update the signup confirmation template if that flow uses it):
```
{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=email
```
This matches the app's supported server-side token-hash callback. Do not use the
default fragment-only access-token URL: this application does not read URL fragments.
Protect/redact token-hash query strings in infrastructure logs where configurable.

Bootstrap the administrator using the UUID of a Supabase Auth user who has
actually verified control of their email (do not manually claim verification):
```sql
insert into outreach.users (id, email, is_admin)
select id, lower(email), true
from auth.users
where id = '<VERIFIED_ADMIN_AUTH_UUID>'::uuid
  and email_confirmed_at is not null;
```
Check exactly one row was inserted and ownership uses that UUID. Existing-user
promotion/revocation must be reviewed by the operator; do not delete/recreate
accounts or silently reactivate revoked users. The app does not use a service-role
credential. See SETUP.md for invitation issue/redemption/revocation semantics.

Set authoritative database limits and verified project sender after provider
verification. Suggested first-launch limits match the secrets template:
```sql
update outreach.settings
set batch_limit = 50, global_hourly_limit = 100, global_daily_limit = 300,
    sender_email = '<VERIFIED_PROJECT_SENDER>',
    sender_domain_verified = true, real_sends_enabled = false
where singleton;
```
Plan 1 defaults to 300 accepted real submissions per user per UTC day. App caps
can tighten database limits, never increase them. Keep database real sending off.

## 4. Fill Community Cloud Secrets

Copy the template's **top-level** TOML settings into app settings → Secrets.
TOML integers and booleans are supported explicitly, not just quoted strings.

| Setting | Value/check |
| --- | --- |
| SUPABASE_URL | Your HTTPS project URL |
| SUPABASE_ANON_KEY | Publishable/anon key; NEVER service-role key |
| AUTH_REDIRECT_URL | Exact actual HTTPS Cloud root URL, with no fragment/query |
| SENDER_EMAIL | Verified project-controlled sender, not a user's personal mailbox |
| SENDER_DOMAIN_VERIFIED | true only after real provider/SPF/DKIM/DMARC verification |
| BATCH_LIMIT / GLOBAL_HOURLY_LIMIT / GLOBAL_DAILY_LIMIT | Positive caps, matching/tightening database settings |
| MAX_ATTACHMENT_BYTES | Template: 5 MiB |
| MAX_MESSAGE_BYTES | Template: 10 MiB including encoded MIME overhead |
| MAX_CSV_BYTES | Template: 1 MiB |
| ENABLE_REAL_SENDS | false throughout first-launch testing |
| SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD | Actual provider's protected server settings, only when activating SMTP |
| SMTP_PORT / SMTP_TLS_MODE | Provider-supported TLS endpoint; ssl or starttls, never plaintext |
| SMTP_TIMEOUT_SECONDS | Positive and at most 120; template 30 |

Streamlit's server upload cap is 10 MiB, configured separately in
`.streamlit/config.toml`. Raise it deliberately if application upload caps are
increased. The stricter application byte limits still apply before reading files.
Explicit environment variables override TOML settings, including blank/false
overrides; .env is not automatically loaded. Never put application secrets in
config.toml or the example template.

For a local **offline** config check (no network or send):
```
uv run python -m outreach.preflight --secrets-file .streamlit/secrets.toml
```
It exits nonzero for incomplete configuration and never prints values. Passing
means configuration validates only, not database/provider connectivity.

## 5. Architecture / hosting safeguards

- app.py stays the composition root; `st.Page`/`st.navigation` expose Outreach,
  Privacy and Terms with stable `/privacy` and `/terms` URLs.
- `st.connection("supabase", type=SupabaseConnection)` uses a **session-scoped**
  BaseConnection (requires Streamlit 1.65+). Only an HTTP transport is reused.
  Each run constructs a fresh user-JWT wrapper, no JWT enters connection-cache
  arguments/default headers, no auth decisions or protected query results are cached.
- Existing Supabase RPCs remain authoritative on every protected operation.
  Direct SQLConnection/service-role access would bypass that design and is not used.
- `.streamlit/config.toml` enables CORS/XSRF protection, limits upload size and
  hides detailed exceptions. Cloud may override settings such as telemetry or
  fast reruns; do not rely on those as security/access controls.
- Cloud restarts/hibernation discard session memory. Outcomes remain in Supabase;
  recovery requires login, exact review and identical attachment reupload. Unknown
  submissions are never automatically retried. No local disk persistence is required.
- Confirm actual host-to-Supabase HTTPS and provider SMTP egress/support before
  activating real sends. A local SMTP check does not prove Cloud egress. Do not
  swap to an HTTP sending provider or disable TLS merely to bypass host restrictions.

## 6. Checks before inviting users

Run locally/CI:
```
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run python -m compileall -q app.py outreach legal.py build_site.py
uv run python build_site.py
```
Then check in your hosted application (no real outreach sends):
- Cloud build succeeds using Python 3.12/uv.lock, no credential values in logs.
- Missing settings show a locked setup state, not unrestricted access.
- `/privacy` and `/terms` render. Resolve visible operator/provider/retention/legal
  draft placeholders before public availability; this session cannot invent them.
- Auth-email callback uses the correct app root; invited user verifies the bound
  email; wrong/expired/revoked/replayed invites are denied.
- Admin/other users cannot read another user's batches/logs. Revocation blocks
  subsequent actions. Verify RPC permissions/RLS with isolated accounts/database.
- Fake mode remains selected, actual To is the verified account, BCC is disabled,
  no SMTP/network email submission occurs, progress/log/export/recovery work.
- Confirm real Postgres two-session quota races and interruption/cancellation
  behavior. Unit tests use fakes; syntax parsing is not migration execution proof.

Only after these checks, provider/domain verification and finalized legal/privacy
decisions should an operator enable **both** application ENABLE_REAL_SENDS and
database real_sends_enabled. This session does not enable them or send live messages.

## Troubleshooting

- Missing module/build error: verify pushed uv.lock + pyproject and selected Python.
- Missing configuration: fill real Cloud Secrets, not the example file in GitHub.
- Magic link lands unauthenticated: check Site URL, exact redirect, email template,
  token expiry and Cloud URL; never paste the token into tickets/logs.
- "Invitation required": check verified Auth UUID and active outreach user/invite.
- Missing RPC/permissions: apply reviewed migration and verify grants in Supabase.
- SMTP timeout: keep real sends off; confirm provider/host egress and TLS endpoint.
  Never retry an unknown outcome.
- Cannot deploy through the agent browser: use your regular browser; there is no
  documented Community Cloud deployment API to replace account sign-in.

References used:
- https://docs.streamlit.io/develop/api-reference
- https://docs.streamlit.io/develop/api-reference/connections/st.connection
- https://docs.streamlit.io/develop/api-reference/connections/st.connections.baseconnection
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://supabase.com/docs/guides/auth/auth-smtp
