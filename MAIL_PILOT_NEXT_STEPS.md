# Current setup: live submission passed; capture-only restored

**Development project:** `gnmimpoeqxeczjhvzrrx`. All three migrations are installed;
**do not rerun them, regenerate the signing key, or repeat the live test**.

## Latest verified checkpoint

- PowerShell and all pilot services work; certificate-verified HTTPS passes.
  Backend/database signing keys match without either secret being exposed.
  After Docker Desktop became unavailable, its connection was restored and only
  this pilot's stopped containers were started. All four are running again;
  API/mail healthchecks and web HTTPS checks pass. Previous Mailpit captures and
  volumes were preserved. No new mail was sent.
- `gamingtui94@gmail.com` is a verified, active administrator.
  `igabbay@binghamton.edu` verified email and redeemed its invitation; it is active
  as a **non-administrator**, restored after the authorized revocation test.
- Both user-operated captures passed database/Mailpit Message-ID, headers and
  approved-body checks. User history isolation passed; cross-owner batch access
  was denied. Revocation blocked the second user's already-open session while
  leaving the administrator working. The redeemed invitation file was removed.
- A real history bug was fixed with additive migration
  `20261021020352_qualify_pilot_history_columns.sql` and regression tests.
- With explicit approval and temporary 1/hour, 1/day limits, the user privately
  connected Gmail, previewed/approved, and submitted **one real email** from
  `gamingtui94@gmail.com` to `leokarpel98@gmail.com`. Actual subject:
  `Mass outreach pilot live test`. Hosted status is **completed / accepted**,
  `user_gmail_v1`, zero quota hold. SMTP acceptance is **not** inbox delivery.
- **Cleanup is verified:** database live gate off; legacy live gate still off;
  `infra/.env` and running API restored to capture/false, caps 5/hour and 10/day.
  API recreated, dropping the in-memory SMTP credential. Exactly one real batch,
  zero submitting attempts and zero total held quota. Second-user access restored
  only after live mode was disabled. No original WSL-relay changes, commits or
  pushes were made.

**Recipient verification unavailable:** the user reported no access to the mailbox
needed for the delivery check and asked to continue. Inbox/Spam delivery and
SPF/DKIM/DMARC are therefore **unverified**, not failed or confirmed. No second
message was sent, and no recipient change was authorized. A future delivery test
requires a separately approved recipient whose mailbox can be inspected.

**Manual credential cleanup remains unconfirmed:** the sending-account owner
should revoke only the dedicated **Mail pilot frontend test** app password in
Google's App Passwords page. Disconnect/recreation does not revoke that credential.
Do not accidentally revoke the separate **Supabase Auth development** credential
while it is still needed for sign-in. Do not post full headers or credentials.
Reload the frontend before its next use to replace any stale Gmail-mode UI; a
fresh sign-in link may be required because Auth tokens are memory-only.

For future sender/recipient changes, use the address-management table in
[MAIL_PILOT_SETUP.md](MAIL_PILOT_SETUP.md#where-sender-and-recipient-addresses-are-managed).
This pilot is not approved for production outreach.

Sections 1–5 are retained as setup/troubleshooting reference. Stop at the first
failure and send only the redacted error. Do not repeatedly request Auth links
or restart services to guess at errors.

## 1. Prepare private configuration

```powershell
Set-Location 'C:\Users\isaia\Documents\mo_v2'
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath '.\infra\.env')) {
    Copy-Item -LiteralPath '.\infra\.env.example' -Destination '.\infra\.env'
}
notepad.exe .\infra\infra.env
notepad.exe .\infra\.env
```

This preserves your existing `infra/infra.env` and any existing `infra/.env`.
Transfer **only** the appropriate project's publishable key from the source
file. Do not transfer a service-role key, SMTP password or another project's URL.
Both filenames are excluded from Git and the Docker build context.

In your own browser, open
<https://supabase.com/dashboard/project/gnmimpoeqxeczjhvzrrx/sql/new>.
Privately run:

```sql
select signing_secret from outreach.mail_settings where singleton;
```

Copy that value directly into `MAIL_SIGNING_SECRET` in **`infra/.env`**. Never
paste the result, filled config, or a screenshot of it into chat. Do not generate
a different local key: the backend and database keys must match. Restrict access
to your dashboard, clipboard and private config.

Ensure these values in `infra/.env` (fill the two private placeholders yourself):

```dotenv
MAIL_SUPABASE_URL=https://gnmimpoeqxeczjhvzrrx.supabase.co
MAIL_SUPABASE_PUBLISHABLE_KEY=YOUR_PROJECT_PUBLISHABLE_KEY
MAIL_SIGNING_SECRET=THE_EXISTING_DATABASE_SIGNING_KEY
MAIL_ORIGIN=https://localhost:8443
MAIL_TEST_RECIPIENT=leokarpel98@gmail.com
MAIL_TRANSPORT=capture
MAIL_ENABLE_REAL_SENDS=false
MAIL_HOURLY_LIMIT=5
MAIL_DAILY_LIMIT=10
```

If the publishable key is missing or belongs to another project, get this
project's `sb_publishable_...` key from its API Keys/Connect page. Do not share it
unnecessarily. Close/save Notepad before continuing.

## 2. Start only this pilot's containers

Start Docker Desktop first, then:

```powershell
docker compose -f infra/compose.yaml up --build -d --wait
docker compose -f infra/compose.yaml ps
```

Expected: `web`, `api`, `postfix`, `mailpit` are running; API and mail services
become healthy. This project is `mo-v2-mail-pilot`; it does not use or modify the
original WSL relay. If 8443/8026 is occupied, report the conflict rather than
stopping unrelated containers. Do not post `docker compose config` output; it
expands private environment values.

## 3. Trust the local HTTPS certificate yourself

This installs a development certificate authority in **your current Windows
user's** trust store. It permits certificates signed by that CA; do this only
on your development machine, restrict access to the Caddy volume and remove the
CA when finished. The agent has not performed this trust-store change.

```powershell
New-Item -ItemType Directory -Force infra/certs | Out-Null
docker compose -f infra/compose.yaml cp web:/data/caddy/pki/authorities/local/root.crt infra/certs/pilot-root.crt
certutil -user -addstore Root infra/certs/pilot-root.crt
```

Open <https://localhost:8443/api/health> in **your own browser**. Expected:
`status: ok`, `transport: capture`, `live_enabled: false`, with **no certificate
warning**. Import the public root manually into your browser's separate trust
store if needed. Never bypass a warning or import the CA's private key.

### If health returns HTTP 502

A Caddy log such as `dial tcp: lookup api: i/o timeout` means the HTTPS request
reached the proxy, but Docker could not resolve the backend service `api`.
It is **not a certificate-trust or Supabase-login error**. Do not reinstall the
CA, disable TLS checks, expose port 8000, or replace `api:8000` with `localhost`:
inside Caddy, `localhost` refers to the web container, not the API.

From the repository root, run these once and share their redacted output:

```powershell
docker compose -f infra/compose.yaml ps -a
docker compose -f infra/compose.yaml logs --tail 50 api
```

An exited API needs its startup error corrected first (for example, missing or
invalid private configuration). If it is healthy, the next check is Docker DNS
and shared-network membership. Do not repeatedly recreate containers or delete
networks/volumes before identifying which case applies. Do not share `.env`,
`docker compose config`, full container-inspection output, or Auth URLs/tokens.

**Confirmed startup failure:** `Publishable key and a private signing secret
(64+ characters) required` means either the publishable-key format is rejected,
the signing secret is shorter than 64 characters, or both. It does not mean a
Supabase request failed: the process stops before contacting Supabase.

Edit **`infra/.env`**, not the root `.env` or the preserved `infra/infra.env`:

- `MAIL_SUPABASE_PUBLISHABLE_KEY`: this development project's actual active
  `sb_publishable_...` key (not the documentation placeholder, a service-role
  key, or a dashboard access token).
- `MAIL_SIGNING_SECRET`: the existing 64-character backend key from the private
  SQL query in section 1. It must match the database exactly. This is **not** a
  Gmail app password; do not invent a replacement key just to satisfy the length.

If needed, this one-shot diagnostic checks only format/length and prints no keys:

```powershell
docker compose -f infra/compose.yaml run --rm --no-deps --entrypoint python api -c "import os; from outreach.api.config import is_public_key; print('publishable_key_format_ok:', is_public_key(os.getenv('MAIL_SUPABASE_PUBLISHABLE_KEY', ''))); print('signing_secret_64_plus:', len(os.getenv('MAIL_SIGNING_SECRET', '')) >= 64)"
```

Both results must be `True`, but that alone does not prove the public key is
active or the private key matches the database. After saving the correct values,
recreate **only the API** to reload its environment (a restart does not reload it):

```powershell
docker compose -f infra/compose.yaml up -d --force-recreate --wait api
docker compose -f infra/compose.yaml ps -a
```

Retry the health URL once. If it still fails, share the new redacted API error,
not the private field values. Leave capture mode and both live-send flags off.

## 4. Configure Auth and verify the first real user

In your own Supabase dashboard:

1. **Authentication → URL Configuration**: Site URL `https://localhost:8443`;
   allow redirect URL `https://localhost:8443`.
2. **Authentication → Email Templates → Magic Link**: normal
   `{{ .ConfirmationURL }}` link. Email provider is already enabled and
   email confirmation is required; keep it that way.
3. Supabase's built-in Auth mail sender restricts recipients to project-team
   addresses. If either test user is outside that set, configure **Auth custom
   SMTP** privately with a provider you control. These are Auth-service
   credentials, **not** a customer's session-only Gmail app password. Review the
   provider's cost before enabling it. Do not disable email verification or
   put a customer's Gmail password into Supabase Auth SMTP as a workaround.
4. At <https://localhost:8443>, request one sign-in link for
   **`gamingtui94@gmail.com`**, then open it yourself. A sign-in email is a real
   service email; this does not send the composed pilot message.
5. The app will initially show that an invitation is required. This is expected:
   verification alone does not grant application access. **Do not create an
   administrator or mark the Auth user confirmed manually.** Tell the agent
   "first email verified"; it can verify that fact through the connector and
   bootstrap that verified account as the administrator.

For this development pilot, the user was instructed to configure their own
operator account as a temporary Auth sender, using a **separate newly generated**
Google app password labelled `Supabase Auth development`:

| Auth SMTP setting | Development value |
| --- | --- |
| Sender email / SMTP username | `gamingtui94@gmail.com` |
| Sender name | `Mass Outreach Dev` |
| Host | `smtp.gmail.com` |
| Port / encryption | `465` / SSL-TLS |
| Password | Dedicated operator-owned Google app password, entered privately in Supabase |

This is **not** the normal Google password, a Supabase key, or a customer's
session-only sending credential. Supabase persists this Auth-service credential;
its separate label does not restrict its mailbox privileges. Do not reuse relay
or frontend passwords. Revoke the dedicated credential after testing and choose
a dedicated transactional provider for production. Google app-password eligibility
and account-wide sending limits still apply. No SMTP password was supplied to or
tested by the agent. A successful verified app sign-in has been observed in Auth;
the exact dashboard SMTP configuration was not independently inspected.

If requesting the link fails, report the displayed error/status once. Inspect
Authentication logs without sharing tokens or link URLs. Do not repeat the
request in a loop. The agent can then diagnose the specific failure.

After bootstrap, sign out and request a fresh sign-in link. Avoid reloading a
signed-in page until needed: Auth tokens are memory-only, and reloading may
require another sign-in. Used magic links cannot be reused.

## 5. Capture and second-user gates

**Completed for both selected users.** The following is the replay checklist, not
an instruction to repeat testing or request another invitation.

Administrator bootstrap is complete. In your own browser, sign out and sign in
with a **fresh** link if the app still shows the old access error. Do not enter an
invitation code for this administrator; it already has application access.

1. Sign in as `gamingtui94@gmail.com`, start a capture session, compose a uniquely
   labelled plain-text test, preview, approve and **Capture one email**.
2. Inspect <http://localhost:8026>: From/Reply-To must be the verified sender;
   To must be `leokarpel98@gmail.com`; verify subject and body. No external mail
   is delivered in capture mode. Report only the subject/status, not credentials.
3. The invitation for **`igabbay@binghamton.edu`** has been redeemed successfully.
   Its private temporary code file was removed. Do not reuse that invitation or
   request another one for this test. Only its hash remains in the database.
4. In a separate browser/profile, verify that second user's own email and redeem
   the invitation. It must see only its own history and connection. Its live
   Gmail eligibility is a **separate** question; an institutional address does
   not by itself prove it is Google Workspace or permits app passwords.
5. Coordinate revoking the second **test** user's application access with the
   agent, then confirm the existing second session cannot send or preview.

Those gates passed and the separately approved one-message Gmail test reached
SMTP acceptance. Both live gates are now off. Any further live sending requires
fresh explicit approval. Never share passwords, JWTs, magic links or invitation
codes in chat.

For optional regression commands and live-test instructions, see
[MAIL_PILOT_SETUP.md](MAIL_PILOT_SETUP.md), sections 5–7. After PowerShell recovered,
the current run passed **125 Python tests**, including the eleven disposable real
PostgreSQL tests, plus **8 frontend tests**, typecheck/build and Ruff checks.
These suites were rerun successfully after Docker connectivity recovered. The
deployed history function also exactly matches the local migration body. The two
synthetic-verification-stack smoke tests were skipped because this
operator's running stack occupies their fixed ports; equivalent HTTPS, anonymous
access/origin rejection and synthetic capture checks passed against the running
stack without stopping it. The runtime frontend matches the fresh local build.
The user-operated authenticated frontend tests in section 5 also passed.
