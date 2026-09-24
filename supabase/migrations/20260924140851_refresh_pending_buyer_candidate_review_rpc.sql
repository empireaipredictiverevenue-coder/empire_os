-- Governed pending buyer-candidate review evidence refresh.
--
-- Canonical Supabase migration version: 20260924140851.
-- Keeps buyer_candidate_reviews table UPDATE unavailable to service_role.
-- Only the internal service_role may execute this narrow refresh RPC.
-- The RPC can update verified contact/evidence fields only while status=pending.
-- It cannot approve/reject reviews, send outreach, move funds, or recognize revenue.

create or replace function public.refresh_pending_buyer_candidate_review(
  p_review_id uuid,
  p_contact_name text,
  p_contact_title text,
  p_contact_email text,
  p_decision_score numeric,
  p_evidence jsonb
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  r public.buyer_candidate_reviews%rowtype;
  v_email text := lower(trim(coalesce(p_contact_email,'')));
  v_name text := trim(coalesce(p_contact_name,''));
  v_title text := trim(coalesce(p_contact_title,''));
begin
  if p_review_id is null then
    raise exception 'review id required';
  end if;

  if length(v_name) < 3 or length(v_title) < 2 then
    raise exception 'verified decision maker required';
  end if;

  if v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then
    raise exception 'verified contact email required';
  end if;

  if p_decision_score is null
     or p_decision_score < 0.5
     or p_decision_score > 1 then
    raise exception 'decision score threshold not met';
  end if;

  if coalesce(p_evidence,'{}'::jsonb) = '{}'::jsonb then
    raise exception 'candidate evidence required';
  end if;

  select * into r
  from public.buyer_candidate_reviews
  where id = p_review_id
  for update;

  if not found then
    raise exception 'buyer candidate review not found';
  end if;

  if r.status <> 'pending' then
    return jsonb_build_object(
      'decision','not_pending',
      'review_id',r.id,
      'status',r.status,
      'actual_revenue',false
    );
  end if;

  if r.contact_name = v_name
     and r.contact_title = v_title
     and lower(r.contact_email) = v_email
     and r.decision_score = p_decision_score
     and r.evidence = p_evidence then
    return jsonb_build_object(
      'decision','no_change',
      'review_id',r.id,
      'status',r.status,
      'actual_revenue',false
    );
  end if;

  update public.buyer_candidate_reviews
  set contact_name = v_name,
      contact_title = v_title,
      contact_email = v_email,
      decision_score = p_decision_score,
      evidence = p_evidence
  where id = r.id
    and status = 'pending'
  returning * into r;

  if not found then
    raise exception 'pending review changed concurrently';
  end if;

  return jsonb_build_object(
    'decision','updated',
    'review_id',r.id,
    'status',r.status,
    'actual_revenue',false
  );
end;
$$;

revoke execute on function public.refresh_pending_buyer_candidate_review(
  uuid,text,text,text,numeric,jsonb
) from public, anon, authenticated;

grant execute on function public.refresh_pending_buyer_candidate_review(
  uuid,text,text,text,numeric,jsonb
) to service_role;

comment on function public.refresh_pending_buyer_candidate_review(
  uuid,text,text,text,numeric,jsonb
) is
'Internal service-role-only refresh of verified contact evidence on an existing pending buyer candidate review. Cannot approve, reject, send outreach, move funds, or recognize revenue.';
