begin;

create table if not exists public.astra_observer_tokens (
  token_sha256 text primary key
    check (token_sha256 ~ '^[0-9a-f]{64}$'),
  active boolean not null default true,
  created_at timestamptz not null default clock_timestamp()
);

alter table public.astra_observer_tokens enable row level security;
revoke all on public.astra_observer_tokens
  from public, anon, authenticated, service_role,
       empire_outcome_recorder, empire_revenue_recognizer,
       empire_outcome_reader, empire_astra_observer;

create or replace function public.astra_observer_token_valid(p_token text)
returns boolean
language sql
stable
security definer
set search_path=''
as $$
  select exists (
    select 1
    from public.astra_observer_tokens t
    where t.active = true
      and t.token_sha256 =
        encode(extensions.digest(coalesce(p_token,''), 'sha256'), 'hex')
  );
$$;

revoke all on function public.astra_observer_token_valid(text)
  from public, anon, authenticated, service_role,
       empire_outcome_recorder, empire_revenue_recognizer,
       empire_outcome_reader, empire_astra_observer;

create or replace function public.get_astra_operational_evidence_token(
  p_token text
) returns jsonb
language plpgsql
stable
security definer
set search_path=''
as $$
begin
  if not public.astra_observer_token_valid(p_token) then
    raise exception 'invalid astra observer token';
  end if;
  return public.get_astra_operational_evidence();
end;
$$;

create or replace function public.get_commercial_outcome_feedback_token(
  p_token text,
  p_limit integer default 100
) returns jsonb
language plpgsql
stable
security definer
set search_path=''
as $$
begin
  if not public.astra_observer_token_valid(p_token) then
    raise exception 'invalid astra observer token';
  end if;
  return public.get_commercial_outcome_feedback(p_limit);
end;
$$;

revoke all on function public.get_astra_operational_evidence_token(text)
  from public, authenticated, service_role,
       empire_outcome_recorder, empire_revenue_recognizer,
       empire_outcome_reader, empire_astra_observer;
revoke all on function public.get_commercial_outcome_feedback_token(text,integer)
  from public, authenticated, service_role,
       empire_outcome_recorder, empire_revenue_recognizer,
       empire_outcome_reader, empire_astra_observer;

grant execute on function public.get_astra_operational_evidence_token(text)
  to anon;
grant execute on function public.get_commercial_outcome_feedback_token(text,integer)
  to anon;

comment on table public.astra_observer_tokens is
'Phase 4 Astra observer token hashes only; raw tokens are never stored in Supabase.';
comment on function public.get_astra_operational_evidence_token(text) is
'Read-only Phase 4 Astra operational RPC authenticated by a server-held token.';
comment on function public.get_commercial_outcome_feedback_token(text,integer) is
'Read-only Phase 4 Astra feedback RPC authenticated by a server-held token.';

commit;
