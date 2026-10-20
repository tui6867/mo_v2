# Handoff status — October 12, 2026

## Current session: Streamlit Community Cloud launch preparation

- Re-read PROJECT_CONTEXT.md and this status, checked instructions, clean git
  status, recent commits and remote. Current branch main, HEAD 61c2aa9; origin
  https://github.com/tui6867/mass-outreach-branch.git. Prior implementation is now
  tracked, unlike the October 11 baseline below. No user changes were discarded.
- Owner chose Community Cloud and initially deployment together, then stated
  built-in-browser sign-in is impossible. All account sign-in/deployment/setup
  must be done in their regular browser. Owner explicitly requested **leave
  changes local**: no commit, push, external migration or deployment performed.
- Owner reports an existing project iaubupnvesznnxxerimx connected to GitHub.
  First read-only check: outreach.users/settings/access RPC present. Owner then
  reports full table/RPC checks match but sender/limits/admin setup is missing.
  These are owner reports, not agent-executed database integration checks.
- Supabase dashboard URL supplied is not a Streamlit app URL. Actual Cloud URL,
  Auth redirects/email delivery, verified sender and verified administrator
  configuration remain required.

### Changes (launch scope only)
- Consulted official Streamlit API/reference and Community Cloud dependency,
  deployment, secrets and BaseConnection docs; confirmed uv.lock is supported
  natively. No redundant requirements.txt or fictional deployment REST API added.
- Added .streamlit/config.toml (CORS/XSRF, capped uploads, hidden error details,
  theme) and safe typed .streamlit/secrets.toml.example with blank credentials
  and real sends disabled. No real secrets files were created or inspected by
  tools; credentials were not copied to source or printed.
- Added Streamlit secrets/environment boundary with explicit overrides, typed
  TOML conversion and allowlisted setting names. SMTP uses the same resolved
  settings as the app. Added offline configuration-only preflight command.
- Added official session-scoped st.connection/BaseConnection adapter, requiring
  Streamlit 1.65+. Only HTTP transport is reused; JWT wrappers are fresh per run,
  no tokens/default auth headers, protected results or authorization are cached.
- Replaced radio routing with st.Page/st.navigation and stable legal-page routes.
  Domain modules remain Streamlit/network-free; app.py stays composition only.
- Added tests for TOML/env settings, factory session isolation, changing JWTs,
  safe templates, offline preflight, read-only backend checks and guarded setup.
- Added STREAMLIT_LAUNCH.md and updated readme.md/SETUP.md for the exact target,
  host settings, manual backend/auth/admin setup and release gates.
- Added supabase/launch_checks.sql (SELECT-only, no recipient/secret output) and
  launch_setup.example.sql (operator-only, default guard prevents all writes).
  Existing migrations were not edited or blindly reapplied to the reported schema.

### Verification / remaining work
- Final check commands used the isolated environment by prefixing each uv
  command with `$env:UV_PROJECT_ENVIRONMENT = 'C:\Users\isaia\AppData\Local\Temp\opencode\mass-outreach-streamlit-20261012';`.
  Results on Windows / Python 3.12.5:
  - `uv sync --locked`: passed; 51 resolved, 49 installed packages checked.
  - `uv run ruff format --check .`: passed; 37 Python files formatted.
  - `uv run ruff check .`: passed; no violations.
  - `uv run pytest`: **94 passed in 4.03s**.
  - `uv run python -m compileall -q app.py outreach legal.py build_site.py`: passed.
  - `uv run python build_site.py`: passed; both local legal pages written.
  - `uv run python -m outreach.preflight --secrets-file .streamlit/secrets.toml.example`:
    expected **BLOCKED, exit 1** because template credentials/sender are blank;
    no live backend readiness is claimed.
  - `git diff --check`: passed; only Windows LF/CRLF informational warnings.
- Original .venv contains an inaccessible lib64 link from a different environment;
  uv initially refused to replace it. Kept that environment rather than deleting
  user work; used an isolated approved temporary uv environment for checks/server.
- Local browser verified locked root page and desktop privacy/mobile terms routes.
  No auth/outreach messages, real recipient data or external API tests used.
- Fixed inherited empty sidebar color warnings by declaring explicit theme
  colors; fresh page snapshots had no console problems. Stopped only the local
  test server started in this session (PID 27348, port 8512); existing port 8501
  was not touched. Hosted browser/deployment was not verified.
- A factory-isolation test initially reused AppTest's literal test session ID;
  corrected the harness to assign distinct synthetic session IDs, then verified
  distinct transports and per-request JWTs. No production-session bypass added.
- Still needed: owner push/deploy, actual Cloud URL, Supabase Auth custom SMTP
  (default mail is team-only/rate-limited), confirmed admin UUID and sender domain,
  operator-reviewed quota settings and Cloud secrets, hosted fake-mode checks,
  actual DB authorization/concurrency verification and resolved legal/retention
  placeholders before public service availability. Keep both real-send flags off.

### Owner's next steps
1. Review/commit/push local launch files yourself; deploy main/app.py/Python 3.12
   in a regular browser and obtain the actual .streamlit.app root URL.
2. Configure Supabase Site URL/redirect and auth mail/templates. Its default
   mail service only supports project team addresses at a low rate, so custom
   SMTP is needed before onboarding ordinary invitees.
3. Verify project sender/provider/domain. Obtain a genuinely confirmed admin
   Auth UUID; dashboard/GitHub login is not a project Auth user automatically.
4. Review/fill the guarded launch_setup.example.sql privately and run it as
   operator, keeping DB real sends off. Fill Cloud Secrets from the safe template
   with matching caps/sender/app URL. Never share keys in chat or commit them.
5. Repeat read-only launch checks and hosted fake-mode/auth/authorization checks.
   See STREAMLIT_LAUNCH.md for the detailed walkthrough and remaining release gates.

## Previous session record — October 11, 2026

Branch: `main`. No commits made. Repository baseline and implementation files
are untracked; git status does not provide an original tracked-file diff.

## Baseline / safety
- Read PROJECT_CONTEXT.md, local instructions, historical source, dependency,
  build and devcontainer configuration, and git status before implementation.
- Replaced historical top-level OAuth/billing/public-free app paths. No runtime
  Streamlit package mutation remains. Historical billing.py, patch script and
  Google verification notes stay as inactive artifacts, not imports/dependencies.
- Converted requirements.txt to pyproject.toml + uv.lock. No unrelated user
  changes discarded. Existing .env and credentials were not read or changed.
- No real emails, recipients, deployment, external database migration, SMS,
  payments or external service-state changes were used for testing.

## Completed
- Python 3.11–3.13 declaration, Python 3.12 development/CI; uv lock, pytest/Ruff
  configuration, names-only .env.example, GitHub Actions, locked devcontainer
  build and no CORS/XSRF disabling flags.
- app.py is composition only; outreach/ui.py composes Streamlit with pure
  recipients/templates/batches/outcomes/invitations and service adapters.
- Structured manual/CSV recipients, preview and mapping, mandatory append vs
  replace, Unicode/compound name preservation, explicit-address precedence,
  email-validator normalization (no MX checks), final edited deduplication.
- Exact rendered reviews and content hash including intended recipients in fake
  mode, From/Reply-To/BCC, attachment metadata/content hash and test mode.
- Validated job/URL/placeholders, BCC, attachment format/name/upload and encoded
  MIME size; spreadsheet-safe CSV exports; per-user suppression checks.
- Magic-link authentication, hashed expiring single-use invitations, verified
  UUID ownership, database admin role, revocation and per-operation authorization.
- Migration `supabase/migrations/202610110001_invite_outreach.sql`: private
  outreach schema, users/plans/settings/invitations/outreach_batches/
  recipient_attempts/quota_reservations/suppression_entries/audit_events,
  RLS/no direct table grants, four authenticated public RPCs. Legacy data untouched.
- Atomic globally serialized full-batch reservations; plan_1 default 300 UTC/day,
  batch/global UTC calendar-hour/day caps, required-config fail-closed behavior.
- Provider-independent fake and TLS-only SMTP adapters. Durable submitting
  checkpoint before SMTP, accepted/failed/unknown finalization, Message-ID and
  raw SMTP DATA response storage (including queue identifiers when supplied),
  primary-vs-BCC refusal details, SMTPUTF8 capability checking.
- Duplicate start protection, claim tokens and expected-ordinal click protection;
  one user-driven submission per continuation, cancellation between recipients,
  exact persisted-content recovery, identical attachment reupload, no unknown retry.
- Standalone local privacy/terms HTML build creates its output directory and
  no longer references absent assets or external font services. Shared legal
  drafts accurately label provider/retention/operator/legal placeholders.
- SETUP.md covers deployment commands, config, migration/admin bootstrap,
  Supabase magic-link email template, security and release blockers.

## Actual checks run
Final results on Windows / Python 3.12.5:
- `uv sync --locked` — passed; 51 resolved packages, 49 checked installations.
- `uv run ruff format --check .` — passed; 31 Python files formatted.
- `uv run ruff check .` — passed, no violations.
- `uv run pytest` — **81 passed in 3.91s**. Synthetic domain tests, threaded
  fake reservation/click tests, mocked HTTP/SMTP, Streamlit AppTest, static build.
- `uv run python -m compileall -q app.py outreach legal.py build_site.py` — passed.
- `uv run python build_site.py` — passed; wrote site/privacy.html and site/terms.html.
- SQL parser test: 37 PostgreSQL statements and four PLpgSQL function bodies
  parse. Private composite declarations are replaced with record only for body
  syntax parsing because pglast has no actual schema catalog.
- `git status --short` and `git branch --show-current` — ran; branch main, files
  untracked. Generated site/.venv/cache files are ignored.

Earlier findings corrected: Ruff import/variable/closure violations; AppTest's
three-second initial data-editor load timeout (raised test timeout to 30s).
Raw pglast PLpgSQL parsing cannot resolve the new private composite types; the
syntax-only test explicitly documents its limited substitution. These are not
claims of database integration success.

## Decisions / operational semantics
- Database `is_admin` role, not an email allowlist; bootstrap one verified Auth
  UUID explicitly with operator SQL. No app service-role credential.
- Plan allowance lives in outreach.plans. DB limits/sender settings must be set
  independently; app config can tighten, not expand limits. Real sending needs
  both app and database flags. Missing required settings block starts/sends.
- No automatic bulk loop/background thread: users explicitly continue each
  recipient. Closing the browser stops future actions, not an in-flight SMTP send.
- Count accepted real message submissions, including at most one optional BCC,
  once per message, not per envelope address. No delivery claim is made.
- Unknown outcomes keep conservative holds across time buckets. Never retry
  automatically. Definite failures and pending cancellations release holds.
- Five-minute stale submitting lease covers SMTP timeout (maximum 120 seconds)
  and HTTP persistence time. Recovery needs explicit action and exact reapproval.
- Attachments remain in session memory; persisted metadata/content hash permits
  identical reupload. Exact rendered messages/recipient addresses remain in DB.
- Identical owner/content hashes cannot start twice, even under new batch UUIDs.
- Supabase Auth signup alone grants no product access. Rate limits/auth abuse
  controls must be configured; expired sessions require a new magic link.

## Not production-verified / remaining decisions
1. No PostgreSQL/Docker executables were found; migrations were NOT applied.
   Fake concurrency and parser tests do NOT prove database locking, RLS,
   role grants, catalog resolution, Supabase JWT semantics or cross-user isolation.
2. Actual SMTP provider, domain SPF/DKIM/DMARC/provider verification, credentials,
   provider limits/acceptable-use policy and SMTPUTF8 behavior remain operator tasks.
3. Configure isolated Supabase, email-auth delivery, magic-link template/redirect,
   rate limits, admin bootstrap and quota settings; never enable real sends in tests.
4. Confirm hosting/build commands, log redaction, secrets and backups. No hosted
   browser/auth integration or deployment was performed. AppTest uses mocks.
5. Finalize operator/contact/jurisdiction/legal notices, retention/deletion of
   content/metadata/audit records/provider copies and evidence-based unknown-hold
   reconciliation. No automated deletion or unknown reconciliation UI exists.
6. Historical artifacts remain for reference only; do not follow their old setup.

## Next concrete task
Run the migration in an isolated Supabase project/local stack with fake SMTP;
verify two-session quota races, invitation races/revocation, cross-user denial,
stale recovery and cancellation release. Resolve provider, retention/legal and
hosting configuration before approving production activation.
