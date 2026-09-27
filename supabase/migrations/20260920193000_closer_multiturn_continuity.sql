-- Multi-turn continuity and idempotency for governed closer conversations.
BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS closer_recommendations_reply_id_uidx
  ON public.closer_recommendations ((rationale->>'reply_id'))
  WHERE COALESCE(rationale->>'reply_id','') <> '';

CREATE OR REPLACE FUNCTION public.record_closer_recommendation(
  p_case_id uuid,
  p_type text,
  p_confidence numeric,
  p_rationale jsonb,
  p_message text,
  p_model_key text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  r public.closer_recommendations%ROWTYPE;
  v text := lower(trim(p_type));
  v_reply_id text := trim(COALESCE(p_rationale->>'reply_id',''));
BEGIN
  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost') THEN RAISE EXCEPTION 'terminal closer case'; END IF;
  IF v NOT IN (
    'qualify','follow_up','answer_question','handle_objection',
    'prepare_proposal','await_payment','pause','mark_lost','escalate_human'
  ) THEN
    RAISE EXCEPTION 'unsupported closer recommendation';
  END IF;
  IF p_confidence IS NULL OR p_confidence<0 OR p_confidence>1 THEN
    RAISE EXCEPTION 'invalid confidence';
  END IF;

  IF v_reply_id <> '' THEN
    SELECT * INTO r
      FROM public.closer_recommendations
     WHERE rationale->>'reply_id'=v_reply_id
     LIMIT 1;
    IF FOUND THEN
      IF r.case_id IS DISTINCT FROM c.id THEN
        RAISE EXCEPTION 'reply recommendation belongs to different closer case';
      END IF;
      RETURN jsonb_build_object(
        'decision','existing',
        'recommendation_id',r.id,
        'case_id',c.id,
        'state',c.state,
        'actual_revenue',false
      );
    END IF;
  END IF;

  INSERT INTO public.closer_recommendations(
    case_id,recommendation_type,confidence,rationale,proposed_message,model_key
  ) VALUES(
    c.id,v,p_confidence,COALESCE(p_rationale,'{}'::jsonb),p_message,trim(p_model_key)
  ) RETURNING * INTO r;

  INSERT INTO public.closer_events(case_id,event_type,actor,payload)
  VALUES(
    c.id,
    'recommendation_recorded',
    'closer-planner',
    jsonb_build_object(
      'recommendation_id',r.id,
      'type',v,
      'confidence',p_confidence,
      'model_key',r.model_key,
      'reply_id',NULLIF(v_reply_id,'')
    )
  );

  RETURN jsonb_build_object(
    'decision','recorded',
    'recommendation_id',r.id,
    'case_id',c.id,
    'state',c.state,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.list_closer_work(p_limit integer DEFAULT 50)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path=''
AS $$
  SELECT COALESCE(
    jsonb_agg(to_jsonb(q) ORDER BY q.received_at DESC),
    '[]'::jsonb
  )
  FROM (
    SELECT
      r.id AS reply_id,
      r.intent_id AS outbound_intent_id,
      r.classification,
      r.confidence,
      r.received_at,
      COALESCE(c_direct.id,c_thread.id) AS case_id,
      COALESCE(c_direct.state,c_thread.state) AS case_state,
      CASE
        WHEN c_direct.id IS NOT NULL THEN 'direct'
        WHEN c_thread.id IS NOT NULL THEN 'threaded'
        ELSE 'new'
      END AS case_origin,
      COALESCE(c_direct.prospect_id,c_thread.prospect_id,i.prospect_id) AS prospect_id,
      COALESCE(c_direct.entity_id,c_thread.entity_id,i.entity_id) AS entity_id,
      COALESCE(c_direct.buyer_id,c_thread.buyer_id,i.buyer_id) AS buyer_id,
      COALESCE(c_direct.opportunity_id,c_thread.opportunity_id,i.opportunity_id) AS opportunity_id,
      COALESCE(c_direct.fulfilment_order_id,c_thread.fulfilment_order_id) AS fulfilment_order_id
    FROM public.outbound_replies r
    JOIN public.outbound_intents i ON i.id=r.intent_id
    LEFT JOIN public.closer_cases c_direct ON c_direct.reply_id=r.id
    LEFT JOIN public.closer_cases c_thread
      ON c_thread.id = CASE
        WHEN COALESCE(i.metadata->>'closer_case_id','') ~
             '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
        THEN (i.metadata->>'closer_case_id')::uuid
        ELSE NULL
      END
    WHERE r.classification IN ('positive','question','objection')
      AND COALESCE(c_direct.state,c_thread.state,'engaged') NOT IN ('won','lost','paused')
      AND NOT EXISTS (
        SELECT 1
          FROM public.closer_recommendations rec
         WHERE rec.rationale->>'reply_id'=r.id::text
      )
    ORDER BY r.received_at DESC
    LIMIT LEAST(GREATEST(COALESCE(p_limit,50),1),500)
  ) q;
$$;

CREATE OR REPLACE FUNCTION public.get_closer_reply_context(
    p_case_id uuid,
    p_reply_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
BEGIN
  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;

  SELECT * INTO r FROM public.outbound_replies WHERE id=p_reply_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply not found'; END IF;

  SELECT * INTO i FROM public.outbound_intents WHERE id=r.intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply intent not found'; END IF;

  IF r.id IS DISTINCT FROM c.reply_id
     AND COALESCE(i.metadata->>'closer_case_id','') IS DISTINCT FROM c.id::text THEN
    RAISE EXCEPTION 'reply does not belong to closer case';
  END IF;

  RETURN jsonb_build_object(
    'case_id',c.id,
    'case_state',c.state,
    'reply_id',r.id,
    'classification',r.classification,
    'confidence',r.confidence,
    'received_at',r.received_at,
    'reply_subject',r.subject,
    'reply_body_text',r.body_text,
    'from_contact',r.from_contact,
    'root_intent_id',c.outbound_intent_id,
    'source_intent_id',i.id,
    'root_subject',COALESCE(
      (SELECT root.subject FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id),
      i.subject
    ),
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
       WHERE br.id=CASE
         WHEN COALESCE(i.metadata->>'buyer_candidate_review_id','') ~
              '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
         THEN (i.metadata->>'buyer_candidate_review_id')::uuid
         ELSE NULL
       END
       LIMIT 1
    ),
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.propose_closer_reply_intent(
    p_case_id uuid,
    p_reply_id uuid,
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
    source_intent public.outbound_intents%ROWTYPE;
    root public.outbound_intents%ROWTYPE;
    result jsonb;
    merged jsonb;
BEGIN
    SELECT * INTO c
      FROM public.closer_cases
     WHERE id=p_case_id
     FOR UPDATE;

    IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
    IF c.state IN ('won','lost','paused') THEN RAISE EXCEPTION 'active closer case required'; END IF;
    IF c.buyer_id IS NULL THEN RAISE EXCEPTION 'prospective buyer must be provisioned first'; END IF;

    SELECT * INTO x FROM public.outbound_replies WHERE id=p_reply_id;
    IF NOT FOUND
       OR x.classification NOT IN ('positive','question','objection') THEN
        RAISE EXCEPTION 'commercially engaged inbound reply required';
    END IF;

    SELECT * INTO source_intent FROM public.outbound_intents WHERE id=x.intent_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'reply source intent not found'; END IF;

    SELECT * INTO root FROM public.outbound_intents WHERE id=c.outbound_intent_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'root outbound intent not found'; END IF;

    IF x.id IS DISTINCT FROM c.reply_id
       AND COALESCE(source_intent.metadata->>'closer_case_id','') IS DISTINCT FROM c.id::text THEN
        RAISE EXCEPTION 'reply does not belong to closer case';
    END IF;

    IF lower(trim(COALESCE(x.from_contact,''))) IS DISTINCT FROM root.normalized_recipient THEN
        RAISE EXCEPTION 'reply sender does not match governed recipient';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
         WHERE s.normalized_contact=root.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF trim(COALESCE(p_subject,''))='' OR trim(COALESCE(p_body_text,''))='' THEN
        RAISE EXCEPTION 'closer reply subject and body required';
    END IF;

    merged := jsonb_build_object(
        'sequence_kind','closer_reply',
        'root_intent_id',root.id,
        'source_intent_id',source_intent.id,
        'closer_case_id',c.id,
        'inbound_reply_id',x.id,
        'reply_classification',x.classification,
        'buyer_candidate_review_id',root.metadata->>'buyer_candidate_review_id',
        'candidate_evidence',root.metadata->'candidate_evidence',
        'commercial_commitment',false,
        'actual_revenue',false
    );

    result := public.propose_outbound_intent(
        c.entity_id,c.prospect_id,c.buyer_id,c.opportunity_id,
        'email',x.from_contact,p_subject,p_body_text,NULL,root.offer_key,
        p_idempotency_key,p_proposed_by,p_expires_at,merged
    );

    RETURN result || jsonb_build_object(
        'sequence_kind','closer_reply',
        'closer_case_id',c.id,
        'inbound_reply_id',x.id
    );
END;
$$;

REVOKE ALL ON FUNCTION public.get_closer_reply_context(uuid,uuid)
  FROM PUBLIC,anon,authenticated,empire_closer_approver;
REVOKE ALL ON FUNCTION public.propose_closer_reply_intent(
    uuid,uuid,text,text,text,text,timestamptz
) FROM PUBLIC,anon,authenticated,empire_closer_approver;

GRANT EXECUTE ON FUNCTION public.get_closer_reply_context(uuid,uuid)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.propose_closer_reply_intent(
    uuid,uuid,text,text,text,text,timestamptz
) TO service_role;

COMMENT ON FUNCTION public.list_closer_work(integer) IS
'Returns only unprocessed commercial replies, preserving multi-turn replies inside their existing closer case.';

COMMENT ON FUNCTION public.get_closer_reply_context(uuid,uuid) IS
'Reads the exact inbound reply within a governed closer case, including later replies to prior closer messages.';

COMMIT;
