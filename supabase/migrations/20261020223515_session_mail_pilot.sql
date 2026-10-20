-- Additive pilot. Apply AFTER the original migration; never rewrite historical hashes.
-- No SMTP passwords live here. The signing secret authorizes backend commands only.
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

create table outreach.mail_settings (
  singleton boolean primary key default true check (singleton),
  signing_secret text check (length(signing_secret) >= 64),
  test_recipient text,
  capture_enabled boolean not null default true,
  live_enabled boolean not null default false,
  hourly_limit integer not null default 5 check (hourly_limit between 1 and 5),
  daily_limit integer not null default 10 check (daily_limit between 1 and 10)
);
insert into outreach.mail_settings(singleton) values (true);
alter table outreach.mail_settings enable row level security;
revoke all on outreach.mail_settings from public, anon, authenticated;

-- The old implementation stays intact, private, for legacy/historical behavior and
-- shared finalization, suppression and recovery. Both paths use the SAME lock,
-- tables and quota holds, so the pilot cannot evade the legacy global allowance.
alter function public.outreach_action(text,uuid,jsonb) rename to project_action_v1;
alter function public.project_action_v1(text,uuid,jsonb) set schema outreach;
revoke all on function outreach.project_action_v1(text,uuid,jsonb) from public, anon, authenticated;

create function public.outreach_action(operation text, target_batch uuid default null, payload jsonb default '{}')
returns jsonb language plpgsql security definer set search_path = pg_catalog as $$
declare policy text;
begin
  perform public.outreach_access();
  if operation = 'start' then
    policy := payload->'manifest'->>'transport_policy';
  else
    select manifest->>'transport_policy' into policy from outreach.outreach_batches
      where id=target_batch and owner_id=auth.uid();
  end if;
  if policy is not null and policy <> 'project_smtp_v1' then
    raise exception 'Backend-authorized mail command required';
  end if;
  return outreach.project_action_v1(operation,target_batch,payload);
end $$;

-- Centralized pilot eligibility: called at BOTH start and claim.
create function outreach.mail_eligibility(actor jsonb, manifest jsonb) returns void
language plpgsql security definer set search_path = pg_catalog as $$
declare cfg outreach.mail_settings; transport text; test boolean;
begin
  select * into cfg from outreach.mail_settings where singleton;
  transport := manifest->>'transport_policy';
  test := (manifest->>'test_mode')::boolean;
  if transport is null or transport not in ('user_gmail_v1','user_capture_v1') or test is null
    or test is distinct from (transport='user_capture_v1')
    or (test and not cfg.capture_enabled) or (not test and not cfg.live_enabled)
    or lower(manifest->>'sender') is distinct from lower(actor->>'email')
    or lower(manifest->>'reply_to') is distinct from lower(actor->>'email')
    or jsonb_array_length(manifest->'messages') is distinct from 1
    or manifest->'bcc' is distinct from '[]'::jsonb
    or manifest->'attachment' is distinct from 'null'::jsonb
    or cfg.test_recipient is null
    or lower(manifest->'messages'->0->>'to') is distinct from lower(cfg.test_recipient)
    or coalesce(length(manifest->'messages'->0->>'subject'),0) not between 1 and 200
    or (manifest->'messages'->0->>'subject') ~ E'[\r\n]'
    or coalesce(length(manifest->'messages'->0->>'body'),0) not between 1 and 10000 then
    raise exception 'Pilot sender, recipient, content or transport policy rejected';
  end if;
  if exists(select 1 from outreach.suppression_entries where owner_id=auth.uid()
      and email=lower(cfg.test_recipient)) then raise exception 'Recipient suppressed'; end if;
end $$;
revoke all on function outreach.mail_eligibility(jsonb,jsonb) from public, anon, authenticated;

create function public.outreach_mail_action(command text, signature text) returns jsonb
language plpgsql security definer set search_path = pg_catalog as $$
declare cfg outreach.mail_settings; limits outreach.settings; actor jsonb; cmd jsonb;
  op text; target uuid; data jsonb; manifest jsonb; b outreach.outreach_batches;
  r outreach.recipient_attempts; test boolean; user_used integer; hour_used integer;
  day_used integer; user_held integer; global_held integer; extra integer; claim uuid;
begin
  actor := public.outreach_access();
  select * into cfg from outreach.mail_settings where singleton;
  if cfg.signing_secret is null or length(command)>65536 or signature is null
    or signature !~ '^[a-f0-9]{64}$'
    or signature is distinct from encode(extensions.hmac(command,cfg.signing_secret,'sha256'),'hex') then
    raise exception 'Backend signature required';
  end if;
  cmd := command::jsonb;
  if (cmd->>'owner')::uuid is distinct from auth.uid()
    or (cmd->>'expires')::bigint is null
    or (cmd->>'expires')::bigint < extract(epoch from clock_timestamp())
    or (cmd->>'expires')::bigint > extract(epoch from clock_timestamp())+90
    or (cmd->>'session') is distinct from (auth.jwt()->>'session_id')
    or not exists(select 1 from auth.sessions where id=(cmd->>'session')::uuid and user_id=auth.uid()) then
    raise exception 'Owner, session or command expiry invalid';
  end if;
  op := cmd->>'operation'; target := (cmd->>'batch_id')::uuid; data := cmd->'payload';
  if op='check' then return 'true'; end if;
  if op='list' then
    return coalesce((select jsonb_agg(x) from (select id,status,test_mode,created_at,
      manifest->'messages'->0->>'subject' as subject from outreach.outreach_batches
      where owner_id=auth.uid() and manifest->>'transport_policy' in ('user_gmail_v1','user_capture_v1')
      order by created_at desc limit 50) x),'[]');
  end if;
  perform pg_advisory_xact_lock(610110001);
  actor := public.outreach_access();
  select * into b from outreach.outreach_batches where id=target and owner_id=auth.uid() for update;
  if op='start' and b.id is null then
    manifest := data->'manifest';
  else
    if b.id is null or coalesce(b.manifest->>'transport_policy','') not in ('user_gmail_v1','user_capture_v1') then
      raise exception 'Pilot message not found or unauthorized';
    end if;
    manifest := b.manifest;
  end if;
  if op in ('start','claim') then
    perform outreach.mail_eligibility(actor,manifest);
    test := (manifest->>'test_mode')::boolean;
    select * into limits from outreach.settings where singleton;
    if limits.batch_limit is null or limits.global_hourly_limit is null or limits.global_daily_limit is null then
      raise exception 'Database quotas must be configured';
    end if;
    -- Reuse all legacy real-attempt counters and conservative unknown holds.
    if not test then
      select count(*) filter(where batches.owner_id=auth.uid() and a.updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'),
        count(*) filter(where a.updated_at>=date_trunc('hour',now() at time zone 'UTC') at time zone 'UTC'),
        count(*) filter(where a.updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC')
        into user_used,hour_used,day_used from outreach.recipient_attempts a
        join outreach.outreach_batches batches on batches.id=a.batch_id where not batches.test_mode and a.state='accepted';
      select coalesce(sum(held) filter(where owner_id=auth.uid()),0),coalesce(sum(held),0)
        into user_held,global_held from outreach.quota_reservations;
      extra := case when op='start' and b.id is null then 1 else 0 end;
      if user_used+user_held+extra > (actor->>'daily_limit')::integer
        or hour_used+global_held+extra > least(limits.global_hourly_limit,cfg.hourly_limit)
        or day_used+global_held+extra > least(limits.global_daily_limit,cfg.daily_limit)
        or (op='start' and ((data->>'global_hourly')::integer is null or (data->>'global_daily')::integer is null
          or hour_used+global_held+extra > (data->>'global_hourly')::integer
          or day_used+global_held+extra > (data->>'global_daily')::integer)) then
        raise exception 'Pilot or shared sending allowance exceeded';
      end if;
    end if;
    if op='start' then
      if b.id is not null then
        if b.content_hash is distinct from data->>'content_hash' or b.manifest is distinct from data->'manifest' then
          raise exception 'Message already exists with different content'; end if;
        return jsonb_build_object('id',b.id);
      end if;
      insert into outreach.outreach_batches(id,owner_id,content_hash,manifest,test_mode)
        values(target,auth.uid(),data->>'content_hash',manifest,test);
      insert into outreach.recipient_attempts(batch_id,ordinal,email) values(target,0,manifest->'messages'->0->>'to');
      insert into outreach.quota_reservations(batch_id,owner_id,held) values(target,auth.uid(),case when test then 0 else 1 end);
      insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'pilot_started',target);
      return jsonb_build_object('id',target);
    end if;
    if b.content_hash is distinct from data->>'content_hash' or b.status<>'started' then
      -- Completed/cancelled intents cannot submit again.
      return null;
    end if;
    select * into r from outreach.recipient_attempts where batch_id=target and ordinal=0 for update;
    if r.state='submitting' then raise exception 'Submission in progress; recover after lease expiry'; end if;
    if r.state<>'not_attempted' or (data->>'expected_ordinal')::integer is distinct from 0 then return null; end if;
    claim := gen_random_uuid();
    update outreach.recipient_attempts set state='submitting',claim_token=claim,updated_at=now() where batch_id=target and ordinal=0;
    return jsonb_build_object('ordinal',0,'claim_token',claim);
  elsif op in ('finish','log','recover','cancel','get') then
    return outreach.project_action_v1(op,target,data);
  end if;
  raise exception 'Unsupported pilot operation';
end $$;

revoke all on function public.outreach_action(text,uuid,jsonb) from public, anon;
grant execute on function public.outreach_action(text,uuid,jsonb) to authenticated;
revoke all on function public.outreach_mail_action(text,text) from public, anon;
grant execute on function public.outreach_mail_action(text,text) to authenticated;
