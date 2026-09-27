-- Bounded standing-authority bridge for evidence-complete buyer/outbound actions.
-- No funds, commercial-terms acceptance, revenue recognition, infrastructure
-- mutation, or authority expansion is exposed here.
BEGIN;

CREATE OR REPLACE FUNCTION public.auto_review_buyer_candidate(
    p_review_id uuid,
    p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
    r public.buyer_candidate_reviews%ROWTYPE;
    contact jsonb;
    approved_today integer;
BEGIN
    IF p_daily_cap IS NULL OR p_daily_cap < 1 OR p_daily_cap > 50 THEN
        RAISE EXCEPTION 'standing authority daily cap must be 1-50';
    END IF;

    SELECT * INTO r
      FROM public.buyer_candidate_reviews
     WHERE id=p_review_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'buyer candidate review not found';
    END IF;

    IF r.status='approved' THEN
        RETURN jsonb_build_object(
            'decision','existing',
            'review_id',r.id,
            'status',r.status,
            'actual_revenue',false
        );
    END IF;

    IF r.status<>'pending' THEN
        RAISE EXCEPTION 'pending buyer candidate review required';
    END IF;

    IF r.proposed_at < clock_timestamp()-interval '7 days' THEN
        RAISE EXCEPTION 'buyer candidate review expired';
    END IF;

    IF r.offer_key <> 'managed_service' THEN
        RAISE EXCEPTION 'offer outside standing authority';
    END IF;

    IF COALESCE(lower(r.evidence->>'review_ready'),'false') <> 'true'
       OR COALESCE(lower(r.evidence->>'outreach_ready'),'false') <> 'true' THEN
        RAISE EXCEPTION 'review and outreach readiness required';
    END IF;

    IF COALESCE(r.company_score,0) < 70
       OR COALESCE(r.decision_score,0) < 0.70 THEN
        RAISE EXCEPTION 'candidate score below standing authority threshold';
    END IF;

    IF COALESCE(r.evidence->>'contact_source','') NOT IN (
        'official_site','official_site_current','public_record','press_release'
    ) THEN
        RAISE EXCEPTION 'contact source outside standing authority';
    END IF;

    SELECT item INTO contact
      FROM jsonb_array_elements(
        CASE
          WHEN jsonb_typeof(r.evidence->'verified_contacts')='array'
          THEN r.evidence->'verified_contacts'
          ELSE '[]'::jsonb
        END
      ) items(item)
     WHERE lower(trim(COALESCE(item->>'email',''))) =
           lower(trim(COALESCE(r.contact_email,'')))
     LIMIT 1;

    IF contact IS NULL THEN
        RAISE EXCEPTION 'verified contact evidence required';
    END IF;

    IF contact->'bound_to_decision_maker' IS DISTINCT FROM 'true'::jsonb
       OR contact->'has_mx' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_valid' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_disposable' IS DISTINCT FROM 'false'::jsonb
       OR contact->'is_role_address' IS DISTINCT FROM 'false'::jsonb THEN
        RAISE EXCEPTION 'verified decision-maker contact evidence required';
    END IF;

    IF jsonb_typeof(contact->'confidence') <> 'number'
       OR (contact->>'confidence')::numeric < 0.70 THEN
        RAISE EXCEPTION 'contact confidence below standing authority threshold';
    END IF;

    IF COALESCE(contact->>'source','') NOT IN (
        'official_site','official_site_current','public_record','press_release'
    ) THEN
        RAISE EXCEPTION 'verified contact source outside standing authority';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
         WHERE s.normalized_contact=lower(trim(r.contact_email))
    ) THEN
        RAISE EXCEPTION 'recipient is suppressed';
    END IF;

    SELECT count(*)::integer INTO approved_today
      FROM public.buyer_candidate_review_events e
     WHERE e.event_type='approved'
       AND e.actor='gtm-standing-authority'
       AND e.occurred_at >= date_trunc('day', clock_timestamp());

    IF approved_today >= p_daily_cap THEN
        RAISE EXCEPTION 'standing authority daily candidate cap reached';
    END IF;

    UPDATE public.buyer_candidate_reviews
       SET status='approved',
           reviewed_at=clock_timestamp(),
           reviewed_by='gtm-standing-authority',
           review_note='Approved automatically under bounded GTM standing authority.'
     WHERE id=r.id
     RETURNING * INTO r;

    INSERT INTO public.buyer_candidate_review_events(
        review_id,event_type,actor,payload
    ) VALUES(
        r.id,
        'approved',
        'gtm-standing-authority',
        jsonb_build_object(
            'standing_authority',true,
            'daily_cap',p_daily_cap,
            'actual_revenue',false
        )
    );

    RETURN jsonb_build_object(
        'decision','approved',
        'review_id',r.id,
        'status',r.status,
        'standing_authority',true,
        'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.list_buyer_reviews_for_outbound(
    p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path=''
AS $$
  SELECT COALESCE(
    jsonb_agg(to_jsonb(q) ORDER BY q.reviewed_at, q.id),
    '[]'::jsonb
  )
  FROM (
    SELECT
      r.id,
      r.prospect_id,
      r.entity_id,
      r.contact_name,
      r.contact_title,
      r.contact_email,
      r.offer_key,
      r.company_score,
      r.decision_score,
      r.evidence,
      r.reviewed_at
    FROM public.buyer_candidate_reviews r
    WHERE r.status='approved'
      AND r.reviewed_at >= clock_timestamp()-interval '7 days'
      AND COALESCE(lower(r.evidence->>'outreach_ready'),'false')='true'
      AND NOT EXISTS (
        SELECT 1
          FROM public.buyer_candidate_review_events e
         WHERE e.review_id=r.id
           AND e.event_type='outbound_proposed'
      )
    ORDER BY r.reviewed_at, r.id
    LIMIT LEAST(GREATEST(COALESCE(p_limit,25),1),100)
  ) q;
$$;

CREATE OR REPLACE FUNCTION public.auto_approve_outbound_intent(
    p_intent_id uuid,
    p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
    i public.outbound_intents%ROWTYPE;
    r public.buyer_candidate_reviews%ROWTYPE;
    evidence jsonb;
    contact jsonb;
    review_id uuid;
    approved_today integer;
    result jsonb;
BEGIN
    IF p_daily_cap IS NULL OR p_daily_cap < 1 OR p_daily_cap > 50 THEN
        RAISE EXCEPTION 'standing authority daily cap must be 1-50';
    END IF;

    SELECT * INTO i
      FROM public.outbound_intents
     WHERE id=p_intent_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF i.status='approved' THEN
        RETURN jsonb_build_object(
            'decision','existing',
            'intent_id',i.id,
            'status',i.status,
            'actual_revenue',false
        );
    END IF;

    IF i.status<>'pending_approval' THEN
        RAISE EXCEPTION 'pending outbound intent required';
    END IF;

    IF i.expires_at IS NULL OR i.expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'fresh outbound intent required';
    END IF;

    IF i.channel <> 'email'
       OR trim(COALESCE(i.recipient,''))=''
       OR trim(COALESCE(i.subject,''))=''
       OR trim(COALESCE(i.body_text,''))='' THEN
        RAISE EXCEPTION 'complete email intent required';
    END IF;

    IF lower(i.body_text) NOT LIKE '%opt out%'
       AND lower(i.body_text) NOT LIKE '%unsubscribe%'
       AND lower(i.body_text) NOT LIKE '%opt-out%' THEN
        RAISE EXCEPTION 'visible opt-out required';
    END IF;

    IF lower(i.body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
        RAISE EXCEPTION 'approved postal footer required';
    END IF;

    IF i.offer_key <> 'managed_service' THEN
        RAISE EXCEPTION 'offer outside standing authority';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
         WHERE s.normalized_contact=i.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient is suppressed';
    END IF;

    BEGIN
        review_id := (i.metadata->>'buyer_candidate_review_id')::uuid;
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'buyer candidate review reference required';
    END;

    SELECT * INTO r
      FROM public.buyer_candidate_reviews
     WHERE id=review_id;

    IF NOT FOUND OR r.status<>'approved'
       OR r.reviewed_at IS NULL
       OR r.reviewed_at < clock_timestamp()-interval '7 days' THEN
        RAISE EXCEPTION 'fresh approved buyer candidate review required';
    END IF;

    evidence := COALESCE(i.metadata->'candidate_evidence','{}'::jsonb);

    IF COALESCE(lower(evidence->>'review_ready'),'false') <> 'true'
       OR COALESCE(lower(evidence->>'outreach_ready'),'false') <> 'true' THEN
        RAISE EXCEPTION 'review and outreach readiness required';
    END IF;

    IF COALESCE((i.metadata->>'company_score')::numeric,0) < 70 THEN
        RAISE EXCEPTION 'company score below standing authority threshold';
    END IF;

    SELECT item INTO contact
      FROM jsonb_array_elements(
        CASE
          WHEN jsonb_typeof(evidence->'verified_contacts')='array'
          THEN evidence->'verified_contacts'
          ELSE '[]'::jsonb
        END
      ) items(item)
     WHERE lower(trim(COALESCE(item->>'email',''))) =
           i.normalized_recipient
     LIMIT 1;

    IF contact IS NULL
       OR contact->'bound_to_decision_maker' IS DISTINCT FROM 'true'::jsonb
       OR contact->'has_mx' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_valid' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_disposable' IS DISTINCT FROM 'false'::jsonb
       OR contact->'is_role_address' IS DISTINCT FROM 'false'::jsonb THEN
        RAISE EXCEPTION 'verified decision-maker contact evidence required';
    END IF;

    IF jsonb_typeof(contact->'confidence') <> 'number'
       OR (contact->>'confidence')::numeric < 0.70
       OR COALESCE(contact->>'source','') NOT IN (
           'official_site','official_site_current','public_record','press_release'
       ) THEN
        RAISE EXCEPTION 'contact evidence outside standing authority';
    END IF;

    SELECT count(*)::integer INTO approved_today
      FROM public.outbound_events e
     WHERE e.event_type='approved'
       AND e.actor='gtm-standing-authority'
       AND e.occurred_at >= date_trunc('day', clock_timestamp());

    IF approved_today >= p_daily_cap THEN
        RAISE EXCEPTION 'standing authority daily outbound cap reached';
    END IF;

    result := public.approve_outbound_intent(
        i.id,
        'gtm-standing-authority',
        'Approved automatically under bounded GTM standing authority.'
    );

    RETURN result || jsonb_build_object(
        'standing_authority',true,
        'actual_revenue',false
    );
END;
$$;

REVOKE ALL ON FUNCTION public.auto_review_buyer_candidate(uuid,integer)
  FROM PUBLIC,anon,authenticated,empire_outbound_approver,
       empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.list_buyer_reviews_for_outbound(integer)
  FROM PUBLIC,anon,authenticated,empire_outbound_approver,
       empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.auto_approve_outbound_intent(uuid,integer)
  FROM PUBLIC,anon,authenticated,empire_outbound_approver,
       empire_outbound_sender,empire_reply_ingest;

GRANT EXECUTE ON FUNCTION public.auto_review_buyer_candidate(uuid,integer)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.list_buyer_reviews_for_outbound(integer)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.auto_approve_outbound_intent(uuid,integer)
  TO service_role;

COMMENT ON FUNCTION public.auto_review_buyer_candidate(uuid,integer) IS
'Bounded evidence-only GTM standing-authority approval for review-ready managed-service buyer candidates. No outbound send, payment, terms acceptance, or revenue mutation.';
COMMENT ON FUNCTION public.auto_approve_outbound_intent(uuid,integer) IS
'Bounded GTM standing-authority approval for compliant evidence-complete email intents. Send remains governed separately.';
COMMENT ON FUNCTION public.list_buyer_reviews_for_outbound(integer) IS
'Lists fresh approved outreach-ready buyer reviews that have not yet produced an outbound intent.';

COMMIT;
