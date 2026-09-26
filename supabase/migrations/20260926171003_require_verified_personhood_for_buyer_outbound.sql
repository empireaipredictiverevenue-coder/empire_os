-- Require verified named contact personhood throughout governed buyer outbound.
-- This prevents stale/pseudo-person buyer reviews from being auto-approved,
-- reproposed, or used to create a fresh outbound intent.
BEGIN;

CREATE OR REPLACE FUNCTION public.list_buyer_reviews_for_outbound(
    p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path=''
AS $function$
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
      AND COALESCE(lower(r.evidence->>'contact_personhood_valid'),'false')='true'
      AND COALESCE(lower(r.evidence->>'has_named_contact'),'false')='true'
      AND NOT EXISTS (
        SELECT 1
        FROM public.outbound_suppressions s
        WHERE s.normalized_contact=lower(trim(r.contact_email))
      )
      AND NOT EXISTS (
        SELECT 1
        FROM public.outbound_intents i
        WHERE i.normalized_recipient=lower(trim(r.contact_email))
          AND (
            i.status IN (
              'sending','sent','delivered','replied',
              'bounced','failed','suppressed'
            )
            OR (
              i.status IN ('pending_approval','approved')
              AND i.expires_at > clock_timestamp()
            )
          )
      )
    ORDER BY r.reviewed_at,r.id
    LIMIT LEAST(GREATEST(COALESCE(p_limit,25),1),100)
  ) q;
$function$;

CREATE OR REPLACE FUNCTION public.propose_reviewed_outbound_intent(
    p_review_id uuid,
    p_subject text,
    p_body_text text,
    p_body_html text,
    p_idempotency_key text,
    p_proposed_by text,
    p_expires_at timestamptz,
    p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $function$
DECLARE
    r public.buyer_candidate_reviews%ROWTYPE;
    result jsonb;
    merged jsonb;
BEGIN
    SELECT * INTO r
    FROM public.buyer_candidate_reviews
    WHERE id=p_review_id
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'buyer candidate review not found';
    END IF;
    IF r.status<>'approved' THEN
      RAISE EXCEPTION 'approved buyer candidate review required';
    END IF;
    IF r.reviewed_at IS NULL
       OR r.reviewed_at < clock_timestamp()-interval '7 days' THEN
      RAISE EXCEPTION 'fresh buyer candidate approval required';
    END IF;
    IF COALESCE(lower(r.evidence->>'outreach_ready'),'false') <> 'true' THEN
      RAISE EXCEPTION 'outreach-ready evidence required';
    END IF;
    IF COALESCE(lower(r.evidence->>'contact_personhood_valid'),'false') <> 'true'
       OR COALESCE(lower(r.evidence->>'has_named_contact'),'false') <> 'true' THEN
      RAISE EXCEPTION 'verified contact personhood required';
    END IF;

    merged := COALESCE(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'buyer_candidate_review_id',r.id,
      'decision_score',r.decision_score,
      'company_score',r.company_score,
      'candidate_evidence',r.evidence
    );

    result := public.propose_outbound_intent(
      r.entity_id,
      r.prospect_id,
      NULL,
      NULL,
      'email',
      r.contact_email,
      p_subject,
      p_body_text,
      p_body_html,
      r.offer_key,
      p_idempotency_key,
      p_proposed_by,
      p_expires_at,
      merged
    );

    INSERT INTO public.buyer_candidate_review_events(
      review_id,event_type,actor,payload
    )
    VALUES(
      r.id,
      'outbound_proposed',
      trim(p_proposed_by),
      jsonb_build_object('intent_id',result->>'intent_id')
    );

    RETURN result || jsonb_build_object(
      'buyer_candidate_review_id',r.id
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.auto_review_buyer_candidate(
    p_review_id uuid,
    p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $function$
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

    IF COALESCE(lower(r.evidence->>'contact_personhood_valid'),'false') <> 'true'
       OR COALESCE(lower(r.evidence->>'has_named_contact'),'false') <> 'true' THEN
      RAISE EXCEPTION 'verified contact personhood required';
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
      SELECT 1
      FROM public.outbound_suppressions s
      WHERE s.normalized_contact=lower(trim(r.contact_email))
    ) THEN
      RAISE EXCEPTION 'recipient is suppressed';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM public.outbound_intents i
      WHERE i.normalized_recipient=lower(trim(r.contact_email))
        AND i.status IN (
          'sending','sent','delivered','replied','bounced','failed','suppressed'
        )
    ) THEN
      RAISE EXCEPTION 'existing outbound history requires explicit review';
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
    )
    VALUES(
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
$function$;

COMMENT ON FUNCTION public.list_buyer_reviews_for_outbound(integer) IS
'Lists only fresh approved outreach-ready reviews with verified named contact personhood, no suppression, no real outbound history, and no still-live unsent intent.';

COMMENT ON FUNCTION public.propose_reviewed_outbound_intent(
    uuid,text,text,text,text,text,timestamptz,jsonb
) IS
'Creates outbound intent only from fresh approved outreach-ready buyer reviews with verified named contact personhood.';

COMMENT ON FUNCTION public.auto_review_buyer_candidate(uuid,integer) IS
'Bounded evidence-only GTM standing-authority approval requiring verified named contact personhood and decision-maker contact evidence. No outbound send, payment, terms acceptance, or revenue mutation.';

COMMIT;
