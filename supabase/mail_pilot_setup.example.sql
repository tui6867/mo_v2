-- OPERATOR ONLY. New development project gnmimpoeqxeczjhvzrrx ONLY.
-- Copy to ignored infra/mail_setup.private.sql before filling secrets privately.
-- Apply both migrations first. This script refuses all writes until edited.
do $$
declare
  approve_development_setup boolean := false;
  confirmed_project_ref text := '';
  backend_signing_secret text := '';
  test_owned_recipient text := '';
  verified_admin_id uuid := null;
begin
  if not approve_development_setup or confirmed_project_ref <> 'gnmimpoeqxeczjhvzrrx'
    or length(backend_signing_secret)<64 or test_owned_recipient !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
    or verified_admin_id is null then
    raise exception 'Review the target and fill all development setup fields privately';
  end if;
  if not exists(select 1 from auth.users where id=verified_admin_id and email_confirmed_at is not null) then
    raise exception 'Create and verify the application Auth user before administrator bootstrap';
  end if;
  insert into outreach.users(id,email,is_admin)
    select id,lower(email),true from auth.users where id=verified_admin_id
    on conflict(id) do update set is_admin=true;
  -- No fake domain-verification flag or fixed sender is needed for the user-account policy.
  update outreach.settings set batch_limit=1,global_hourly_limit=5,global_daily_limit=10
    where singleton;
  update outreach.mail_settings set signing_secret=backend_signing_secret,
    test_recipient=lower(test_owned_recipient),capture_enabled=true,live_enabled=false,
    hourly_limit=5,daily_limit=10 where singleton;
end $$;

-- SELECT-only readiness output. Do not output the signing secret or Auth tokens.
select capture_enabled,live_enabled,(signing_secret is not null) as signing_key_configured,
  (test_recipient is not null) as recipient_configured,hourly_limit,daily_limit
from outreach.mail_settings;
