-- Additive Cloudflare application. Existing pilot/legacy tables and RPCs stay intact.
-- No Gmail credentials are persisted. Only backend HMAC key, approved content and outcomes.
create table outreach.cloud_settings (
  singleton boolean primary key default true check(singleton),
  signing_secret text not null default encode(extensions.gen_random_bytes(32),'hex') check(length(signing_secret)>=64),
  live_enabled boolean not null default false,
  debug_enabled boolean not null default true,
  batch_limit integer not null default 5 check(batch_limit between 1 and 5),
  user_daily_limit integer not null default 10 check(user_daily_limit between 1 and 10),
  global_daily_limit integer not null default 50 check(global_daily_limit between 1 and 50)
);
insert into outreach.cloud_settings(singleton) values(true);
create table outreach.cloud_requests (
  owner_id uuid primary key references auth.users(id),
  full_name text not null check(length(full_name) between 1 and 200),
  purpose text not null check(length(purpose) between 1 and 1000),
  status text not null default 'pending' check(status in ('pending','approved','revoked')),
  daily_limit integer not null default 10 check(daily_limit between 1 and 10),
  admin_notes text not null default '' check(length(admin_notes)<=2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  connect_window timestamptz,
  connect_attempts integer not null default 0
);
create table outreach.cloud_batches (
  id uuid primary key,
  owner_id uuid not null references outreach.users(id),
  sender text not null,
  content_hash text not null check(content_hash ~ '^[a-f0-9]{64}$'),
  messages jsonb not null check(jsonb_typeof(messages)='array' and jsonb_array_length(messages) between 1 and 5),
  status text not null default 'active' check(status in ('active','completed','cancelled')),
  created_at timestamptz not null default now(),
  unique(owner_id,content_hash)
);
create table outreach.cloud_attempts (
  batch_id uuid not null references outreach.cloud_batches(id),
  ordinal integer not null check(ordinal between 0 and 4),
  email text not null,
  state text not null default 'pending' check(state in ('pending','submitting','accepted','failed','unknown','cancelled')),
  claim_token uuid,
  message_id text,
  detail text not null default 'Waiting for browser-confirmed sending.',
  updated_at timestamptz not null default now(),
  primary key(batch_id,ordinal)
);
create index cloud_attempts_accepted_time on outreach.cloud_attempts(updated_at) where state='accepted';
create index cloud_batches_owner_created on outreach.cloud_batches(owner_id,created_at desc);
alter table outreach.cloud_settings enable row level security;
alter table outreach.cloud_requests enable row level security;
alter table outreach.cloud_batches enable row level security;
alter table outreach.cloud_attempts enable row level security;
revoke all on outreach.cloud_settings,outreach.cloud_requests,outreach.cloud_batches,outreach.cloud_attempts from public,anon,authenticated;

-- Count every unresolved reservation, including old pilot/legacy holds. Cloud sends
-- are disabled if either previous live transport is enabled (no parallel quota paths).
create function outreach.cloud_usage(owner uuid) returns jsonb
language sql stable set search_path=pg_catalog as $$
  with accepted as (
    select b.owner_id,a.updated_at from outreach.cloud_attempts a join outreach.cloud_batches b on b.id=a.batch_id where a.state='accepted'
    union all
    select b.owner_id,a.updated_at from outreach.recipient_attempts a join outreach.outreach_batches b on b.id=a.batch_id where a.state='accepted' and not b.test_mode
  ), held as (
    select b.owner_id,count(*)::bigint as n from outreach.cloud_attempts a join outreach.cloud_batches b on b.id=a.batch_id where a.state in ('pending','submitting','unknown') group by b.owner_id
    union all select r.owner_id,r.held from outreach.quota_reservations r
  ) select jsonb_build_object(
    'user_used',(select count(*) from accepted where owner_id=owner and updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'),
    'global_used',(select count(*) from accepted where updated_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'),
    'user_held',(select coalesce(sum(n),0) from held where owner_id=owner),
    'global_held',(select coalesce(sum(n),0) from held));
$$;
revoke all on function outreach.cloud_usage(uuid) from public,anon,authenticated;

create function public.cloud_mail_action(command text,signature text) returns jsonb
language plpgsql security definer set search_path=pg_catalog as $$
declare cfg outreach.cloud_settings; actor outreach.users; profile outreach.cloud_requests;
  cmd jsonb; op text; data jsonb; target uuid; email_address text; approved boolean;
  usage jsonb; allowance integer; target_user uuid; verified_target text;
  batch outreach.cloud_batches; attempt outreach.cloud_attempts; message jsonb; n integer; i integer;
  claim uuid; result jsonb; outcome text;
begin
  select * into cfg from outreach.cloud_settings where singleton;
  if cfg.signing_secret is null or length(command)>131072 or signature is null or signature !~ '^[a-f0-9]{64}$'
    or signature is distinct from encode(extensions.hmac(command,cfg.signing_secret,'sha256'),'hex') then
    raise exception 'Backend authorization required';
  end if;
  cmd:=command::jsonb; op:=cmd->>'operation'; data:=coalesce(cmd->'payload','{}'::jsonb); target:=(cmd->>'batch_id')::uuid;
  if auth.uid() is null or (cmd->>'owner')::uuid is distinct from auth.uid()
    or (cmd->>'expires')::bigint is null or (cmd->>'expires')::bigint < extract(epoch from clock_timestamp())
    or (cmd->>'expires')::bigint > extract(epoch from clock_timestamp())+90
    or cmd->>'session' is distinct from auth.jwt()->>'session_id'
    or not exists(select 1 from auth.sessions where id=(cmd->>'session')::uuid and user_id=auth.uid()) then
    raise exception 'Verified active sign-in required';
  end if;
  select lower(email) into email_address from auth.users where id=auth.uid() and email_confirmed_at is not null;
  if email_address is null then raise exception 'Verified email required'; end if;
  select * into actor from outreach.users where id=auth.uid();
  select * into profile from outreach.cloud_requests where owner_id=auth.uid();
  approved:=coalesce(actor.active and lower(actor.email)=email_address,false);
  allowance:=least(cfg.user_daily_limit,coalesce(profile.daily_limit,10));
  if op='me' then
    usage:=outreach.cloud_usage(auth.uid());
    return jsonb_build_object('id',auth.uid(),'email',email_address,'approved',approved,'is_admin',approved and coalesce(actor.is_admin,false),
      'request_status',case when approved then 'approved' when actor.id is not null and not actor.active then 'revoked' else coalesce(profile.status,'not_requested') end,
      'full_name',coalesce(profile.full_name,''),'purpose',coalesce(profile.purpose,''),'daily_limit',allowance,
      'remaining',case when approved then greatest(0,allowance-(usage->>'user_used')::integer-(usage->>'user_held')::integer) else 0 end,
      'live_enabled',cfg.live_enabled,'debug_enabled',approved and coalesce(actor.is_admin,false) and cfg.debug_enabled,
      'batch_limit',cfg.batch_limit,'global_daily_limit',cfg.global_daily_limit);
  elsif op='request_access' then
    if length(trim(data->>'full_name')) not between 1 and 200 or length(trim(data->>'purpose')) not between 1 and 1000
      or data->>'full_name' is null or data->>'purpose' is null then raise exception 'Name and intended use are required'; end if;
    insert into outreach.cloud_requests(owner_id,full_name,purpose,status)
      values(auth.uid(),trim(data->>'full_name'),trim(data->>'purpose'),case when approved then 'approved' else 'pending' end)
      on conflict(owner_id) do update set full_name=excluded.full_name,purpose=excluded.purpose,updated_at=now();
    insert into outreach.audit_events(actor_id,event) values(auth.uid(),'cloud_access_requested');
    return 'true';
  end if;
  -- A claimed outcome may still be finalized after application revocation. It
  -- cannot authorize another send and prevents a known SMTP result being lost.
  if not approved and op<>'finish' then raise exception 'Administrator approval required or access revoked'; end if;
  if op like 'admin_%' then
    if not approved or not actor.is_admin then raise exception 'Administrator required'; end if;
    if op='admin_users' then
      return coalesce((select jsonb_agg(x order by x.created_at desc) from (
        select a.id,a.email,coalesce(u.active,false) as active,coalesce(u.is_admin,false) as is_admin,
          coalesce(p.full_name,'') as full_name,coalesce(p.purpose,'') as purpose,coalesce(p.admin_notes,'') as admin_notes,
          coalesce(p.daily_limit,10) as daily_limit,coalesce(p.status,case when u.active then 'approved' else 'pending' end) as status,
          coalesce(p.created_at,u.created_at) as created_at
        from auth.users a left join outreach.users u on u.id=a.id left join outreach.cloud_requests p on p.owner_id=a.id
        where (u.id is not null or p.owner_id is not null) and a.email_confirmed_at is not null
      ) x),'[]'::jsonb);
    end if;
    perform pg_advisory_xact_lock(610110001);
    -- Re-check membership inside the same lock used by approval/revocation/send.
    if not exists(select 1 from outreach.users where id=auth.uid() and active and is_admin) then raise exception 'Administrator required'; end if;
    if op='admin_settings' then
      if data ? 'live_enabled' then
        if jsonb_typeof(data->'live_enabled')<>'boolean' then raise exception 'Invalid live switch'; end if;
        if (data->>'live_enabled')::boolean and coalesce(data->>'policy_ack','')<>'permitted_messages_only' then raise exception 'Confirm permitted use before enabling Gmail'; end if;
        if (data->>'live_enabled')::boolean and (exists(select 1 from outreach.settings where real_sends_enabled) or exists(select 1 from outreach.mail_settings where live_enabled)) then raise exception 'Disable the older live transports first'; end if;
        update outreach.cloud_settings set live_enabled=(data->>'live_enabled')::boolean where singleton;
      end if;
      if data ? 'debug_enabled' then
        if jsonb_typeof(data->'debug_enabled')<>'boolean' then raise exception 'Invalid debug switch'; end if;
        update outreach.cloud_settings set debug_enabled=(data->>'debug_enabled')::boolean where singleton;
      end if;
      insert into outreach.audit_events(actor_id,event) values(auth.uid(),'cloud_settings_updated'); return 'true';
    end if;
    target_user:=(data->>'id')::uuid;
    select lower(email) into verified_target from auth.users where id=target_user and email_confirmed_at is not null;
    if verified_target is null or not (exists(select 1 from outreach.cloud_requests where owner_id=target_user) or exists(select 1 from outreach.users where id=target_user)) then raise exception 'Verified applicant not found'; end if;
    if op='admin_approve' then
      insert into outreach.users(id,email,active,is_admin) values(target_user,verified_target,true,false)
        on conflict(id) do update set active=true where lower(outreach.users.email)=excluded.email;
      update outreach.cloud_requests set status='approved',updated_at=now() where owner_id=target_user;
    elsif op='admin_revoke' then
      if exists(select 1 from outreach.users where id=target_user and is_admin) then raise exception 'Administrator revocation requires operator review'; end if;
      update outreach.users set active=false where id=target_user;
      update outreach.cloud_requests set status='revoked',updated_at=now() where owner_id=target_user;
      update outreach.cloud_attempts a set state='cancelled',detail='Access revoked before submission.',updated_at=now()
        from outreach.cloud_batches b where b.id=a.batch_id and b.owner_id=target_user and a.state='pending';
      update outreach.cloud_batches set status='cancelled' where owner_id=target_user and status='active';
    elsif op='admin_update' then
      if (data->>'daily_limit')::integer not between 1 and 10 or data->>'daily_limit' is null or length(coalesce(data->>'admin_notes',''))>2000 then raise exception 'Invalid user limit or notes'; end if;
      insert into outreach.cloud_requests(owner_id,full_name,purpose,status,daily_limit,admin_notes)
        values(target_user,coalesce(nullif(data->>'full_name',''),verified_target),'Existing approved account',case when exists(select 1 from outreach.users where id=target_user and active) then 'approved' else 'revoked' end,(data->>'daily_limit')::integer,coalesce(data->>'admin_notes',''))
        on conflict(owner_id) do update set full_name=excluded.full_name,daily_limit=excluded.daily_limit,admin_notes=excluded.admin_notes,updated_at=now();
    else raise exception 'Unsupported administrator operation'; end if;
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),op,target_user); return 'true';
  elsif op='debug' then
    if not actor.is_admin or not cfg.debug_enabled then raise exception 'Debug screen unavailable'; end if;
    return jsonb_build_object('database','connected','live_enabled',cfg.live_enabled,'session_verified',true,
      'batch_limit',cfg.batch_limit,'user_daily_limit',cfg.user_daily_limit,'global_daily_limit',cfg.global_daily_limit,
      'usage',outreach.cloud_usage(auth.uid()),'server_time',now());
  elsif op='suppressions' then
    return coalesce((select jsonb_agg(s.email) from outreach.suppression_entries s where s.owner_id=auth.uid()),'[]'::jsonb);
  elsif op='suppress' then
    perform pg_advisory_xact_lock(610110001);
    if coalesce(data->>'email','') !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' or length(data->>'email')>254 then raise exception 'Invalid suppression email'; end if;
    insert into outreach.suppression_entries(owner_id,email) values(auth.uid(),lower(data->>'email')) on conflict do nothing;
    insert into outreach.audit_events(actor_id,event) values(auth.uid(),'cloud_suppression_added'); return 'true';
  elsif op='connect_attempt' then
    perform pg_advisory_xact_lock(610110001);
    insert into outreach.cloud_requests(owner_id,full_name,purpose,status) values(auth.uid(),email_address,'Existing approved account','approved') on conflict do nothing;
    update outreach.cloud_requests set connect_attempts=case when connect_window is null or connect_window<now()-interval '10 minutes' then 1 else connect_attempts+1 end,
      connect_window=case when connect_window is null or connect_window<now()-interval '10 minutes' then now() else connect_window end where owner_id=auth.uid()
      returning * into profile;
    if profile.connect_attempts>5 then raise exception 'Connection limit reached; wait ten minutes'; end if;
    return 'true';
  elsif op='list' then
    return coalesce((select jsonb_agg(x order by x.created_at desc) from (
      select b.id,b.status,b.created_at,b.messages->0->>'subject' as subject,jsonb_array_length(b.messages) as recipient_count
      from outreach.cloud_batches b where b.owner_id=auth.uid() order by b.created_at desc limit 50
    ) x),'[]'::jsonb);
  end if;
  perform pg_advisory_xact_lock(610110001);
  select * into batch from outreach.cloud_batches where id=target and owner_id=auth.uid() for update;
  if op in ('start','claim') then
    if not exists(select 1 from outreach.users u join auth.users a on a.id=u.id where u.id=auth.uid() and u.active and lower(u.email)=lower(a.email) and a.email_confirmed_at is not null) then raise exception 'Administrator approval required or access revoked'; end if;
    select * into cfg from outreach.cloud_settings where singleton;
    select * into profile from outreach.cloud_requests where owner_id=auth.uid();
    allowance:=least(cfg.user_daily_limit,coalesce(profile.daily_limit,10));
    if not cfg.live_enabled then raise exception 'Live sending is disabled by the administrator'; end if;
    if exists(select 1 from outreach.settings where real_sends_enabled) or exists(select 1 from outreach.mail_settings where live_enabled) then raise exception 'Disable the older live transports first'; end if;
  end if;
  if op='start' then
    if jsonb_typeof(data->'messages') is distinct from 'array' then raise exception 'Invalid message list'; end if;
    n:=jsonb_array_length(data->'messages');
    if n<1 or n>cfg.batch_limit or data->>'content_hash' is null or data->>'content_hash' !~ '^[a-f0-9]{64}$' then raise exception 'Batch exceeds the approved limits'; end if;
    if exists(select 1 from outreach.cloud_batches b where b.owner_id=auth.uid() and b.content_hash=data->>'content_hash') then
      select * into batch from outreach.cloud_batches b where b.owner_id=auth.uid() and b.content_hash=data->>'content_hash';
      if batch.messages is distinct from data->'messages' then raise exception 'Content hash conflict'; end if;
      return jsonb_build_object('id',batch.id,'existing',true);
    end if;
    for message in select value from jsonb_array_elements(data->'messages') loop
      if jsonb_typeof(message->'email') is distinct from 'string' or jsonb_typeof(message->'name') is distinct from 'string'
        or jsonb_typeof(message->'subject') is distinct from 'string' or jsonb_typeof(message->'body') is distinct from 'string'
        or message->>'email' !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' or length(message->>'email')>254
        or length(message->>'name')>200 or message->>'name' ~ '[[:cntrl:]]'
        or length(trim(message->>'subject')) not between 1 and 200 or message->>'subject' ~ '[[:cntrl:]]'
        or length(trim(message->>'body')) not between 1 and 10000 then raise exception 'Invalid message content'; end if;
      if exists(select 1 from outreach.suppression_entries where owner_id=auth.uid() and email=lower(message->>'email')) then raise exception 'A recipient is on your suppression list'; end if;
    end loop;
    if (select count(distinct lower(value->>'email')) from jsonb_array_elements(data->'messages'))<>n then raise exception 'Duplicate recipients'; end if;
    usage:=outreach.cloud_usage(auth.uid());
    if (usage->>'user_used')::integer+(usage->>'user_held')::integer+n>allowance or (usage->>'global_used')::integer+(usage->>'global_held')::integer+n>cfg.global_daily_limit then raise exception 'Daily sending allowance exceeded'; end if;
    insert into outreach.cloud_batches(id,owner_id,sender,content_hash,messages) values(target,auth.uid(),email_address,data->>'content_hash',data->'messages');
    for i in 0..n-1 loop insert into outreach.cloud_attempts(batch_id,ordinal,email) values(target,i,lower(data->'messages'->i->>'email')); end loop;
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'cloud_batch_approved',target);
    return jsonb_build_object('id',target,'existing',false);
  end if;
  if batch.id is null then raise exception 'Batch not found or unauthorized'; end if;
  if op='claim' then
    if batch.status<>'active' then return null; end if;
    if batch.sender is distinct from email_address then raise exception 'Verified sender changed; cancel this batch and review again'; end if;
    if exists(select 1 from outreach.cloud_attempts where batch_id=target and state in ('submitting','unknown')) then raise exception 'Resolve the in-progress or unknown submission before continuing'; end if;
    usage:=outreach.cloud_usage(auth.uid());
    if (usage->>'user_used')::integer+(usage->>'user_held')::integer>allowance or (usage->>'global_used')::integer+(usage->>'global_held')::integer>cfg.global_daily_limit then raise exception 'Daily sending allowance exceeded'; end if;
    select * into attempt from outreach.cloud_attempts where batch_id=target and state='pending' order by ordinal limit 1 for update;
    if attempt.batch_id is null then return null; end if;
    if (data->>'ordinal')::integer is distinct from attempt.ordinal then raise exception 'Recipient order changed; refresh status'; end if;
    if exists(select 1 from outreach.suppression_entries where owner_id=auth.uid() and email=attempt.email) then raise exception 'A recipient is on your suppression list'; end if;
    if coalesce(data->>'message_id','') !~ '^<[a-f0-9-]+@[a-z0-9.-]+>$' then raise exception 'Invalid message identifier'; end if;
    claim:=gen_random_uuid();
    update outreach.cloud_attempts set state='submitting',claim_token=claim,message_id=data->>'message_id',detail='Submitting to Gmail over TLS.',updated_at=now() where batch_id=target and ordinal=attempt.ordinal;
    return jsonb_build_object('ordinal',attempt.ordinal,'claim_token',claim,'sender',batch.sender,'message',batch.messages->attempt.ordinal);
  elsif op='finish' then
    outcome:=data->>'state';
    if outcome not in ('accepted','failed','unknown') or outcome is null then raise exception 'Invalid submission outcome'; end if;
    select * into attempt from outreach.cloud_attempts where batch_id=target and ordinal=(data->>'ordinal')::integer for update;
    if attempt.state is distinct from 'submitting' or attempt.claim_token is distinct from (data->>'claim_token')::uuid or attempt.claim_token is null then raise exception 'Submission claim invalid'; end if;
    update outreach.cloud_attempts set state=outcome,detail=case outcome when 'accepted' then 'Gmail accepted the message. Inbox delivery is not confirmed.' when 'failed' then 'Submission failed or was rejected before acceptance; no automatic retry.' else 'Outcome uncertain. Check Gmail Sent; do not resend.' end,updated_at=now() where batch_id=target and ordinal=attempt.ordinal;
    insert into outreach.audit_events(actor_id,event,object_id) values(auth.uid(),'cloud_submission_'||outcome,target);
  elsif op='cancel' then
    update outreach.cloud_attempts set state='cancelled',detail='Cancelled before submission.',updated_at=now() where batch_id=target and state='pending';
    update outreach.cloud_batches set status='cancelled' where id=target;
  elsif op='recover' then
    update outreach.cloud_attempts set state='unknown',detail='Submission interrupted. Check Gmail Sent; do not resend.',updated_at=now() where batch_id=target and state='submitting' and updated_at<now()-interval '5 minutes';
  elsif op<>'get' then raise exception 'Unsupported operation';
  end if;
  if batch.status='active' and not exists(select 1 from outreach.cloud_attempts where batch_id=target and state in ('pending','submitting')) then update outreach.cloud_batches set status='completed' where id=target; end if;
  select jsonb_build_object('id',b.id,'status',b.status,'created_at',b.created_at,'sender',b.sender,'messages',b.messages,
    'attempts',(select jsonb_agg(jsonb_build_object('ordinal',a.ordinal,'email',a.email,'name',b.messages->a.ordinal->>'name','state',a.state,'detail',a.detail,'message_id',a.message_id,'updated_at',a.updated_at) order by a.ordinal) from outreach.cloud_attempts a where a.batch_id=b.id)) into result
    from outreach.cloud_batches b where b.id=target;
  return result;
end $$;
revoke all on function public.cloud_mail_action(text,text) from public,anon;
grant execute on function public.cloud_mail_action(text,text) to authenticated;
