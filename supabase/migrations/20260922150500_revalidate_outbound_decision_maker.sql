-- Revalidate decision-maker personhood at the final standing-authority gate.
BEGIN;

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
    business_name text;
    contact_norm text;
    business_norm text;
    contact_words integer;
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
      SELECT 1
      FROM public.outbound_suppressions s
      WHERE s.normalized_contact=i.normalized_recipient
    ) THEN
      RAISE EXCEPTION 'recipient is suppressed';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM public.outbound_intents prior
      WHERE prior.id<>i.id
        AND prior.normalized_recipient=i.normalized_recipient
        AND prior.status IN (
          'sending','sent','delivered','replied',
          'bounced','failed','suppressed'
        )
    ) THEN
      RAISE EXCEPTION 'existing outbound history requires explicit review';
    END IF;

    BEGIN
      review_id := (i.metadata->>'buyer_candidate_review_id')::uuid;
    EXCEPTION WHEN others THEN
      RAISE EXCEPTION 'buyer candidate review reference required';
    END;

    SELECT * INTO r
    FROM public.buyer_candidate_reviews
    WHERE id=review_id;

    IF NOT FOUND
       OR r.status<>'approved'
       OR r.reviewed_at IS NULL
       OR r.reviewed_at < clock_timestamp()-interval '7 days' THEN
      RAISE EXCEPTION 'fresh approved buyer candidate review required';
    END IF;

    SELECT p.business_name INTO business_name
    FROM public.prospects p
    WHERE p.id=r.prospect_id;

    IF trim(COALESCE(r.contact_name,''))=''
       OR trim(COALESCE(r.contact_title,''))=''
       OR lower(trim(COALESCE(r.contact_email,'')))<>i.normalized_recipient THEN
      RAISE EXCEPTION 'named decision-maker review required';
    END IF;

    contact_norm := trim(
      regexp_replace(lower(r.contact_name),'[^a-z]+',' ','g')
    );
    business_norm := trim(
      regexp_replace(lower(COALESCE(business_name,'')),'[^a-z]+',' ','g')
    );
    contact_words := COALESCE(
      array_length(regexp_split_to_array(contact_norm,'\s+'),1),
      0
    );

    IF contact_words < 2 OR contact_words > 5
       OR contact_norm ~
          '(^| )(your|referral|program|contact|team|company|services?|support|sales|info|office|membership|pricing|quote|estimate|booking|schedule)( |$)'
       OR business_norm = contact_norm
       OR (
         contact_norm <> ''
         AND business_norm LIKE contact_norm || ' %'
       ) THEN
      RAISE EXCEPTION 'plausible named decision-maker required';
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
    WHERE lower(trim(COALESCE(item->>'email','')))=i.normalized_recipient
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
         'official_site','official_site_current',
         'public_record','press_release'
       ) THEN
      RAISE EXCEPTION 'contact evidence outside standing authority';
    END IF;

    SELECT count(*)::integer INTO approved_today
    FROM public.outbound_events e
    WHERE e.event_type='approved'
      AND e.actor='gtm-standing-authority'
      AND e.occurred_at >= date_trunc('day',clock_timestamp());

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
      'personhood_revalidated',true,
      'actual_revenue',false
    );
END;
$$;

COMMENT ON FUNCTION public.auto_approve_outbound_intent(uuid,integer)
IS 'Bounded first-touch approval with fresh review, suppression, delivery, verified-contact and plausible named-person revalidation.';

COMMIT;
