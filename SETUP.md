# Mass Outreach — invite-only release

For the first **Streamlit Community Cloud** launch, follow
[STREAMLIT_LAUNCH.md](STREAMLIT_LAUNCH.md). Repository: tui6867/mass-outreach-branch;
branch main; app.py; select Python 3.12. The official host supports uv.lock directly.

## Local checks (no live sending)
Supported Python: 3.11–3.13; development/CI uses 3.12. Install uv, then:
```
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run python -m compileall -q app.py outreach legal.py build_site.py
uv run python build_site.py
uv run streamlit run app.py
```
Do not import the historical app in tests. Tests use synthetic example.com
addresses, fake stores, HTTP mock transports and mocked SMTP. They make no live
sends. SQL contract tests and a locked in-memory concurrency model are NOT real
PostgreSQL integration tests. pglast validates SQL/PLpgSQL syntax only (private
composite declaration types are substituted with record for parser-only checks).
Streamlit AppTest covers fail-closed/login/exact preview using mocked services.
Validate migrations/RPCs/RLS with two concurrent
authenticated sessions in an isolated Supabase instance before release.

## Hosting
Use a Streamlit-compatible host supporting Python and uv. Build:
`uv sync --locked --no-dev`. Start:
`uv run --no-sync streamlit run app.py --server.address 0.0.0.0 --server.port <HOST_PORT>`.
Do not run patch_streamlit_html.py; installed packages are never mutated.
Community Cloud installs the existing uv.lock directly; no custom build or
requirements.txt is needed. Other hosts that require requirements.txt need a
separately reviewed build configuration. Keep pyproject/uv.lock authoritative.
Configure environment variables through the host's secret store; .env.example
lists names only, not a directly loadable dotenv file. The app does not load .env.
For Community Cloud, paste the filled `.streamlit/secrets.toml.example` template
into Cloud Secrets. The app reads `st.secrets`, supports TOML booleans/integers
and honors explicit environment overrides. Never commit the real secrets.toml.

## Supabase database / access
Apply `supabase/migrations/202610110001_invite_outreach.sql` through an operator's
normal migration process after testing locally. Nothing here applies it for you.
The migration creates a private `outreach` schema and public authenticated RPCs.
It does not modify/delete the historical public users/phones/billing data.
Tables: users (auth UUID ownership), plans, settings, invitations,
outreach_batches, recipient_attempts, quota_reservations, suppression_entries,
audit_events. Private tables have RLS and no authenticated direct DML grants.
Do not expose the private schema through PostgREST or grant client table access.

Set database settings explicitly with operator SQL (substitute your values):
```
update outreach.settings set
  batch_limit = <LIMIT>, global_hourly_limit = <LIMIT>,
  global_daily_limit = <LIMIT>, sender_email = '<VERIFIED_PROJECT_SENDER>',
  sender_domain_verified = true, real_sends_enabled = false;
-- plan_1 starts at 300/day; configurable in the database, not a browser setting:
update outreach.plans set daily_limit = 300 where name = 'plan_1';
```
Null required database settings block batch starts. App configuration can only
tighten DB limits, not expand them. Never enable real sends until SMTP service,
domain authentication, acceptable-use and deployment checks are complete.

Admin authorization uses a database `is_admin` role. Bootstrap a previously
verified Supabase Auth user by inserting their auth UUID and normalized email
into outreach.users with is_admin=true using operator SQL. Never bootstrap by
an unverified submitted email. Admin UI issues random single-use invitations
(only SHA-256 hashes stored), sets expiry and revokes invitations or users.
Deliver invitation secrets privately. No automatic invitation mailing exists.
Revoking an invitation prevents redemption; revoke the user separately to end
already redeemed access. A new invite never silently reactivates revoked users.

## Magic-link authentication
Configure Supabase email auth, auth-email SMTP/rate limits and exact allowed
redirect URL. Disable unused providers. Configure the Supabase magic-link
email template confirmation URL as:
`{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=email`.
The app verifies token_hash with Supabase, immediately clears query parameters,
checks confirmed email and exchanges the invitation secret after login.
Configure proxy/hosting logs to redact auth query strings. Auth signup alone
does not grant application access: all protected RPCs check verified UUID,
invitation-backed active account, ownership and role. Supabase public auth
endpoints themselves can create uninvited Auth accounts; configure rate limits
and CAPTCHA/provider abuse controls before production. These accounts have no
product data/sending access. Session JWTs stay in server session memory; no
service-role key is needed or accepted by the app. Expired sessions require a
fresh login; refresh tokens are not persisted. Sign-out clears all session data.

## Environment variables
Required, including in fake mode (fail closed on missing/invalid values):
- SUPABASE_URL: HTTPS project URL; SUPABASE_ANON_KEY: publishable/anon key.
- AUTH_REDIRECT_URL: exact HTTPS application return URL.
- SENDER_EMAIL: normalized project-controlled email; SENDER_DOMAIN_VERIFIED:
  literal true, only after operator verifies SPF/DKIM/DMARC and provider domain.
- BATCH_LIMIT, GLOBAL_HOURLY_LIMIT, GLOBAL_DAILY_LIMIT: positive integers,
  no fallback to unlimited. Database settings are authoritative.
- MAX_ATTACHMENT_BYTES, MAX_MESSAGE_BYTES, MAX_CSV_BYTES: positive byte limits;
  message limit includes MIME overhead and reserved Message-ID header overhead.
- ENABLE_REAL_SENDS: optional; only true permits real mode in the app. Also
  requires DB real_sends_enabled=true. Defaults to false, not unrestricted use.

For real SMTP: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
SMTP_TLS_MODE (starttls or ssl; no plaintext), SMTP_TIMEOUT_SECONDS (positive,
at most 120). Configure credentials only on server. No real test-send option:
test mode always uses FakeAdapter, actual To is the verified user and BCC is
disabled. Fake acceptance does not mean any email was sent.

## Quotas and sending/recovery
Plan 1 starts at 300 accepted real SMTP submissions per UTC day. Each submitted
message counts once, including its optional single BCC envelope copy; not per
envelope recipient. BCC suppression is checked too. Both project-wide UTC
calendar-hour and UTC-day limits apply (not rolling windows).
Batch start reserves the full count atomically using one transaction-scoped
global advisory lock. Concurrent starts cannot overspend. Reservations from
any previous period remain conservatively held so crossing midnight/hour
cannot bypass limits. Definite failures and unattempted cancellations release
holds. Acceptance consumes the hold and counts at finalization time. Unknown
keeps a hold, not an accepted count. Operator reconciliation requires provider
evidence; no automated unknown retry or reconciliation interface exists.

Approval hashes normalized selected addresses (including intended recipients
in fake mode), exact rendered content, From, Reply-To, BCC, mode and attachment
name/type/size/content SHA-256. Hash changes require renewed review. A unique
owner/hash and per-recipient claim token prevent duplicate start/send clicks.
Each continuation includes its expected ordinal, so replaying a completed click
cannot silently submit the next recipient. Identical batches cannot be started again, even with a new UUID; use a genuinely
new draft rather than working around this safety constraint.

Sending is session-bound: start/reserve, then explicitly submit the next
recipient. There is no background queue, thread or automatic all-recipient
loop. Users can cancel between recipients. Closing the browser prevents the
next user-driven submission, but cannot abort an in-flight SMTP transaction.
Checkpoints are persisted before submission and finalized afterward. SMTP
timeout/disconnection after submission begins yields unknown. A finalization
failure leaves submitting; after a five-minute lease, explicit recovery marks
it unknown. Never retry those messages automatically. Completed outcomes are
stored with the generated Message-ID and the SMTP DATA response when supplied
(including any provider queue identifier); these are not delivery evidence.
Outcomes are durable. Recovery displays the stored exact rendered batch; reapprove it and
reupload the identical attachment to continue only not_attempted recipients;
use cancellation to release unused
holds if that draft cannot be recovered. Logs are exportable without restoring
attachments. No guarantee of exactly-once sending or recipient delivery.

## Security / release decisions
Manual and UTF-8 CSV recipients retain names/emails and row provenance. Explicit
emails override guesses; malformed explicit emails block selection. CSV headers
are previewed/mapped and append/replace is mandatory. Final edited addresses
are normalized/deduplicated with email-validator, without MX checks. Names are
not stripped/transliterated. Unicode addresses require provider SMTPUTF8.
Attachment checks require PDF signature or DOCX container, safe filename,
uploaded size, expanded DOCX size and encoded message size; not malware scanning.
Streamlit text/code/data displays escape untrusted content. CSV export prefixes
formula-like cells. Suppression entries are per-user, not global opt-outs.

Before release: verify migration execution and RLS/RPC cross-user isolation,
invitation race/expiry/revocation, simultaneous quota reservations, interruption
and quota release with an isolated database and fake SMTP. Select actual
non-Google SMTP provider and authenticated domain; configure hosting secrets,
Supabase redirect/auth-email delivery and rate limits; decide retention and
deletion (including stuck holds), backups, logging/redaction and legal notices.
legal.py contains visible placeholders, not finalized legal promises.
build_site.py produces local privacy/terms HTML, not deployment or a complete
homepage. Historical billing.py, Google verification notes, and package patch
script remain only as inactive artifacts; they are not imported by the app or
included in checks. Do not follow their old deployment instructions.
