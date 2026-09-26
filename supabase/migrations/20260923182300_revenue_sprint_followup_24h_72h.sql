-- Revenue sprint cadence: first no-reply follow-up at +24h, final at +72h.
-- Maximum follow-up count, suppression/reply/bounce gates, local contact windows,
-- standing-authority cap and outbound separation remain unchanged.

BEGIN;

CREATE OR REPLACE FUNCTION public.list_due_outbound_followups(
    p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path=''
AS $$
WITH roots AS (
    SELECT
        i.id AS root_intent_id,
        i.prospect_id,
        i.entity_id,
        i.buyer_id,
        i.opportunity_id,
        i.recipient,
        i.normalized_recipient,
        i.offer_key,
        i.subject AS root_subject,
        i.metadata,
        (
            SELECT max(e.occurred_at)
            FROM public.outbound_events e
            WHERE e.intent_id=i.id
              AND e.event_type='delivered'
        ) AS delivered_at
    FROM public.outbound_intents i
    WHERE i.channel='email'
      AND i.status='delivered'
      AND COALESCE(
        i.metadata->>'sequence_kind',
        'first_touch'
      ) <> 'followup'
      AND i.metadata ? 'buyer_candidate_review_id'
),
eligible AS (
    SELECT
        r.*,
        COALESCE((
            SELECT count(*)
            FROM public.outbound_intents f
            WHERE f.metadata->>'sequence_kind'='followup'
              AND f.metadata->>'root_intent_id'=r.root_intent_id::text
              AND f.status NOT IN ('cancelled','rejected')
        ),0)::integer AS followup_count,
        (
            SELECT max(e.occurred_at)
            FROM public.outbound_intents f
            JOIN public.outbound_events e ON e.intent_id=f.id
            WHERE f.metadata->>'sequence_kind'='followup'
              AND f.metadata->>'root_intent_id'=r.root_intent_id::text
              AND f.metadata->>'followup_step'='1'
              AND e.event_type='delivered'
        ) AS first_followup_delivered_at
    FROM roots r
    WHERE r.delivered_at IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM public.outbound_suppressions s
          WHERE s.normalized_contact=r.normalized_recipient
      )
      AND NOT EXISTS (
          SELECT 1
          FROM public.outbound_replies rep
          JOIN public.outbound_intents ri ON ri.id=rep.intent_id
          WHERE ri.normalized_recipient=r.normalized_recipient
      )
      AND NOT EXISTS (
          SELECT 1
          FROM public.outbound_events e
          JOIN public.outbound_intents ei ON ei.id=e.intent_id
          WHERE ei.normalized_recipient=r.normalized_recipient
            AND e.event_type IN (
              'bounced','complained','failed','suppressed'
            )
      )
),
due AS (
    SELECT
        e.*,
        CASE
          WHEN e.followup_count=0
               AND e.delivered_at <= now()-interval '24 hours'
            THEN 1
          WHEN e.followup_count=1
               AND e.first_followup_delivered_at IS NOT NULL
               AND e.delivered_at <= now()-interval '72 hours'
               AND e.first_followup_delivered_at <= now()-interval '24 hours'
            THEN 2
          ELSE NULL
        END AS followup_step
    FROM eligible e
),
hydrated AS (
    SELECT
        d.*,
        review.id AS current_review_id,
        review.company_score AS current_company_score,
        review.decision_score AS current_decision_score,
        (
          COALESCE(d.metadata->'candidate_evidence','{}'::jsonb)
          || COALESCE(review.evidence,'{}'::jsonb)
          || jsonb_strip_nulls(jsonb_build_object(
               'contact_name',review.contact_name,
               'contact_title',review.contact_title,
               'contact_source',review.evidence->>'contact_source'
             ))
          || jsonb_strip_nulls(jsonb_build_object(
               'business_name',prospect.business_name,
               'niche',prospect.niche,
               'metro',prospect.metro,
               'website',prospect.website,
               'phone',prospect.phone,
               'rating',prospect.rating,
               'review_count',prospect.review_count,
               'buy_signal_score',prospect.buy_signal_score
             ))
        ) AS hydrated_candidate_evidence
    FROM due d
    LEFT JOIN public.buyer_candidate_reviews review
      ON review.id::text=d.metadata->>'buyer_candidate_review_id'
    LEFT JOIN public.prospects prospect
      ON prospect.id=d.prospect_id
    WHERE d.followup_step IS NOT NULL
)
SELECT COALESCE(
    jsonb_agg(
        jsonb_build_object(
            'root_intent_id',h.root_intent_id,
            'review_id',COALESCE(
              h.current_review_id::text,
              h.metadata->>'buyer_candidate_review_id'
            ),
            'recipient',h.recipient,
            'normalized_recipient',h.normalized_recipient,
            'offer_key',h.offer_key,
            'root_subject',h.root_subject,
            'delivered_at',h.delivered_at,
            'followup_step',h.followup_step,
            'candidate_evidence',h.hydrated_candidate_evidence,
            'recipient_locale',
              h.hydrated_candidate_evidence->'locale',
            'company_score',COALESCE(
              to_jsonb(h.current_company_score),
              h.metadata->'company_score'
            ),
            'decision_score',COALESCE(
              to_jsonb(h.current_decision_score),
              h.metadata->'decision_score'
            )
        )
        ORDER BY h.delivered_at,h.root_intent_id
    ),
    '[]'::jsonb
)
FROM (
    SELECT *
    FROM hydrated
    ORDER BY delivered_at,root_intent_id
    LIMIT LEAST(GREATEST(COALESCE(p_limit,25),1),100)
) h;
$$;


CREATE OR REPLACE FUNCTION public.propose_outbound_followup(
    p_root_intent_id uuid,
    p_step integer,
    p_subject text,
    p_body_text text,
    p_idempotency_key text,
    p_proposed_by text,
    p_expires_at timestamptz
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
    root public.outbound_intents%ROWTYPE;
    review public.buyer_candidate_reviews%ROWTYPE;
    delivered_at timestamptz;
    existing_count integer;
    first_followup_delivered timestamptz;
    review_id uuid;
    result jsonb;
    merged jsonb;
BEGIN
    IF p_step NOT IN (1,2) THEN
        RAISE EXCEPTION 'follow-up step must be 1 or 2';
    END IF;

    SELECT * INTO root
    FROM public.outbound_intents
    WHERE id=p_root_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'root outbound intent not found';
    END IF;

    IF root.channel<>'email'
       OR root.status<>'delivered'
       OR COALESCE(root.metadata->>'sequence_kind','first_touch')='followup' THEN
        RAISE EXCEPTION 'delivered first-touch email required';
    END IF;

    BEGIN
        review_id := (root.metadata->>'buyer_candidate_review_id')::uuid;
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'buyer candidate review reference required';
    END;

    SELECT * INTO review
    FROM public.buyer_candidate_reviews
    WHERE id=review_id;

    IF NOT FOUND
       OR review.status<>'approved'
       OR COALESCE(lower(review.evidence->>'outreach_ready'),'false')<>'true' THEN
        RAISE EXCEPTION 'approved outreach-ready buyer review required';
    END IF;

    SELECT max(e.occurred_at) INTO delivered_at
    FROM public.outbound_events e
    WHERE e.intent_id=root.id
      AND e.event_type='delivered';

    IF delivered_at IS NULL THEN
        RAISE EXCEPTION 'root delivery evidence required';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
        WHERE s.normalized_contact=root.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_replies rep
        JOIN public.outbound_intents ri ON ri.id=rep.intent_id
        WHERE ri.normalized_recipient=root.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'reply already observed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_events e
        JOIN public.outbound_intents ei ON ei.id=e.intent_id
        WHERE ei.normalized_recipient=root.normalized_recipient
          AND e.event_type IN ('bounced','complained','failed','suppressed')
    ) THEN
        RAISE EXCEPTION 'negative delivery evidence stops follow-up';
    END IF;

    SELECT count(*)::integer INTO existing_count
    FROM public.outbound_intents f
    WHERE f.metadata->>'sequence_kind'='followup'
      AND f.metadata->>'root_intent_id'=root.id::text
      AND f.status NOT IN ('cancelled','rejected');

    IF existing_count <> p_step-1 THEN
        RAISE EXCEPTION 'follow-up sequence state mismatch';
    END IF;

    IF p_step=1 AND delivered_at > clock_timestamp()-interval '24 hours' THEN
        RAISE EXCEPTION 'first follow-up cooldown active';
    END IF;

    IF p_step=2 THEN
        SELECT max(e.occurred_at) INTO first_followup_delivered
        FROM public.outbound_intents f
        JOIN public.outbound_events e ON e.intent_id=f.id
        WHERE f.metadata->>'sequence_kind'='followup'
          AND f.metadata->>'root_intent_id'=root.id::text
          AND f.metadata->>'followup_step'='1'
          AND e.event_type='delivered';

        IF first_followup_delivered IS NULL THEN
            RAISE EXCEPTION 'first follow-up delivery required';
        END IF;
        IF delivered_at > clock_timestamp()-interval '72 hours' THEN
            RAISE EXCEPTION 'final follow-up root cooldown active';
        END IF;
        IF first_followup_delivered > clock_timestamp()-interval '24 hours' THEN
            RAISE EXCEPTION 'final follow-up step cooldown active';
        END IF;
    END IF;

    IF trim(COALESCE(p_subject,''))=''
       OR trim(COALESCE(p_body_text,''))='' THEN
        RAISE EXCEPTION 'follow-up subject and body required';
    END IF;

    IF lower(p_body_text) NOT LIKE '%opt out%'
       AND lower(p_body_text) NOT LIKE '%unsubscribe%'
       AND lower(p_body_text) NOT LIKE '%opt-out%' THEN
        RAISE EXCEPTION 'visible opt-out required';
    END IF;

    IF lower(p_body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
        RAISE EXCEPTION 'approved postal footer required';
    END IF;

    merged := COALESCE(root.metadata,'{}'::jsonb)
      || jsonb_build_object(
        'sequence_kind','followup',
        'root_intent_id',root.id,
        'followup_step',p_step,
        'buyer_candidate_review_id',review.id,
        'candidate_evidence',review.evidence,
        'company_score',review.company_score,
        'decision_score',review.decision_score
      );

    result := public.propose_outbound_intent(
        root.entity_id,
        root.prospect_id,
        root.buyer_id,
        root.opportunity_id,
        'email',
        root.recipient,
        p_subject,
        p_body_text,
        NULL,
        root.offer_key,
        p_idempotency_key,
        p_proposed_by,
        p_expires_at,
        merged
    );

    RETURN result || jsonb_build_object(
        'root_intent_id',root.id,
        'followup_step',p_step,
        'sequence_kind','followup'
    );
END;
$$;


CREATE OR REPLACE FUNCTION public.auto_approve_outbound_followup(
    p_intent_id uuid,
    p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
    i public.outbound_intents%ROWTYPE;
    root public.outbound_intents%ROWTYPE;
    root_id uuid;
    step integer;
    delivered_at timestamptz;
    first_followup_delivered timestamptz;
    approved_today integer;
    result jsonb;
BEGIN
    IF p_daily_cap IS NULL OR p_daily_cap<1 OR p_daily_cap>50 THEN
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

    IF i.status<>'pending_approval'
       OR i.expires_at<=clock_timestamp()
       OR i.channel<>'email'
       OR i.metadata->>'sequence_kind'<>'followup' THEN
        RAISE EXCEPTION 'current pending follow-up intent required';
    END IF;

    BEGIN
        root_id := (i.metadata->>'root_intent_id')::uuid;
        step := (i.metadata->>'followup_step')::integer;
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'valid follow-up metadata required';
    END;

    IF step NOT IN (1,2) THEN
        RAISE EXCEPTION 'invalid follow-up step';
    END IF;

    SELECT * INTO root
    FROM public.outbound_intents
    WHERE id=root_id;

    IF NOT FOUND OR root.status<>'delivered' THEN
        RAISE EXCEPTION 'delivered root intent required';
    END IF;

    IF i.normalized_recipient<>root.normalized_recipient THEN
        RAISE EXCEPTION 'follow-up recipient mismatch';
    END IF;

    SELECT max(e.occurred_at) INTO delivered_at
    FROM public.outbound_events e
    WHERE e.intent_id=root.id
      AND e.event_type='delivered';

    IF delivered_at IS NULL THEN
        RAISE EXCEPTION 'root delivery evidence required';
    END IF;

    IF step=1 AND delivered_at > clock_timestamp()-interval '24 hours' THEN
        RAISE EXCEPTION 'first follow-up cooldown active';
    END IF;

    IF step=2 THEN
        SELECT max(e.occurred_at) INTO first_followup_delivered
        FROM public.outbound_intents f
        JOIN public.outbound_events e ON e.intent_id=f.id
        WHERE f.metadata->>'sequence_kind'='followup'
          AND f.metadata->>'root_intent_id'=root.id::text
          AND f.metadata->>'followup_step'='1'
          AND f.id<>i.id
          AND e.event_type='delivered';

        IF first_followup_delivered IS NULL
           OR delivered_at > clock_timestamp()-interval '72 hours'
           OR first_followup_delivered > clock_timestamp()-interval '24 hours' THEN
            RAISE EXCEPTION 'final follow-up is not due';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
        WHERE s.normalized_contact=i.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_replies rep
        JOIN public.outbound_intents ri ON ri.id=rep.intent_id
        WHERE ri.normalized_recipient=i.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'reply already observed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_events e
        JOIN public.outbound_intents ei ON ei.id=e.intent_id
        WHERE ei.normalized_recipient=i.normalized_recipient
          AND ei.id<>i.id
          AND e.event_type IN ('bounced','complained','failed','suppressed')
    ) THEN
        RAISE EXCEPTION 'negative delivery evidence stops follow-up';
    END IF;

    IF lower(i.body_text) NOT LIKE '%opt out%'
       AND lower(i.body_text) NOT LIKE '%unsubscribe%'
       AND lower(i.body_text) NOT LIKE '%opt-out%' THEN
        RAISE EXCEPTION 'visible opt-out required';
    END IF;

    IF lower(i.body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
        RAISE EXCEPTION 'approved postal footer required';
    END IF;

    SELECT count(*)::integer INTO approved_today
    FROM public.outbound_events e
    WHERE e.event_type='approved'
      AND e.actor='gtm-standing-authority'
      AND e.occurred_at>=date_trunc('day',clock_timestamp());

    IF approved_today>=p_daily_cap THEN
        RAISE EXCEPTION 'standing authority daily outbound cap reached';
    END IF;

    result := public.approve_outbound_intent(
        i.id,
        'gtm-standing-authority',
        'Approved automatically under bounded no-reply follow-up authority.'
    );

    RETURN result || jsonb_build_object(
        'standing_authority',true,
        'sequence_kind','followup',
        'followup_step',step,
        'actual_revenue',false
    );
END;
$$;



COMMENT ON FUNCTION public.list_due_outbound_followups(integer) IS
'Lists governed no-reply follow-ups due at +24h and final +72h cadence with canonical context.';
COMMENT ON FUNCTION public.propose_outbound_followup(
    uuid,integer,text,text,text,text,timestamptz
) IS
'Creates one of at most two governed no-reply follow-ups at the 24h/72h revenue-sprint cadence.';
COMMENT ON FUNCTION public.auto_approve_outbound_followup(uuid,integer) IS
'Approves only due no-reply follow-up intents under the bounded 24h/72h cadence and existing safety gates.';

COMMIT;
