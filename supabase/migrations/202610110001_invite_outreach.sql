-- New private schema: legacy public users/phones and billing records are untouched.
create schema if not exists outreach;
revoke all on schema outreach from public, anon, authenticated;

create table outreach.plans (
  name text primary key,
  daily_limit integer not null check (daily_limit > 0)
);
insert into outreach.plans values ('plan_1', 300);

create table outreach.settings (
  singleton boolean primary key default true check (singleton),
  batch_limit integer check (batch_limit > 0),
  global_hourly_limit integer check (global_hourly_limit > 0),
  global_daily_limit integer check (global_daily_limit > 0),
  sender_email text,
  sender_domain_verified boolean not null default false,
  real_sends_enabled boolean not null default false
);
insert into outreach.settings(singleton) values (true);

create table outreach.users (
  id uuid primary key references auth.users(id),
  email text not null,
  plan text not null default 'plan_1' references outreach.plans(name),
  active boolean not null default true,
  is_admin boolean not null default false,
  created_at timestamptz not null default now()
);
create table outreach.invitations (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  token_hash text not null unique check (token_hash ~ '^[a-f0-9]{64}$'),
  issuer uuid not null references outreach.users(id),
  expires_at timestamptz not null,
  redeemed_at timestamptz,
  redeemed_by uuid references auth.users(id),
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create table outreach.outreach_batches (
  id uuid primary key,
  owner_id uuid not null references outreach.users(id),
  content_hash text not null check (content_hash ~ '^[a-f0-9]{64}$'),
  manifest jsonb not null,
  test_mode boolean not null,
  status text not null default 'started' check (status in ('started', 'completed', 'cancelled')),
  created_at timestamptz not null default now(),
  unique(owner_id, content_hash)
);
create table outreach.recipient_attempts (
  batch_id uuid not null references outreach.outreach_batches(id),
  ordinal integer not null check (ordinal >= 0),
  email text not null,
  state text not null default 'not_attempted'
    check (state in ('not_attempted', 'submitting', 'accepted', 'failed', 'unknown')),
  detail text not null default '',
  provider_id text,
  provider_response text,
  claim_token uuid,
  updated_at timestamptz not null default now(),
  primary key(batch_id, ordinal)
);
create table outreach.quota_reservations (
  batch_id uuid primary key references outreach.outreach_batches(id),
  owner_id uuid not null references outreach.users(id),
  held integer not null check (held >= 0),
  created_at timestamptz not null default now()
);
create table outreach.suppression_entries (
  owner_id uuid not null references outreach.users(id),
  email text not null,
  created_at timestamptz not null default now(),
  primary key(owner_id, email)
);
create table outreach.audit_events (
  id bigint generated always as identity primary key,
  actor_id uuid references auth.users(id),
  event text not null,
  object_id uuid,
  created_at timestamptz not null default now()
);
create index on outreach.recipient_attempts(updated_at) where state = 'accepted';
create index on outreach.outreach_batches(owner_id);
create index on outreach.quota_reservations(owner_id);

-- Private tables have no browser/user DML grants. RLS is defense in depth;
-- access is exclusively through the authenticated SECURITY DEFINER functions below.
alter table outreach.users enable row level security;
alter table outreach.invitations enable row level security;
alter table outreach.outreach_batches enable row level security;
alter table outreach.recipient_attempts enable row level security;
alter table outreach.quota_reservations enable row level security;
alter table outreach.suppression_entries enable row level security;
alter table outreach.audit_events enable row level security;
alter table outreach.plans enable row level security;
alter table outreach.settings enable row level security;

create function public.outreach_access() returns jsonb
language plpgsql security definer set search_path = pg_catalog as $$
declare u outreach.users; allowance integer; used integer; held integer;
begin
  select a.* into u from outreach.users a join auth.users b on b.id = a.id
    where a.id = auth.uid() and a.active and b.email_confirmed_at is not null
      and lower(a.email) = lower(b.email);
  if u.id is null then raise exception 'Invitation required or access revoked'; end if;
  select daily_limit into allowance from outreach.plans where name = u.plan;
  select count(*) into used from outreach.recipient_attempts a
    join outreach.outreach_batches b on b.id = a.batch_id
    where b.owner_id = u.id and not b.test_mode and a.state = 'accepted'
      and a.updated_at >= date_trunc('day', now() at time zone 'UTC') at time zone 'UTC';
  select coalesce(sum(r.held),0) into held from outreach.quota_reservations r where r.owner_id = u.id;
  return jsonb_build_object('id',u.id,'email',u.email,'plan',u.plan,'is_admin',u.is_admin,
                           'daily_limit',allowance,'accepted_today',used,'held',held,
                           'remaining',greatest(0,allowance-used-held));
end $$;

create function public.issue_invitation(invited_email text, secret_hash text, expires timestamptz)
returns uuid language plpgsql security definer set search_path = pg_catalog as $$
declare actor jsonb; result uuid;
begin
  actor := public.outreach_access();
  if not (actor->>'is_admin')::boolean then raise exception 'Administrator required'; end if;
  if expires <= now() or invited_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
    raise exception 'Invalid invitation email or expiry'; end if;
  insert into outreach.invitations(email,token_hash,issuer,expires_at)
    values(lower(invited_email),secret_hash,auth.uid(),expires) returning id into result;
  insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'invitation_issued',result);
  return result;
end $$;

create function public.redeem_invitation(secret_hash text) returns jsonb
language plpgsql security definer set search_path = pg_catalog as $$
declare invited outreach.invitations; verified_email text;
begin
  select lower(email) into verified_email from auth.users
    where id = auth.uid() and email_confirmed_at is not null;
  if verified_email is null then raise exception 'Verified authentication required'; end if;
  select * into invited from outreach.invitations where token_hash = secret_hash for update;
  if invited.id is null or invited.email <> verified_email or invited.expires_at <= now()
    or invited.revoked_at is not null or invited.redeemed_at is not null then
    raise exception 'Invitation invalid, expired, revoked, already used or for another address'; end if;
  -- Do not let a second invitation silently reactivate a revoked account.
  if exists(select 1 from outreach.users where id=auth.uid() and not active) then
    raise exception 'Access revoked; contact administrator'; end if;
  insert into outreach.users(id,email) values(auth.uid(),verified_email) on conflict(id) do nothing;
  update outreach.invitations set redeemed_at=now(),redeemed_by=auth.uid() where id=invited.id;
  insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'invitation_redeemed',invited.id);
  return public.outreach_access();
end $$;

-- Global serialization is intentionally simple for the first 300/day tier.
-- All starts and finalizations use the same transaction-scoped advisory lock.
-- Accepted real submissions count; failed/unattempted release holds; unknown
-- retains a hold indefinitely until an operator reconciles actual provider evidence.
create function public.outreach_action(operation text, target_batch uuid default null, payload jsonb default '{}')
returns jsonb language plpgsql security definer set search_path = pg_catalog as $$
declare actor jsonb; b outreach.outreach_batches; settings outreach.settings;
  n integer; user_limit integer; user_used integer; hour_used integer; day_used integer;
  user_held integer; global_held integer; r outreach.recipient_attempts; result jsonb;
  manifest jsonb; test boolean; claim uuid; outcome text;
begin
  actor := public.outreach_access();
  if operation = 'suppressions' then
    return coalesce((select jsonb_agg(jsonb_build_object('email',email)) from outreach.suppression_entries
      where owner_id=auth.uid()),'[]');
  elsif operation = 'suppress' then
    if payload->>'email' !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then raise exception 'Invalid suppression email'; end if;
    insert into outreach.suppression_entries(owner_id,email) values(auth.uid(),lower(payload->>'email')) on conflict do nothing;
    insert into outreach.audit_events(actor_id,event) values(auth.uid(),'suppression_added');
    return 'true';
  elsif operation in ('revoke_invitation','revoke_user') then
    if not (actor->>'is_admin')::boolean then raise exception 'Administrator required'; end if;
    if operation='revoke_invitation' then
      update outreach.invitations set revoked_at=now() where id=(payload->>'id')::uuid;
    else
      update outreach.users set active=false where id=(payload->>'id')::uuid;
    end if;
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),operation,(payload->>'id')::uuid);
    return 'true';
  elsif operation = 'list' then
    return coalesce((select jsonb_agg(x) from (select id,content_hash,status,test_mode,created_at
      from outreach.outreach_batches where owner_id=auth.uid() order by created_at desc limit 50) x),'[]');
  end if;
  perform pg_advisory_xact_lock(610110001);
  -- Recheck after waiting for the serialization lock (including access revocation).
  actor := public.outreach_access();
  if operation = 'start' then
    select * into settings from outreach.settings where singleton;
    if settings.batch_limit is null or settings.global_hourly_limit is null or settings.global_daily_limit is null
      or settings.sender_email is null or not settings.sender_domain_verified then
      raise exception 'Required database sending configuration missing; sending disabled'; end if;
    manifest := payload->'manifest';
    test := (manifest->>'test_mode')::boolean;
    if test is null or (not test and not settings.real_sends_enabled) then raise exception 'Real sending disabled'; end if;
    if lower(manifest->>'sender') is distinct from lower(settings.sender_email)
      or lower(manifest->>'reply_to') is distinct from lower(actor->>'email') then
      raise exception 'Sender or verified Reply-To mismatch'; end if;
    n := jsonb_array_length(manifest->'messages');
    if n is null or n < 1 or n > least(settings.batch_limit,(payload->>'batch_limit')::integer)
      or (payload->>'batch_limit')::integer is null then raise exception 'Batch limit exceeded or missing'; end if;
    if jsonb_array_length(manifest->'bcc') > 1 or (test and jsonb_array_length(manifest->'bcc') <> 0) then raise exception 'Invalid BCC'; end if;
    if exists(select 1 from jsonb_array_elements(manifest->'messages') m
      where m->>'to' is null or m->>'to' !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
        or (test and lower(m->>'to')<>lower(actor->>'email'))
        or exists(select 1 from outreach.suppression_entries s where s.owner_id=auth.uid() and s.email=lower(m->>'to')))
      or exists(select 1 from jsonb_array_elements_text(manifest->'bcc') as copies(email)
        join outreach.suppression_entries s on s.email=lower(copies.email) and s.owner_id=auth.uid()) then
      raise exception 'Invalid, non-self test recipient or suppressed recipient'; end if;
    if not test then
      user_limit := (actor->>'daily_limit')::integer;
      select count(*) filter(where b.owner_id=auth.uid() and a.updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'),
        count(*) filter(where a.updated_at>=date_trunc('hour',now() at time zone 'UTC') at time zone 'UTC'),
        count(*) filter(where a.updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC')
        into user_used,hour_used,day_used from outreach.recipient_attempts a join outreach.outreach_batches b on b.id=a.batch_id
        where not b.test_mode and a.state='accepted';
      select coalesce(sum(held) filter(where owner_id=auth.uid()),0),coalesce(sum(held),0)
        into user_held,global_held from outreach.quota_reservations;
      if user_used+user_held+n > user_limit then raise exception 'Per-user UTC daily allowance exceeded'; end if;
      if (payload->>'global_hourly')::integer is null or (payload->>'global_daily')::integer is null
        or hour_used+global_held+n > least(settings.global_hourly_limit,(payload->>'global_hourly')::integer)
        or day_used+global_held+n > least(settings.global_daily_limit,(payload->>'global_daily')::integer) then
        raise exception 'Application hourly/daily allowance exceeded or missing'; end if;
    end if;
    insert into outreach.outreach_batches(id,owner_id,content_hash,manifest,test_mode)
      values(target_batch,auth.uid(),payload->>'content_hash',manifest,test);
    insert into outreach.recipient_attempts(batch_id,ordinal,email)
      select target_batch,(ordinality-1)::integer,value->>'to' from jsonb_array_elements(manifest->'messages') with ordinality;
    insert into outreach.quota_reservations(batch_id,owner_id,held) values(target_batch,auth.uid(),case when test then 0 else n end);
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'batch_started',target_batch);
    return jsonb_build_object('id',target_batch);
  end if;
  select * into b from outreach.outreach_batches where id=target_batch and owner_id=auth.uid() for update;
  if b.id is null then raise exception 'Batch not found or unauthorized'; end if;
  if operation = 'get' then
    return jsonb_build_object('manifest',b.manifest,'content_hash',b.content_hash,'status',b.status);
  elsif operation = 'log' then
    return coalesce((select jsonb_agg(jsonb_build_object('ordinal',ordinal,'email',email,'state',state,
      'detail',detail,'provider_id',provider_id,'provider_response',provider_response,'updated_at',updated_at,'test_mode',b.test_mode) order by ordinal)
      from outreach.recipient_attempts where batch_id=b.id),'[]');
  elsif operation = 'claim' then
    if b.status <> 'started' or b.content_hash is distinct from payload->>'content_hash' then raise exception 'Batch stopped or content changed'; end if;
    if exists(select 1 from outreach.recipient_attempts where batch_id=b.id and state='submitting') then
      raise exception 'A submission is already in progress; recover only after its lease expires'; end if;
    select * into settings from outreach.settings where singleton;
    if settings.batch_limit is null or settings.global_hourly_limit is null or settings.global_daily_limit is null
      or not settings.sender_domain_verified or lower(settings.sender_email) is distinct from lower(b.manifest->>'sender')
      or lower(b.manifest->>'reply_to') is distinct from lower(actor->>'email')
      or (not b.test_mode and not settings.real_sends_enabled) then raise exception 'Sending configuration unavailable'; end if;
    select * into r from outreach.recipient_attempts where batch_id=b.id and state='not_attempted' order by ordinal limit 1 for update;
    if r.batch_id is null then return null; end if;
    -- A repeated click must not silently advance to the following recipient.
    if r.ordinal is distinct from (payload->>'expected_ordinal')::integer then return null; end if;
    if not b.test_mode then
      select count(*) filter(where batches.owner_id=auth.uid() and a.updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'),
        count(*) filter(where a.updated_at>=date_trunc('hour',now() at time zone 'UTC') at time zone 'UTC'),
        count(*) filter(where a.updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC')
        into user_used,hour_used,day_used from outreach.recipient_attempts a join outreach.outreach_batches batches on batches.id=a.batch_id
        where not batches.test_mode and a.state='accepted';
      select coalesce(sum(held) filter(where owner_id=auth.uid()),0),coalesce(sum(held),0)
        into user_held,global_held from outreach.quota_reservations;
      if user_used+user_held > (actor->>'daily_limit')::integer
        or hour_used+global_held > settings.global_hourly_limit
        or day_used+global_held > settings.global_daily_limit then
        raise exception 'Sending limits changed; cancel pending reservations before continuing'; end if;
    end if;
    if exists(select 1 from outreach.suppression_entries s where s.owner_id=auth.uid() and
      (s.email=lower(r.email) or s.email in (select lower(value) from jsonb_array_elements_text(b.manifest->'bcc')))) then
      raise exception 'Recipient or BCC suppressed'; end if;
    claim := gen_random_uuid();
    update outreach.recipient_attempts set state='submitting',claim_token=claim,updated_at=now() where batch_id=b.id and ordinal=r.ordinal;
    return jsonb_build_object('ordinal',r.ordinal,'claim_token',claim);
  elsif operation = 'finish' then
    outcome := payload->>'state';
    if outcome not in ('accepted','failed','unknown') or outcome is null then raise exception 'Invalid outcome'; end if;
    select * into r from outreach.recipient_attempts where batch_id=b.id and ordinal=(payload->>'ordinal')::integer for update;
    if r.batch_id is null or r.state is distinct from 'submitting' or r.claim_token is null
      or r.claim_token is distinct from (payload->>'claim_token')::uuid then raise exception 'Invalid claim'; end if;
    update outreach.recipient_attempts set state=outcome,detail=left(payload->>'detail',500),provider_id=payload->>'provider_id',
      provider_response=left(payload->>'provider_response',500),updated_at=now()
      where batch_id=b.id and ordinal=r.ordinal;
    if not b.test_mode and outcome in ('accepted','failed') then
      update outreach.quota_reservations set held=held-1 where batch_id=b.id;
    end if;
    if not exists(select 1 from outreach.recipient_attempts where batch_id=b.id and state in ('not_attempted','submitting')) then
      update outreach.outreach_batches set status='completed' where id=b.id;
    end if;
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'submission_'||outcome,b.id);
    return 'true';
  elsif operation = 'recover' then
    update outreach.recipient_attempts set state='unknown',detail='Interrupted submission: no automatic retry',updated_at=now()
      where batch_id=b.id and state='submitting' and updated_at < now()-interval '5 minutes';
    if exists(select 1 from outreach.recipient_attempts where batch_id=b.id and state='submitting') then
      raise exception 'Submission lease still active; wait five minutes before recovery'; end if;
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'batch_recovered',b.id);
    return 'true';
  elsif operation = 'cancel' then
    select count(*) into n from outreach.recipient_attempts where batch_id=b.id and state='not_attempted';
    if b.status='started' then
      update outreach.outreach_batches set status='cancelled' where id=b.id;
      if not b.test_mode then update outreach.quota_reservations set held=held-n where batch_id=b.id; end if;
    end if;
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'batch_cancelled',b.id);
    return 'true';
  end if;
  raise exception 'Unsupported operation';
end $$;

revoke all on function public.outreach_access() from public, anon;
revoke all on function public.issue_invitation(text,text,timestamptz) from public, anon;
revoke all on function public.redeem_invitation(text) from public, anon;
revoke all on function public.outreach_action(text,uuid,jsonb) from public, anon;
grant execute on function public.outreach_access() to authenticated;
grant execute on function public.issue_invitation(text,text,timestamptz) to authenticated;
grant execute on function public.redeem_invitation(text) to authenticated;
grant execute on function public.outreach_action(text,uuid,jsonb) to authenticated;
