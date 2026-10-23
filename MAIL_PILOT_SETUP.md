# Frontend mail pilot — operator setup

This is the **testing copy** at `C:\Users\isaia\Documents\mo_v2`. The original
Streamlit UI remains available. The new React/FastAPI interface is separate.
No remote migrations, service login, deployment or live sending was performed
by the implementation session. Follow these steps **in your own browser**.

**Current execution:** the connector targets the approved development project;
all three migrations are installed. Both real-user capture/isolation and the
existing-session revocation test passed. One explicitly approved, user-confirmed
Gmail message reached durable SMTP acceptance; inbox delivery/header checks are
unverified because the recipient mailbox is unavailable to the operator. No
additional live send or recipient change was made. Both live gates are off again
and the API is back in capture mode with
its in-memory credentials cleared. The second user's non-admin access is restored.
After Docker connectivity recovered, all four pilot services were started again;
API/mail healthchecks and web HTTPS checks pass. Volumes and captures were preserved.
The original implementation session's no-remote-change statement above is
historical. Follow **[MAIL_PILOT_NEXT_STEPS.md](MAIL_PILOT_NEXT_STEPS.md)** for the
current checkpoint and remaining recipient/credential checks. Do not reapply
migrations or regenerate an already configured database signing key.

## 1. Scope and policy gate

- One plain-text message, one operator-configured **test-owned recipient**,
  exact preview and explicit confirmation. No bulk sending, BCC, attachments,
  aliases, automatic retries or arbitrary SMTP servers.
- Gmail/Workspace app-password mode uses `smtp.gmail.com:587` with verified
  STARTTLS. Your verified application email is the SMTP username, From,
  Reply-To and envelope sender. Dot/plus variants are not treated as equivalent.
- SMTP authentication **does not override Google's previous API verification
  rejection or authorize prohibited use**. The eventual unsolicited job-outreach
  use case remains a policy/product release blocker. Switching providers is not
  a way to evade policies; select a provider that explicitly permits the actual
  use case and review sender-identity requirements before extending this pilot.
- Google's [Program Policies](https://www.google.com/gmail/about/policy/)
  prohibit spam and unsolicited commercial mail. Its
  [sender guidelines](https://support.google.com/mail/answer/81126?hl=en)
  advise against sending to people who did not sign up. Fewer messages does not
  make otherwise prohibited messages acceptable.
- [Personal Gmail limits](https://support.google.com/mail/answer/22839?hl=en):
  sending more than 500 emails/day or over 500 recipients in one message may
  trigger a restriction; recovery can take 1–24 hours.
- [Workspace limits](https://support.google.com/a/answer/166852?hl=en) vary by
  account/trial/method: commonly 2,000 messages/day, 500 for trial accounts;
  the window is **rolling 24 hours**, and SMTP has separate recipient limits.
  They can change without notice. Other activity in the same mailbox counts.
- This application's conservative **5/hour, 10/day global UTC-calendar caps**
  are not a promise that Google will accept mail and do not track Gmail usage
  elsewhere. Provider quota errors are final failures here; do not retry
  automatically or rotate accounts to bypass restrictions.
- Gmail delivery requires TLS and authenticated domains (SPF or DKIM for all
  senders to personal Gmail). Workspace domain operators should configure and
  verify SPF, DKIM and DMARC. Inspect received headers during the actual test;
  authentication success or SMTP acceptance alone does not prove deliverability.

## 2. Manual Supabase setup — development project only

Open <https://supabase.com/dashboard/project/gnmimpoeqxeczjhvzrrx> yourself.
The connector has now been verified against this **development** project.
The old project `iaubupnvesznnxxerimx` must not be modified. Recheck the connector
target at the beginning of any later setup session.

### Inspect before applying

In **SQL Editor**, run these read-only checks:

```sql
select to_regnamespace('outreach') as existing_outreach_schema;
select schemaname,tablename from pg_tables where schemaname='outreach';
select n.nspname as extension_schema,e.extname from pg_extension e
join pg_namespace n on n.oid=e.extnamespace where e.extname='pgcrypto';
```

If `outreach` already contains tables, **stop and report the redacted structure**;
do not rerun the original migration or delete data. If `pgcrypto` exists outside
`extensions`, stop and report that schema rather than moving it blindly.

For a fresh project, review and run, in order:

1. `supabase/migrations/202610110001_invite_outreach.sql`
2. `supabase/migrations/20261020223515_session_mail_pilot.sql`
3. `supabase/migrations/20261021020352_qualify_pilot_history_columns.sql`

Run each as a transaction (`BEGIN;` / file content / `COMMIT;`) so a failure
cannot leave half a migration applied. These create private application tables
and authenticated RPCs; they do not enable live sending. Preserve any unrelated
data. Keep `outreach` **out of Data API exposed schemas**; public RPC grants are
explicit. Do not grant browser table access or add service-role keys to the app.

### Auth, keys and bootstrap

1. In **Authentication → URL Configuration**, set Site URL to
   `https://localhost:8443` and allow that exact redirect URL. Central deployment
   needs its own HTTPS origin/redirect, not the localhost configuration.
2. Enable Email authentication. Use the normal Magic Link template that sends
   `{{ .ConfirmationURL }}`. **Do not copy the old Streamlit token-hash callback**:
   this separate frontend uses the SDK's implicit callback with memory-only auth
   storage. No OAuth consent or Gmail API scope is requested.
3. In **Project Settings / Connect / API Keys**, obtain the project's publishable
   key (`sb_publishable_...`, or legacy anon key). Enter it **privately** in
   `infra/.env`. Never use `sb_secret_...` or a service-role key.
4. Supabase's default Auth mail delivery is limited to project-team addresses
   and low rates. If a sign-in email fails, inspect **Authentication logs** once.
   Configure your own Auth SMTP provider for other users, or use a team address
   for initial testing. This Auth provider is **separate** from session-only
   customer Gmail credentials. Provider usage may cost money. Do not repeatedly
   request links or weaken email verification to work around a failure.
5. **Complete §3 below to configure/start the local HTTPS app first**, then return
   here. Use the app to request a sign-in link and open it in **your own browser**.
   The first Auth signup creates an identity but grants no product access yet.
   In **Authentication → Users**, confirm the email is verified and copy its UUID
   privately. Dashboard login is not an application Auth identity.
6. Copy `supabase/mail_pilot_setup.example.sql` to ignored
   `infra/mail_setup.private.sql`. Fill the target reference, verified admin UUID,
   test-owned recipient, the same signing secret as `infra/.env`, and the approval
   boolean. Review and run it in this development project's SQL Editor.
   This bootstraps one invited administrator and capture configuration only;
   it does not enable real mail. The secret may be retained in dashboard SQL
   history: keep operator access private. Never share this filled file in chat.
7. Sign in again or refresh the app. Access should now be granted.

For a second invited user, create a random invitation code privately with the
same `secrets.token_hex(32)` command. In this project's SQL Editor, replace the
three placeholders below privately and run:

```sql
begin;
select set_config('request.jwt.claims',
  jsonb_build_object('sub','VERIFIED-ADMIN-UUID','role','authenticated')::text,true);
select public.issue_invitation('SECOND-TEST-OWNED-EMAIL',
  encode(extensions.digest('RANDOM-PRIVATE-INVITATION-CODE','sha256'),'hex'),
  now()+interval '24 hours');
commit;
```

The user verifies their own email, then uses **Redeem application invitation**
with that code. Keep the code and SQL history private. Never paste JWTs or codes
into chat. Alternatively use the existing Streamlit admin UI configured for
**this development project** (its own legacy sender configuration is separate).

### Where sender and recipient addresses are managed

| Purpose | Location | Rule |
| --- | --- | --- |
| First operator/admin | Verified `auth.users` identity, then `outreach.users.is_admin` | Current selection: `gamingtui94@gmail.com`; never grant admin merely because a browser claims this email. |
| Additional sending users | `public.issue_invitation` / `public.redeem_invitation`; `outreach.users` | Invite the new address, have its owner verify sign-in and redeem the code. `igabbay@binghamton.edu` is the selected second test user. No source-code sender list needs appending. |
| Actual sender/Reply-To/SMTP username | `outreach/api/store.py:MailStore.identity`, `outreach/api/app.py:render` / `connect` | Always derived from that session's verified identity. A different sender needs its own verified, invited account; changing a UI default does not authorize it. |
| Sole test recipient (backend) | Private `infra/.env`, `MAIL_TEST_RECIPIENT`; loaded by `outreach/api/config.py:Settings.load` | Current selection: `leokarpel98@gmail.com`. After editing, recreate only the API service. |
| Sole test recipient (database) | `outreach.mail_settings.test_recipient`; enforced by `outreach.mail_eligibility` in the pilot migration | Must match the backend's single address. Change it with an operator-authorized SQL UPDATE, not by editing an applied migration. |
| Recipient display | Authenticated `/api/me` → `frontend/src/App.tsx` | Read-only display of the configured recipient; not an authorization list. |

To **replace** the recipient for a future controlled test, first turn live sending
off and coordinate any in-flight request, update the one database address and
`MAIL_TEST_RECIPIENT`, then recreate the API and review a new preview:

```sql
update outreach.mail_settings
set live_enabled=false, test_recipient='NEW-TEST-OWNED-EMAIL'
where singleton;
```

```powershell
docker compose -f infra/compose.yaml up -d --force-recreate api
```

Set `MAIL_ENABLE_REAL_SENDS=false` privately before that recreation. This drops
memory-only connections. **Do not append comma-separated recipients**: this pilot
supports exactly one operator-controlled test recipient globally. Per-user or
multiple-recipient support requires a separately reviewed schema/API change with
isolation tests and a provider-policy decision. Gmail connection works only for
eligible Gmail/Workspace accounts; invitation alone does not establish eligibility.

## 3. Private local configuration and HTTPS

Start Docker Desktop yourself and wait for its engine to be ready. The original
relay at `/home/devcontainers/projects/postfix_files` is **not** used or modified.
Its ports 1587/8025 and volumes stay untouched.

Copy `infra/.env.example` to ignored `infra/.env`, then fill the publishable key
and test-owned recipient. Generate a signing secret in your **private terminal**:

```powershell
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Use that value for `MAIL_SIGNING_SECRET` and the private SQL setup file. This is
a backend-command key, **not** an SMTP password. Do not share it. Keep:

```dotenv
MAIL_SUPABASE_URL=https://gnmimpoeqxeczjhvzrrx.supabase.co
MAIL_ORIGIN=https://localhost:8443
MAIL_TRANSPORT=capture
MAIL_ENABLE_REAL_SENDS=false
```

From the repository root:

```powershell
docker compose -f infra/compose.yaml up --build -d
docker compose -f infra/compose.yaml ps
```

Compose project `mo-v2-mail-pilot` uses separate named volumes, private API/SMTP
ports and loopback-only HTTPS `8443` / Mailpit administration `8026`. Mailpit
has **no relay secrets or external network**, and Postfix is egress-isolated.
It cannot release mail through the successful original relay.

Caddy creates a private local CA. Before credentials, copy and trust its **public
root certificate** (never its private key):

```powershell
New-Item -ItemType Directory -Force infra/certs
docker compose -f infra/compose.yaml cp web:/data/caddy/pki/authorities/local/root.crt infra/certs/pilot-root.crt
certutil -user -addstore Root infra/certs/pilot-root.crt
```

Trusting a CA permits certificates it signs; restrict access to the Caddy volume,
use this only on your development machine and remove this CA from your user trust
store when finished. If your browser uses a separate trust store, import the
public root there manually. **Do not click through certificate warnings to enter
credentials**, disable TLS verification, or expose the private API directly.

Open <https://localhost:8443> in your own browser. API health is
<https://localhost:8443/api/health>. Health is process liveness, not proof of
Supabase configuration or SMTP readiness. `npm run dev` is only a no-credential
UI development server; use the HTTPS Compose proxy for actual sign-in/connections.

If setup fails, report the failing step/status and redacted logs. Do not include
`.env`, filled SQL, passwords, authorization headers or URL fragments from Auth.
Never run `docker compose config` publicly: it can expand private env values.

## 4. Capture test first

1. Sign in as the invited verified user. Click **Start capture session**; no
   password field is present and capture mode rejects supplied SMTP passwords.
2. Compose plain text, preview it, approve the exact preview, and click
   **Capture one email**.
3. Inspect <http://localhost:8026>. API acceptance means **Postfix queued** the
   message, not that Mailpit has already stored it. Verify the captured From,
   Reply-To, To, Subject, body, Date and Message-ID there.
4. Refresh durable history. Double-clicking or repeating the same owner/content
   must not create a second SMTP submission. Changing content requires reapproval.
5. With two invited users in separate browsers, verify cross-user history and
   connection isolation, revoke one through the operator/admin path, and confirm
   that further preview/send requests are blocked.

## 5. One user-operated Gmail test

**Current checkpoint:** one approved live submission already completed/accepted.
Both gates were disabled afterward. Do not repeat it; the instructions below are
for a future separately approved test. See `MAIL_PILOT_NEXT_STEPS.md` for results.

Only after real SQL/role tests and capture tests pass, and you approve the actual
message/recipient, enable **both** gates yourself:

```sql
update outreach.mail_settings set live_enabled=true where singleton;
```

Set `MAIL_TRANSPORT=gmail` and `MAIL_ENABLE_REAL_SENDS=true` in `infra/.env`, then:

```powershell
docker compose -f infra/compose.yaml up -d --force-recreate api
```

Recreation loses memory-only connections. Use a fresh preview; capture approvals
cannot authorize Gmail sends. Do **not** change the legacy domain-verification flag
or relay credentials. `outreach.settings.real_sends_enabled` remains the legacy
project-SMTP gate; `outreach.mail_settings.live_enabled` is the separate pilot gate.

In your own browser:

1. Enable [2-Step Verification](https://myaccount.google.com/security) and create
   an app password at <https://myaccount.google.com/apppasswords>. Google recommends
   OAuth when available; this pilot uses app passwords only where permitted.
   Workspace admin policy, security-key-only 2FA or Advanced Protection may
   prevent app passwords. If unavailable, **stop**—do not use your normal password
   or enable deprecated “less secure apps.” Decide on a provider/auth pivot.
2. Enter the app password **in the app's HTTPS form yourself**. The input clears
   before the request completes. Connect performs TLS/authentication only; no
   email is submitted. A wrong password is rejected without raw SMTP diagnostics.
3. Preview one plain-text test, confirm it, and click **Send one real email**.
   This sends real mail and consumes provider/application allowance.
4. “Accepted” means Gmail accepted SMTP DATA, **not inbox delivery**. Inspect
   received headers (SPF/DKIM/DMARC, actual From), spam folder and Gmail Sent view.
   Do not provide full message headers containing private data in chat.
5. Disconnect. Revoke the dedicated app password on Google's App Passwords page
   when finished; disconnect alone only drops this backend's references.
6. Turn both live gates off after the test. Capture mode never falls back to Gmail.

## 6. Status, restart and failure semantics

- Passwords are held in one backend process only, expire after **30 minutes idle**
  or **two hours maximum**, and are pruned every minute/on use. Python reference
  removal is best effort, not guaranteed byte-zeroization. No SMTP password is
  written to browser storage, database, relay YAML, image or durable job payload.
- Supabase JWTs are verified through Auth; signed commands also verify a live
  `auth.sessions` row and invitation access. Owner/session IDs are not trusted
  from the browser. Auth tokens are memory-only in the frontend too: a full reload
  may require another sign-in. Reconnect after expiry/restart/session change.
- Every SMTP operation has a committed durable claim first. Failed finalization
  returns explicit uncertainty; refresh history, **do not resend**. A stale
  `submitting` claim can become `unknown` only after five minutes through
  **Recover interrupted status**. Unknown retains its conservative quota hold.
- No automatic retry of rejected, accepted or unknown messages. Identical
  owner/content is duplicate-protected across connection/backend restarts.
- Preview receipts expire after ten minutes and bind owner, Auth session,
  connection and exact content. Sender/content/policy/connection changes invalidate
  approval. Disconnect blocks future sends, not an already in-flight SMTP request.
- Public browsers cannot finalize pilot outcomes: commands require a short-lived
  backend HMAC signature as well as the user's verified JWT. The signing key is
  in a private table and backend env only. The old project-SMTP API is preserved,
  but explicitly cannot operate on pilot batches.
- Quotas, suppression entries and claim/finalization/recovery tables are shared
  with legacy sending under its existing global transaction lock. History hashes
  and historical manifests are not rewritten. Pilot records carry versioned
  `user_gmail_v1` / `user_capture_v1` policies.
- Status uses explicit authenticated refresh, **not Realtime Broadcast yet**.
  Multi-worker deployment, background sends, production legal/retention/abuse
  handling and generalized customer delivery remain outside this controlled pilot.
- Centrally hosting this requires a real HTTPS domain, matching origin/Auth
  redirects/CSP/host configuration, outbound SMTP 587, private administration,
  and one backend worker/replica until credential routing is designed. Customers
  would then need only a browser, not Docker/WSL. Supabase URL is intentionally
  locked to the approved development project; production needs explicit review.

## 7. Verification commands

Do not replace/delete the copied `.venv`; it contains a foreign environment link.
On this Windows checkout use an isolated approved environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT="$env:LOCALAPPDATA\Temp\opencode\mo-v2-mail-pilot"
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run python -m compileall -q app.py outreach legal.py build_site.py
npm --prefix frontend ci --ignore-scripts
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit
```

With Docker running, opt into real SQL/role/concurrency tests:

```powershell
$env:MAIL_RUN_DB_TESTS='1'
uv run pytest tests/test_mail_postgres.py -v
Remove-Item Env:MAIL_RUN_DB_TESTS
```

That suite creates/removes only its own disposable PostgreSQL 17 container,
without host ports, network or durable volumes. It tests actual SQL/grants,
claim/quota races, suppression/revocation, unknown recovery, invitations and legacy
compatibility. Minimal fixture Auth tables/claims do **not** prove hosted Supabase
GoTrue/PostgREST behavior. The two-user hosted check remains a separate gate.
CI is configured to run the real PostgreSQL suite and frontend checks; no CI run
is claimed until these local changes are committed/pushed by you.

To reproduce the real HTTPS/capture transport smoke tests without any usable
Supabase key, real SMTP password or remote database setup:

```powershell
docker compose -p mo-v2-mail-pilot-verification -f infra/compose.yaml -f infra/compose.verify.yaml up --build -d --wait
$env:MAIL_RUN_CAPTURE_TESTS='1'
uv run pytest tests/test_mail_capture.py -v
Remove-Item Env:MAIL_RUN_CAPTURE_TESTS
docker compose -p mo-v2-mail-pilot-verification -f infra/compose.yaml -f infra/compose.verify.yaml down
```

The override needs a recent Docker Compose supporting `!reset`. It is synthetic
verification only, not a working sign-in setup. Stop it before starting the normal
pilot stack: both use local 8443/8026. `down` here leaves only this verification
project's synthetic volumes; it never targets the original relay. The smoke test
verifies real certificate-checked HTTPS, anonymous auth rejection, capture network
isolation and the actual adapter → Postfix → Mailpit handoff. It does not replace
the manual authenticated frontend/hosted Supabase test.
