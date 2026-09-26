-- Governed closer reply lane for genuine buyer conversations.
-- Allows a bounded reply only when it is linked to a classified real inbound
-- reply and a non-terminal closer case. It does not accept commercial terms,
-- move funds, confirm payment, fulfil work, or recognize revenue.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_closer_reply_context(
    p_case_id uuid
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
  SELECT jsonb_build_object(
    'case_id',c.id,
    'case_state',c.state,
    'reply_id',r.id,
    'classification',r.classification,
    'confidence',r.confidence,
    'received_at',r.received_at,
    'reply_subject',r.subject,
    'reply_body_text',r.body_text,
    'from_contact',r.from_contact,
    'root_intent_id',i.id,
    'root_subject',i.subject,
    'offer_key',i.offer_key,
    'prospect_id',c.prospect_id,
    'entity_id',c.entity_id,
    'buyer_id',c.buyer_id,
    'opportunity_id',c.opportunity_id,
    'business_name',i.metadata->'candidate_evidence'->>'business_name',
    'niche',i.metadata->'candidate_evidence'->>'niche',
    'metro',i.metadata->'candidate_evidence'->>'metro',
    'contact_name',(
        SELECT br.contact_name
          FROM public.buyer_candidate_reviews br
         WHERE br.id=(i.metadata->>'buyer_candidate_review_id')::uuid
         LIMIT 1
    ),
    'actual_revenue',false
  )
  FROM public.closer_cases c
  JOIN public.outbound_replies r ON r.id=c.reply_id
  JOIN public.outbound_intents i ON i.id=c.outbound_intent_id
  WHERE c.id=p_case_id;
$$;

CREATE OR REPLACE FUNCTION public.propose_closer_reply_intent(
    p_case_id uuid,
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
    c public.closer_cases%ROWTYPE;
    x public.outbound_replies%ROWTYPE;
    root public.outbound_intents%ROWTYPE;
    result jsonb;
    merged jsonb;
BEGIN
    SELECT * INTO c
      FROM public.closer_cases
     WHERE id=p_case_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'closer case not found';
    END IF;

    IF c.state IN ('won','lost','paused') THEN
        RAISE EXCEPTION 'active closer case required';
    END IF;

    IF c.buyer_id IS NULL THEN
        RAISE EXCEPTION 'prospective buyer must be provisioned first';
    END IF;

    SELECT * INTO x
      FROM public.outbound_replies
     WHERE id=c.reply_id;

    IF NOT FOUND
       OR x.classification NOT IN ('positive','question','objection') THEN
        RAISE EXCEPTION 'commercially engaged inbound reply required';
    END IF;

    SELECT * INTO root
      FROM public.outbound_intents
     WHERE id=c.outbound_intent_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'root outbound intent not found';
    END IF;

    IF root.id IS DISTINCT FROM x.intent_id THEN
        RAISE EXCEPTION 'reply/root intent mismatch';
    END IF;

    IF lower(trim(COALESCE(x.from_contact,''))) IS DISTINCT FROM root.normalized_recipient THEN
        RAISE EXCEPTION 'reply sender does not match governed recipient';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.outbound_suppressions s
         WHERE s.normalized_contact=root.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF trim(COALESCE(p_subject,''))=''
       OR trim(COALESCE(p_body_text,''))='' THEN
        RAISE EXCEPTION 'closer reply subject and body required';
    END IF;

    merged := jsonb_build_object(
        'sequence_kind','closer_reply',
        'root_intent_id',root.id,
        'closer_case_id',c.id,
        'inbound_reply_id',x.id,
        'reply_classification',x.classification,
        'buyer_candidate_review_id',root.metadata->>'buyer_candidate_review_id',
        'candidate_evidence',root.metadata->'candidate_evidence',
        'commercial_commitment',false,
        'actual_revenue',false
    );

    result := public.propose_outbound_intent(
        c.entity_id,
        c.prospect_id,
        c.buyer_id,
        c.opportunity_id,
        'email',
        x.from_contact,
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
        'sequence_kind','closer_reply',
        'closer_case_id',c.id,
        'inbound_reply_id',x.id
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.auto_approve_closer_reply_intent(
    p_intent_id uuid,
    p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
    i public.outbound_intents%ROWTYPE;
    c public.closer_cases%ROWTYPE;
    x public.outbound_replies%ROWTYPE;
    root public.outbound_intents%ROWTYPE;
    case_id uuid;
    reply_id uuid;
    root_id uuid;
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
       OR i.metadata->>'sequence_kind'<>'closer_reply' THEN
        RAISE EXCEPTION 'current pending closer reply intent required';
    END IF;

    BEGIN
        case_id := (i.metadata->>'closer_case_id')::uuid;
        reply_id := (i.metadata->>'inbound_reply_id')::uuid;
        root_id := (i.metadata->>'root_intent_id')::uuid;
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'valid closer reply metadata required';
    END;

    SELECT * INTO c FROM public.closer_cases WHERE id=case_id;
    SELECT * INTO x FROM public.outbound_replies WHERE id=reply_id;
    SELECT * INTO root FROM public.outbound_intents WHERE id=root_id;

    IF c.id IS NULL OR x.id IS NULL OR root.id IS NULL THEN
        RAISE EXCEPTION 'closer reply evidence missing';
    END IF;

    IF c.state IN ('won','lost','paused')
       OR c.buyer_id IS NULL THEN
        RAISE EXCEPTION 'active buyer-bound closer case required';
    END IF;

    IF x.intent_id IS DISTINCT FROM root.id
       OR x.classification NOT IN ('positive','question','objection') THEN
        RAISE EXCEPTION 'commercially engaged inbound reply required';
    END IF;

    IF i.buyer_id IS DISTINCT FROM c.buyer_id
       OR i.prospect_id IS DISTINCT FROM c.prospect_id
       OR i.normalized_recipient IS DISTINCT FROM x.normalized_from_contact
       OR i.normalized_recipient IS DISTINCT FROM root.normalized_recipient THEN
        RAISE EXCEPTION 'closer reply identity mismatch';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.outbound_suppressions s
         WHERE s.normalized_contact=i.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.outbound_replies newer
         WHERE newer.normalized_from_contact=i.normalized_recipient
           AND newer.received_at>x.received_at
           AND newer.classification IN ('negative','unsubscribe','bounce')
    ) THEN
        RAISE EXCEPTION 'newer negative reply stops closer response';
    END IF;

    IF lower(i.body_text) NOT LIKE '%opt out%'
       AND lower(i.body_text) NOT LIKE '%unsubscribe%'
       AND lower(i.body_text) NOT LIKE '%opt-out%' THEN
        RAISE EXCEPTION 'visible opt-out required';
    END IF;

    IF lower(i.body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
        RAISE EXCEPTION 'approved postal footer required';
    END IF;

    IF COALESCE((i.metadata->>'commercial_commitment')::boolean,true) IS NOT FALSE THEN
        RAISE EXCEPTION 'closer reply must not contain binding commercial commitment authority';
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
        'Approved automatically under bounded closer-reply authority.'
    );

    RETURN result || jsonb_build_object(
        'standing_authority',true,
        'sequence_kind','closer_reply',
        'closer_case_id',c.id,
        'actual_revenue',false
    );
END;
$$;

REVOKE ALL ON FUNCTION public.get_closer_reply_context(uuid)
  FROM PUBLIC,anon,authenticated,empire_closer_approver;
REVOKE ALL ON FUNCTION public.propose_closer_reply_intent(
    uuid,text,text,text,text,timestamptz
) FROM PUBLIC,anon,authenticated,empire_closer_approver;
REVOKE ALL ON FUNCTION public.auto_approve_closer_reply_intent(uuid,integer)
  FROM PUBLIC,anon,authenticated,empire_outbound_approver,
       empire_outbound_sender,empire_reply_ingest;

GRANT EXECUTE ON FUNCTION public.get_closer_reply_context(uuid)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.propose_closer_reply_intent(
    uuid,text,text,text,text,timestamptz
) TO service_role;
GRANT EXECUTE ON FUNCTION public.auto_approve_closer_reply_intent(uuid,integer)
  TO service_role;

COMMENT ON FUNCTION public.propose_closer_reply_intent(
    uuid,text,text,text,text,timestamptz
) IS
'Creates a pending outbound reply only from a genuine classified buyer reply and buyer-bound active closer case.';

COMMENT ON FUNCTION public.auto_approve_closer_reply_intent(uuid,integer) IS
'Approves only a non-binding closer reply tied to real inbound evidence, with suppression and daily-cap checks.';

COMMIT;
