# Frontend and Docker Email Integration

## Purpose

This document records verified progress, proposed architecture, and implementation instructions for the coding agent working in this testing repository.

The existing application files have been copied from another repository. Preserve the original working application and successful relay experiment.

## Instructions for the coding agent

- Read applicable `AGENTS.md` instructions first.
- Confirm this repository is the intended testing repository before editing.
- Respect the current agent mode. This document does not authorize implementation while in Plan mode.
- Do not modify the original repository or its working Docker services.
- Preserve unfamiliar existing changes.
- Do not commit or push without explicit user authorization.
- Do not apply remote database changes without confirming the development target and obtaining authorization.
- Update this document as milestones are actually completed.
- Never describe planned or mocked behavior as verified functionality.

### Website authentication and dashboard tasks

**Do not use the integrated browser to log in to Supabase or any other website.**

Do not automate passwords, OAuth consent, MFA, account recovery, or authenticated dashboard configuration. Do not use an existing logged-in browser session to make dashboard changes.

When website interaction is required:

1. Explain the task and why it is necessary.
2. Ask the user to perform it in their own browser.
3. Provide the official URL, navigation instructions, fields to configure, and expected result.
4. Explain any cost, permission, production, or email-sending consequences.
5. Wait for confirmation or a redacted result.

Research public documentation with read-only tools as needed.

Never ask the user to paste passwords, private keys, access tokens, or complete secrets files into chat. Explain how to enter secrets privately into local/server configuration.

Local UI testing is permitted when authorized, but the user must perform real login and app-password entry.

Existing CLI/MCP authentication does not authorize arbitrary remote changes. Confirm the connected project is the intended development project.

## Requirements

- Support personal Gmail and Google Workspace sending accounts where app passwords are available.
- Recipients must see the customer's actual sending address.
- Initial pilot: approximately 10 users or fewer.
- Basic frontend first; visual design comes later.
- Users connect an account and initiate a single email through the UI.
- SMTP execution and credential handling remain server-side.
- App passwords are session-only for this test.
- Start locally, but make the application deployable centrally for other computers' browsers.
- Retain Postfix unless another approach materially simplifies operation and scaling.

The eventual use case includes unsolicited job outreach. Google previously rejected Gmail API verification for the use case. SMTP authentication success does not override that rejection or Gmail's sending policies.

## Verified progress

The user confirmed:

1. Docker Postfix and Mailpit captured a synthetic email successfully.
2. Mailpit was configured to manually release messages through Gmail SMTP.
3. Gmail initially rejected authentication with `535 5.7.8`.
4. After credential troubleshooting, the user reported success.

The working experiment is:

```text
Synthetic submission → Postfix → Mailpit
                                  ↓ manual release
                              Gmail SMTP → recipient
```

Postfix logs confirmed capture handoff. Real-email success was reported by the user; received authentication headers and deliverability have not been independently inspected.

### Implementation milestone — October 20, 2026

The user confirmed this testing repository, direct Gmail SMTP with Postfix/Mailpit
retained for capture, and development project `gnmimpoeqxeczjhvzrrx`. They chose
manual dashboard setup and a restricted test-owned-recipient pilot, with a future
provider pivot if the actual use case requires it.

Implemented locally:

- `frontend/`: React/TypeScript sign-in, invitation redemption, account connection,
  plain-text compose, exact preview/confirmation, disconnect and durable history.
- `outreach/api/`: single-worker FastAPI, verified Supabase identity/access/session,
  per-owner/Auth-session memory-only connections, 30-minute idle/two-hour maximum
  lifetime, connection throttling and fixed verified-STARTTLS Gmail transport.
- Backend-generated sender headers, expiring content-bound approvals, durable
  claim before SMTP, duplicate protection and conservative finalization/unknown
  handling. A backend HMAC protects pilot database commands, including finish;
  browsers cannot fabricate authoritative pilot outcomes using their JWT alone.
- Additive migration `20261020223515_session_mail_pilot.sql` preserves the original
  migration, legacy behavior/hashes and shared quotas/suppression/recovery. Both
  pilot start and claim enforce verified owner/sender and one test-owned recipient.
  Defaults do not enable live sends. **Not applied remotely.**
- Separate Compose/Caddy HTTPS deployment in `infra/`, private API/SMTP and
  capture-only Postfix/Mailpit with no relay secrets or egress. Published endpoints
  are loopback-only 8443 and 8026. The web proxy has an edge network because Docker
  does not publish ports on internal-only networks in this environment; the mail
  services remain on an internal-only network.
- `MAIL_PILOT_SETUP.md`: user-operated Supabase, keys, Auth, invitation bootstrap,
  local certificate trust, capture and controlled real-email instructions.

Verified in this testing copy:

- API/domain tests cover tampering, cross-user/session connections, revocation,
  duplicate clicks, wrong credentials, expired connections/backend-memory loss,
  failed finalization and ambiguous SMTP outcomes (mocked SMTP).
- Actual PostgreSQL 17 container tests execute both migrations and verify private
  grants, backend signatures, Auth-session existence, sender/recipient rules,
  quota/claim races, unknown holds/recovery, accepted/failed finalization,
  invitation single use and legacy compatibility. Auth tables/JWT claims are
  synthetic fixtures, **not hosted Supabase Auth/PostgREST verification**.
- Real Docker builds and HTTPS proxy requests passed with certificate verification
  using the test stack's public CA, without modifying the host trust store.
- Synthetic message submitted through the actual capture adapter → Postfix →
  isolated Mailpit; captured sender, recipient and body inspected programmatically.
  Internal-only mail networks verified. No external email sent.
- Anonymous frontend rendered in the local browser with synthetic public config;
  no website login, OAuth consent or real password entry was attempted.

Final local checks: **125 Python tests passed** (including 9 real PostgreSQL and
2 real HTTPS/capture smoke tests); **8 frontend tests passed**; frontend typecheck/
build, locked dependency sync, Ruff format/lint, compileall and `git diff --check`
passed. `npm audit` reported zero vulnerabilities. The Python suite emits one
upstream Starlette TestClient/httpx deprecation warning; it does not affect these
results. Verification containers and the synthetic UI preview were stopped after
testing; only the verification project's synthetic named volumes/build cache were
retained. No host CA trust was installed. CI configuration was added but not run
remotely.

Still pending:

- User-operated setup and two real invited sessions on the new hosted project.
- One explicitly user-approved real Gmail message and received authentication
  headers. Live sending remains off by default; no real SMTP credentials were used.
- Production-use/provider policy decision: Gmail prohibits spam and unsolicited
  commercial mail; SMTP is not a bypass for the previous API rejection. See
  `MAIL_PILOT_SETUP.md` for current official limits/policy sources.
- Private Realtime Broadcast (current status is explicit authenticated refetch),
  generalized recipient support, production legal/retention/abuse handling,
  multi-replica credential routing and any Convex migration.

The supplied Compose structure was reviewed and the existing relay directory was
located at `/home/devcontainers/projects/postfix_files` in Ubuntu WSL. Its secret
file was not read, and its files/services/queues/volumes were not modified.
The MCP connection still points to the old Supabase project; it was not used for
database changes. No commits or pushes were made.

## Proposed architecture

Recommended starting point:

- Vite + React + TypeScript frontend.
- Python FastAPI backend in Docker.
- Existing Supabase authentication and database safeguards.
- Private Supabase Realtime Broadcast for status later.
- Temporary backend-memory SMTP credentials.
- Direct backend-to-Gmail SMTP for live submissions.
- Postfix/Mailpit retained for capture/reference testing.

```text
React browser UI
    |
    | HTTPS / authenticated API
    v
Docker FastAPI mail service
    ├── temporary per-user/session credentials
    ├── authorization, validation and orchestration
    ├── live transport → Gmail SMTP → recipient
    └── capture transport → Postfix → Mailpit

Supabase:
    identity, access, quotas, durable attempts, private status updates
```

### Confirm the transport decision before implementation

The user prefers retaining Postfix unless bypassing it provides meaningful benefits.

**Confirmed October 20:** direct live Gmail transport is authorized for the
restricted pilot; preserve Postfix/Mailpit as an isolated capture path.

Direct Gmail SMTP is recommended because session-only credentials do not require shared relay-file updates or Postfix credential-map synchronization. It also provides the immediate upstream result without an intermediate queue.

This is an operational simplification, not a measured increase in throughput.

If Postfix is mandatory for live delivery, explicitly redesign around sender-dependent SASL authentication. Do not silently choose a different architecture.

### Supabase versus Convex

Keep Supabase for the first integration round.

Supabase already provides real-time updates. The current database also implements invitations, quotas, claims, suppression and recovery.

Convex offers integrated reactive queries and TypeScript transactions, but migration requires rebuilding and testing those safeguards. Its serverless function memory is not a dependable session credential vault.

Do not maintain Supabase and Convex as competing permanent sources of truth.

## Existing code to understand

Paths are relative to this copied repository:

| File | Relevant behavior |
|---|---|
| `app.py`, `outreach/ui.py` | Existing Streamlit UI; preserve while adding the new interface. |
| `pyproject.toml`, `uv.lock` | Authoritative Python dependencies; FastAPI is not currently declared. Development uses Python 3.12. |
| `outreach/services/config.py` | Requires one project sender and domain-verification flag. |
| `outreach/services/supabase.py` | Uses the user's JWT and authenticated RPCs, not a service-role key. |
| `outreach/services/smtp.py` | TLS/authenticated SMTP, bounded timeout, failure/unknown classification. |
| `outreach/services/sending.py` | Durable claim before SMTP and finalization afterward. |
| `outreach/domain/batches.py` | Sender-aware MIME generation and exact-content approval digest. |
| `supabase/migrations/202610110001_invite_outreach.sql` | Private schema, access, quotas, claims, suppression and fixed-sender enforcement. |
| `SETUP.md`, `STREAMLIT_LAUNCH.md` | Current deployment assumptions; adapt rather than follow blindly. |

Existing sending is user-driven, one recipient at a time. It is not an automatic background batch system.

## Phase 1 — Establish the integration boundary

### Objective

Build:

```text
Frontend → authenticated Docker API → development Supabase
```

No real sending or real credential entry yet.

### Execution

1. Confirm:
   - Testing repository path.
   - Working relay Compose directory.
   - Existing ports, networks and volumes.
   - Whether existing Supabase user/history data must be preserved.

2. Preserve the successful experiment.
   - Use separate Compose project identity and volumes.
   - Avoid conflicting published ports.
   - Do not delete existing containers, queues or volumes.
   - New integration Mailpit must be capture-only, without Gmail relay credentials.

3. Review copied configuration safely.
   - Do not print `.env` or secrets.
   - Prevent secrets entering Git or Docker build contexts.
   - Do not delete unfamiliar copied files without investigating.

4. Use an isolated development database.
   - Confirm the target before migrations.
   - Ask the user to perform required website setup.
   - Create two synthetic invited users for isolation testing.
   - Keep real sending disabled.

5. Add a separate frontend and API using repository conventions.
   Suggested locations:
   - `frontend/`
   - `outreach/api/`
   - `infra/`

6. Configure a same-origin frontend proxy:
   - `/` serves the frontend.
   - `/api/*` reaches FastAPI.
   - Publish local application endpoints only on loopback.
   - Establish HTTPS before enabling password entry.
   - Keep SMTP and Mailpit administration private.
   - Never mount the Docker socket into the application.

7. Implement application authentication first.
   - Verify Supabase identity and invitation-backed access.
   - Derive user ID/email server-side.
   - Never trust submitted owner IDs.
   - Preserve private-table/RPC boundaries.
   - Do not introduce a privileged database key merely for convenience.

8. Add:
   - Health endpoint.
   - Current-user endpoint.
   - Server-generated draft-preview endpoint.
   - Basic account/compose/status UI.

9. Keep Connect and Send explicitly disabled until implemented.
   - Do not return fictional connection/send success.
   - Do not weaken the real SMTP adapter's TLS checks for capture testing.

### Acceptance

- Frontend reaches Docker API.
- Anonymous, uninvited and revoked users are blocked.
- Two users cannot access each other's data.
- Preview validation happens server-side.
- Capture testing cannot send externally.
- SMTP passwords are not accepted yet.

## Phase 2 — Adapt account and sender rules

### Objective

Replace the fixed project-sender assumption with explicit user-account authorization.

### Execution

1. Separate:
   - Platform configuration.
   - Transport policy.
   - Per-user/session connection data.

2. Preserve the legacy sender mode.
   - Project SMTP still requires project-domain verification.
   - New Gmail mode requires user authorization and a valid backend connection.
   - Never fake `SENDER_DOMAIN_VERIFIED=true` to bypass checks.

3. Initially require:

```text
verified application email
    = connected account
    = SMTP username
    = From
    = envelope sender
    = Reply-To
```

Additional accounts and aliases are outside this first version. Use consistent normalization; do not assume plus/dot variants are interchangeable.

4. Define a safe connection interface:
   - Connection ID.
   - Sending email.
   - Status.
   - Expiry.

Internally bind the connection to owner, application session and backend instance. Use mocked connections in Phase 2.

A submitted `smtp_verified=true` flag is not proof of authentication.

5. Construct sender headers on the backend.
   - Do not accept authoritative `From` headers from the browser.
   - Reuse existing message/domain code.
   - Changing sender or content invalidates approval.
   - Expired connections block; never silently switch accounts.

6. Update database enforcement at both:
   - Batch start.
   - Recipient claim.

The original migration contains fixed-sender checks around lines 188–198 and 245–249; inspect the current copy before editing.

Preserve access checks, atomic quotas, suppression, duplicate protection, claim tokens and recovery.

7. Use additive/versioned compatibility.
   - Consider explicit `project_smtp_v1` and `user_gmail_v1` policies.
   - Do not rewrite historical manifests or approval hashes.
   - Preserve historical batch recovery.
   - Do not rely solely on editing an old migration for initialized databases.
   - Keep shared enforcement logic centralized.

8. Separate trust responsibilities:
   - Database checks verified owner/sender eligibility.
   - Backend checks actual connection ownership, credential availability and expiry.

9. Adapt SMTP credential injection per operation.
   Never switch users by mutating:
   - Global environment variables.
   - Shared adapter credentials.
   - Shared relay YAML.

Preserve TLS, certificate validation, timeouts and conservative outcome classification.

### Acceptance

With mocked SMTP:

- Cross-user senders/connections are rejected.
- Tampered ownership and From values are rejected.
- Sender changes invalidate approval.
- Expired/missing connections block progression.
- Legacy behavior and historical recovery remain valid.
- Existing quota/suppression/duplicate safeguards remain effective.
- Passwords never enter manifests, database records or logs.

## Phase 3 — Session-only SMTP connections

- Implement authenticated connect/status/disconnect.
- Validate Gmail credentials without sending mail.
- Fix upstream to `smtp.gmail.com:587`; require verified STARTTLS.
- Do not accept arbitrary SMTP destinations.
- Store passwords only in backend process memory.
- Proposed inactivity timeout: 30 minutes, plus a maximum lifetime.
- Clear password input after submission.
- Never persist SMTP passwords in browser local/session storage.
- Disable request-body logging and credential-form analytics.
- Restart requires reconnection.
- Disconnect does not revoke the Google app password; explain user-operated revocation.
- Start with one backend process. Multiple replicas require explicit session routing or protected shared ephemeral storage.

## Phase 4 — One controlled real message

- One allowlisted test-owned recipient.
- Plain text; no BCC, attachments, scheduling or bulk sending.
- Exact preview and explicit confirmation.
- Durable intent/claim and duplicate protection before SMTP.
- Bounded execution without blocking the API event loop.
- Distinguish rejected, accepted and unknown.
- Never automatically retry ambiguous submissions.
- SMTP acceptance is not inbox delivery.
- Ask the user to enter real credentials and approve the actual test.

## Phase 5 — Real-time status

- Private owner-authorized Supabase Broadcast channels.
- Minimal safe status payloads, not raw database rows.
- Refetch durable state after reconnect/reload.
- Browser must not finalize authoritative SMTP outcomes.
- Do not expose the private database schema.

## Phase 6 — Portability and scaling

- Reproduce the setup on another development computer.
- Deploy centrally behind HTTPS for customer browsers.
- Customers should not need WSL/Docker.
- Confirm hosting permits outbound SMTP on 587.
- Add health checks, redacted logs, graceful shutdown and recovery.
- Address credential affinity before multiple workers/replicas.
- Do not promise restart recovery of memory-only passwords.
- Defer background sending until credential-lifetime requirements are resolved.

## Relay YAML and secret policy

Do not create a Mailpit relay YAML per customer.

The existing relay configuration is a successful operator experiment, not a multi-user credential system.

- Preserve its secret separately.
- Never use it as a customer fallback.
- Local Compose secrets mount files; they do not encrypt the original host file.
- Do not put passwords in source, images, command arguments, URLs, logs or durable job payloads.
- Future remembered-password support requires separate approval and encrypted recoverable storage with server-only key management.
- Hashing alone cannot support SMTP credentials that must be used later.

If Postfix remains in the live path, plan protected sender-dependent credential maps, no account fallback, expiry cleanup and separate `postfix_queued` versus `google_accepted` reporting.

## Verification

Run existing checks after authorized changes:

```text
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run python -m compileall -q app.py outreach legal.py build_site.py
```

Manage dependencies through `pyproject.toml` and `uv.lock`. Do not mutate installed packages or run the historical Streamlit HTML patch script.

Add frontend typecheck/build/tests once that application exists.

Test actual database authorization and concurrency in an isolated instance. Mocked tests and SQL parsing do not prove real RLS/transaction behavior.

Required cases include:
- Wrong credentials.
- Cross-user connection access.
- Revoked application access.
- Changed sender.
- Duplicate clicks.
- Expired connection.
- Backend restart.
- Failed database finalization.
- Ambiguous SMTP outcome.

## Immediate next actions

1. Follow `MAIL_PILOT_SETUP.md` in the user's own browser to inspect and configure
   **only** development project `gnmimpoeqxeczjhvzrrx`. Stop on unexpected existing
   schema; do not modify the old MCP-connected project.
2. Configure private `infra/.env`, apply reviewed migrations/setup manually and
   establish trusted local HTTPS. No SMTP password goes in these files.
3. Verify two hosted invited users, revocation, isolation and capture UI flow.
4. Only after these gates and user approval, enable both pilot live flags and have
   the user enter their app password and confirm one test-owned-recipient message.
5. Resolve the production use-case/provider-policy decision separately. Do not
   generalize the test-recipient allowlist as a policy workaround.

## Documentation

- Postfix SASL:
  https://www.postfix.org/SASL_README.html
- Mailpit relay:
  https://mailpit.axllent.org/docs/configuration/smtp-relay/
- Supabase Realtime:
  https://supabase.com/docs/guides/realtime/subscribing-to-database-changes
- Convex:
  https://docs.convex.dev/understanding/
- Convex action limitations:
  https://docs.convex.dev/functions/actions
- Docker secrets:
  https://docs.docker.com/compose/how-tos/use-secrets/
- FastAPI containers:
  https://fastapi.tiangolo.com/deployment/docker/
- Google app passwords:
  https://support.google.com/accounts/answer/185833

Verify current documentation during implementation.
