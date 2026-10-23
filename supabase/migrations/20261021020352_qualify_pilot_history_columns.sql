-- Fix SQLSTATE 42702 in history: the local manifest variable conflicts with
-- the unqualified column. Preserve all prior batches, grants and send policies.
create or replace function public.outreach_mail_action(command text, signature text) returns jsonb
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
    return coalesce((select jsonb_agg(x) from (
      select history_batch.id,history_batch.status,history_batch.test_mode,history_batch.created_at,
        history_batch.manifest->'messages'->0->>'subject' as subject
      from outreach.outreach_batches as history_batch
      where history_batch.owner_id=auth.uid()
        and history_batch.manifest->>'transport_policy' in ('user_gmail_v1','user_capture_v1')
      order by history_batch.created_at desc limit 50
    ) x),'[]'::jsonb);
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
