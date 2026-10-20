-- READ-ONLY: run in Supabase SQL Editor as an operator. No data changes,
-- credentials, account emails, invitation tokens, recipients or message bodies.
-- Expected tables: present/RLS true, direct anon/user table/schema access false.
-- Expected RPCs: security definer, search_path=pg_catalog, auth true, anon false.

select expected.name, to_regclass('outreach.' || expected.name) is not null as present
from (values ('users'), ('plans'), ('settings'), ('invitations'),
             ('outreach_batches'), ('recipient_attempts'), ('quota_reservations'),
             ('suppression_entries'), ('audit_events')) as expected(name);

select c.relname as table_name, c.relrowsecurity as rls_enabled,
       has_table_privilege('anon', c.oid, 'SELECT,INSERT,UPDATE,DELETE') as anon_direct_access,
       has_table_privilege('authenticated', c.oid, 'SELECT,INSERT,UPDATE,DELETE') as user_direct_access
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='outreach' and c.relkind='r'
order by c.relname;

select has_schema_privilege('anon','outreach','USAGE') as anon_private_schema_access,
       has_schema_privilege('authenticated','outreach','USAGE') as user_private_schema_access;

select p.proname as function_name,
       p.prosecdef as security_definer,
       p.proconfig as function_settings,
       has_function_privilege('anon',p.oid,'EXECUTE') as anon_execute,
       has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_execute
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.proname in
  ('outreach_access','issue_invitation','redeem_invitation','outreach_action')
order by p.proname;

select expected.column_name,
       exists(select 1 from information_schema.columns c
              where c.table_schema='outreach' and c.table_name='recipient_attempts'
                and c.column_name=expected.column_name) as present
from (values ('claim_token'), ('provider_id'), ('provider_response')) as expected(column_name);

select name, daily_limit from outreach.plans where name='plan_1';

select batch_limit, global_hourly_limit, global_daily_limit,
       sender_email is not null and sender_email<>'' as sender_configured,
       sender_domain_verified, real_sends_enabled
from outreach.settings where singleton;

-- Counts only: admin email/UUID must be checked privately in the dashboard.
select count(*) as active_verified_admins
from outreach.users u join auth.users a on a.id=u.id
where u.active and u.is_admin and a.email_confirmed_at is not null
  and lower(u.email)=lower(a.email);
