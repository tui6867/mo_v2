-- OPERATOR TEMPLATE, NOT A MIGRATION AND NOT RUN BY THE APP.
-- Copy into SQL Editor only after launch_checks.sql matches.
-- Fill in the three values below privately. Never put real values in GitHub.
-- Default values deliberately RAISE before any write.
-- Verify sender SPF/DKIM/DMARC/provider approval and genuine email control first.

begin;
do $$
declare
  verified_admin_id uuid := null;       -- Replace null with 'your-auth-uuid'::uuid.
  project_sender text := '';            -- Replace with your verified project sender.
  domain_is_verified boolean := false;  -- Set true ONLY after actual verification.
  confirmed_email text;
begin
  if verified_admin_id is null or project_sender = '' or not domain_is_verified then
    raise exception 'Fill verified admin UUID and verified project sender before running';
  end if;
  if project_sender !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
    raise exception 'Invalid project sender';
  end if;
  select lower(email) into confirmed_email from auth.users
    where id=verified_admin_id and email_confirmed_at is not null;
  if confirmed_email is null then
    raise exception 'Admin must have verified email control through Supabase Auth';
  end if;
  if exists(select 1 from outreach.users where id=verified_admin_id
            and (not active or lower(email)<>confirmed_email)) then
    raise exception 'Existing user is revoked or email differs; requires explicit reconciliation';
  end if;
  if not exists(select 1 from outreach.settings where singleton) then
    raise exception 'Database settings row missing; reconcile migration first';
  end if;

  update outreach.settings
    set batch_limit=50, global_hourly_limit=100, global_daily_limit=300,
        sender_email=project_sender, sender_domain_verified=true,
        real_sends_enabled=false
    where singleton;
  insert into outreach.users(id,email,is_admin)
    values(verified_admin_id,confirmed_email,true)
    on conflict(id) do update set is_admin=true;
  insert into outreach.audit_events(actor_id,event,object_id)
    values(verified_admin_id,'administrator_bootstrap',verified_admin_id);
end $$;
commit;
