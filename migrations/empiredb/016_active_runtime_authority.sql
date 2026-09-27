-- EmpireDB active runtime authority parity.
-- Generated from governed production migration contracts already in this repo.
-- All imported functions are SECURITY INVOKER on EmpireDB.
-- No canonical cutover, no outbound execution, no funds movement in this migration.

SET ROLE empiredb_migrator;

CREATE TABLE IF NOT EXISTS public.closer_recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  recommendation_type text NOT NULL CHECK (recommendation_type IN (
    'qualify','follow_up','answer_question','handle_objection','prepare_proposal',
    'await_payment','pause','mark_lost','escalate_human'
  )),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  rationale jsonb NOT NULL DEFAULT '{}'::jsonb,
  proposed_message text,
  model_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS closer_recommendations_case_idx
  ON public.closer_recommendations(case_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS closer_recommendations_reply_id_uidx
  ON public.closer_recommendations ((rationale->>'reply_id'))
  WHERE COALESCE(rationale->>'reply_id','') <> '';

CREATE TABLE IF NOT EXISTS public.closer_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  event_type text NOT NULL,
  actor text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS closer_events_case_idx
  ON public.closer_events(case_id,occurred_at DESC);

ALTER TABLE public.closer_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.closer_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.closer_recommendations,public.closer_events FROM PUBLIC;

GRANT SELECT,INSERT ON public.closer_recommendations,public.closer_events
TO empiredb_app,empire_closer_planner;
GRANT SELECT ON public.closer_recommendations,public.closer_events
TO empire_closer_approver;

DROP POLICY IF EXISTS closer_recommendations_app_all ON public.closer_recommendations;
CREATE POLICY closer_recommendations_app_all ON public.closer_recommendations
FOR ALL TO empiredb_app USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS closer_events_app_all ON public.closer_events;
CREATE POLICY closer_events_app_all ON public.closer_events
FOR ALL TO empiredb_app USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS closer_recommendations_planner ON public.closer_recommendations;
CREATE POLICY closer_recommendations_planner ON public.closer_recommendations
FOR SELECT TO empire_closer_planner USING (true);
DROP POLICY IF EXISTS closer_recommendations_planner_insert ON public.closer_recommendations;
CREATE POLICY closer_recommendations_planner_insert ON public.closer_recommendations
FOR INSERT TO empire_closer_planner WITH CHECK (true);
DROP POLICY IF EXISTS closer_events_planner ON public.closer_events;
CREATE POLICY closer_events_planner ON public.closer_events
FOR SELECT TO empire_closer_planner USING (true);
DROP POLICY IF EXISTS closer_events_planner_insert ON public.closer_events;
CREATE POLICY closer_events_planner_insert ON public.closer_events
FOR INSERT TO empire_closer_planner WITH CHECK (true);

-- Existing application role mirrors the legacy service-role proposal/read paths.
GRANT SELECT,INSERT,UPDATE ON public.buyer_capacity_intakes TO empiredb_app;
GRANT SELECT,INSERT,UPDATE ON public.commercial_terms_reviews TO empiredb_app;
GRANT SELECT,INSERT ON public.commercial_terms_events TO empiredb_app;
GRANT SELECT,INSERT ON public.bsc_payment_requests TO empiredb_app;
GRANT SELECT,INSERT ON public.bsc_payment_request_events TO empiredb_app;
GRANT SELECT ON public.bsc_payment_evidence,public.bsc_escrow_agreements,
  public.bsc_escrow_evidence TO empiredb_app;

-- Dedicated capability roles. Table privileges remain narrower than function grants.
GRANT SELECT ON public.empire_conversations,public.empire_conversation_events
TO empire_conversation_reader,empire_conversation_ingest;
GRANT INSERT ON public.empire_conversation_events TO empire_conversation_ingest;

GRANT SELECT ON public.revenue_exchange_observations
TO empire_revenue_exchange_reader,empire_revenue_exchange_ingest;
GRANT INSERT ON public.revenue_exchange_observations
TO empire_revenue_exchange_ingest;

GRANT SELECT,UPDATE ON public.bsc_payment_requests TO empire_payment_approver;
GRANT SELECT ON public.fulfilment_orders,public.bsc_payment_evidence
TO empire_payment_approver;
GRANT INSERT ON public.bsc_payment_request_events TO empire_payment_approver;

GRANT SELECT ON public.bsc_payment_requests,public.fulfilment_orders,
  public.bsc_payment_evidence TO empire_bsc_verifier;
GRANT INSERT ON public.bsc_payment_evidence,public.bsc_payment_request_events
TO empire_bsc_verifier;

GRANT SELECT ON public.bsc_payment_requests,public.bsc_escrow_agreements,
  public.bsc_escrow_evidence TO empire_escrow_verifier;
GRANT INSERT,UPDATE ON public.bsc_escrow_agreements TO empire_escrow_verifier;
GRANT INSERT ON public.bsc_escrow_evidence TO empire_escrow_verifier;

GRANT SELECT,UPDATE ON public.commercial_terms_reviews TO empire_commercial_approver;
GRANT SELECT,UPDATE ON public.fulfilment_orders TO empire_commercial_approver;
GRANT SELECT,INSERT ON public.commercial_terms_events TO empire_commercial_approver;

GRANT SELECT,INSERT ON public.commercial_outcomes TO empire_outcome_recorder;
GRANT SELECT,UPDATE ON public.fulfilment_orders TO empire_outcome_recorder;
GRANT INSERT ON public.commercial_events TO empire_outcome_recorder;

GRANT SELECT,UPDATE ON public.fulfilment_orders TO empire_revenue_recognizer;
GRANT SELECT ON public.bsc_payment_requests,public.bsc_payment_evidence,
  public.bsc_escrow_agreements,public.bsc_escrow_evidence,
  public.commercial_outcomes TO empire_revenue_recognizer;
GRANT SELECT,INSERT ON public.commercial_events TO empire_revenue_recognizer;

-- RLS policies for dedicated lanes.
DROP POLICY IF EXISTS conversation_reader_conversations ON public.empire_conversations;
CREATE POLICY conversation_reader_conversations ON public.empire_conversations
FOR SELECT TO empire_conversation_reader USING (true);
DROP POLICY IF EXISTS conversation_reader_events ON public.empire_conversation_events;
CREATE POLICY conversation_reader_events ON public.empire_conversation_events
FOR SELECT TO empire_conversation_reader USING (true);
DROP POLICY IF EXISTS conversation_ingest_conversations ON public.empire_conversations;
CREATE POLICY conversation_ingest_conversations ON public.empire_conversations
FOR SELECT TO empire_conversation_ingest USING (true);
DROP POLICY IF EXISTS conversation_ingest_events_select ON public.empire_conversation_events;
CREATE POLICY conversation_ingest_events_select ON public.empire_conversation_events
FOR SELECT TO empire_conversation_ingest USING (true);
DROP POLICY IF EXISTS conversation_ingest_events_insert ON public.empire_conversation_events;
CREATE POLICY conversation_ingest_events_insert ON public.empire_conversation_events
FOR INSERT TO empire_conversation_ingest WITH CHECK (true);

DROP POLICY IF EXISTS revenue_exchange_reader_select ON public.revenue_exchange_observations;
CREATE POLICY revenue_exchange_reader_select ON public.revenue_exchange_observations
FOR SELECT TO empire_revenue_exchange_reader USING (true);
DROP POLICY IF EXISTS revenue_exchange_ingest_select ON public.revenue_exchange_observations;
CREATE POLICY revenue_exchange_ingest_select ON public.revenue_exchange_observations
FOR SELECT TO empire_revenue_exchange_ingest USING (true);
DROP POLICY IF EXISTS revenue_exchange_ingest_insert ON public.revenue_exchange_observations;
CREATE POLICY revenue_exchange_ingest_insert ON public.revenue_exchange_observations
FOR INSERT TO empire_revenue_exchange_ingest WITH CHECK (true);


CREATE OR REPLACE FUNCTION public.guard_outbound_events_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'outbound events are append-only';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.propose_outbound_intent(
    p_entity_id uuid, p_prospect_id uuid, p_buyer_id uuid, p_opportunity_id uuid,
    p_channel text, p_recipient text, p_subject text, p_body_text text,
    p_body_html text, p_offer_key text, p_idempotency_key text,
    p_proposed_by text, p_expires_at timestamptz, p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.outbound_intents%ROWTYPE; v_recipient text := lower(trim(COALESCE(p_recipient,'')));
BEGIN
    IF p_channel NOT IN ('email','sms','voice','a2a') THEN RAISE EXCEPTION 'unsupported outbound channel'; END IF;
    IF v_recipient='' OR length(trim(COALESCE(p_body_text,'')))<1 THEN RAISE EXCEPTION 'recipient and body required'; END IF;
    IF p_entity_id IS NULL AND p_prospect_id IS NULL AND p_buyer_id IS NULL THEN RAISE EXCEPTION 'canonical identity required'; END IF;
    IF p_expires_at <= clock_timestamp()+interval '5 minutes' OR p_expires_at > clock_timestamp()+interval '7 days' THEN RAISE EXCEPTION 'invalid outbound expiry'; END IF;
    IF EXISTS (SELECT 1 FROM public.outbound_suppressions WHERE normalized_contact=v_recipient) THEN RAISE EXCEPTION 'recipient suppressed'; END IF;
    SELECT * INTO r FROM public.outbound_intents WHERE idempotency_key=trim(p_idempotency_key);
    IF FOUND THEN RETURN jsonb_build_object('decision','existing','intent_id',r.id,'status',r.status,'actual_revenue',false); END IF;
    INSERT INTO public.outbound_intents(entity_id,prospect_id,buyer_id,opportunity_id,channel,recipient,normalized_recipient,subject,body_text,body_html,offer_key,status,idempotency_key,proposed_by,expires_at,metadata)
    VALUES(p_entity_id,p_prospect_id,p_buyer_id,p_opportunity_id,p_channel,p_recipient,v_recipient,p_subject,p_body_text,p_body_html,p_offer_key,'pending_approval',trim(p_idempotency_key),trim(p_proposed_by),p_expires_at,COALESCE(p_metadata,'{}')) RETURNING * INTO r;
    INSERT INTO public.outbound_events(intent_id,event_type,actor,payload) VALUES(r.id,'proposed',r.proposed_by,jsonb_build_object('channel',r.channel,'recipient',r.normalized_recipient));
    RETURN jsonb_build_object('decision','proposed','intent_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.approve_outbound_intent(p_intent_id uuid,p_approved_by text,p_note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.outbound_intents%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.outbound_intents WHERE id=p_intent_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'outbound intent not found'; END IF;
    IF r.status='approved' THEN RETURN jsonb_build_object('decision','existing_approval','intent_id',r.id,'status',r.status,'actual_revenue',false); END IF;
    IF r.status<>'pending_approval' OR r.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'current pending outbound intent required'; END IF;
    IF EXISTS(SELECT 1 FROM public.outbound_suppressions WHERE normalized_contact=r.normalized_recipient) THEN RAISE EXCEPTION 'recipient suppressed'; END IF;
    UPDATE public.outbound_intents SET status='approved',approved_by=trim(p_approved_by),approved_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=r.id RETURNING * INTO r;
    INSERT INTO public.outbound_events(intent_id,event_type,actor,payload) VALUES(r.id,'approved',r.approved_by,jsonb_build_object('note',trim(COALESCE(p_note,''))));
    RETURN jsonb_build_object('decision','approved','intent_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.claim_outbound_send(p_intent_id uuid,p_actor text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.outbound_intents%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.outbound_intents WHERE id=p_intent_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'outbound intent not found'; END IF;
    IF r.status<>'approved' OR r.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'approved unexpired outbound intent required'; END IF;
    IF EXISTS(SELECT 1 FROM public.outbound_suppressions WHERE normalized_contact=r.normalized_recipient) THEN RAISE EXCEPTION 'recipient suppressed'; END IF;
    INSERT INTO public.outbound_events(intent_id,event_type,actor,payload) VALUES(r.id,'send_attempt',trim(p_actor),jsonb_build_object('channel',r.channel));
    RETURN jsonb_build_object('decision','authorized_send','intent_id',r.id,'channel',r.channel,'recipient',r.recipient,'subject',r.subject,'body_text',r.body_text,'body_html',r.body_html,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.record_outbound_delivery(p_intent_id uuid,p_event_type text,p_actor text,p_provider_message_id text,p_payload jsonb DEFAULT '{}'::jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.outbound_intents%ROWTYPE; v_type text:=lower(trim(p_event_type));
BEGIN
    IF v_type NOT IN ('sent','delivered','failed') THEN RAISE EXCEPTION 'unsupported delivery event'; END IF;
    SELECT * INTO r FROM public.outbound_intents WHERE id=p_intent_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'outbound intent not found'; END IF;
    IF v_type='sent' AND r.status<>'approved' THEN RAISE EXCEPTION 'approved intent required'; END IF;
    IF v_type='delivered' AND r.status NOT IN ('sent','delivered') THEN RAISE EXCEPTION 'sent intent required'; END IF;
    UPDATE public.outbound_intents SET status=CASE WHEN v_type='failed' THEN 'failed' ELSE v_type END,updated_at=clock_timestamp() WHERE id=r.id RETURNING * INTO r;
    INSERT INTO public.outbound_events(intent_id,event_type,actor,provider_message_id,payload) VALUES(r.id,v_type,trim(p_actor),p_provider_message_id,COALESCE(p_payload,'{}'));
    RETURN jsonb_build_object('decision','recorded','intent_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.ingest_outbound_reply(p_intent_id uuid,p_provider_message_id text,p_from_contact text,p_subject text,p_body_text text,p_received_at timestamptz,p_metadata jsonb DEFAULT '{}'::jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.outbound_intents%ROWTYPE; x public.outbound_replies%ROWTYPE; v_from text:=lower(trim(p_from_contact));
BEGIN
    SELECT * INTO r FROM public.outbound_intents WHERE id=p_intent_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'outbound intent not found'; END IF;
    IF r.status NOT IN ('sent','delivered','replied') THEN RAISE EXCEPTION 'reply requires a sent intent'; END IF;
    INSERT INTO public.outbound_replies(intent_id,provider_message_id,from_contact,normalized_from_contact,subject,body_text,received_at,metadata)
    VALUES(r.id,p_provider_message_id,p_from_contact,v_from,p_subject,p_body_text,p_received_at,COALESCE(p_metadata,'{}'))
    ON CONFLICT(intent_id,provider_message_id) DO NOTHING RETURNING * INTO x;
    IF NOT FOUND THEN SELECT * INTO x FROM public.outbound_replies WHERE intent_id=r.id AND provider_message_id=p_provider_message_id; END IF;
    UPDATE public.outbound_intents SET status='replied',updated_at=clock_timestamp() WHERE id=r.id;
    INSERT INTO public.outbound_events(intent_id,event_type,actor,provider_message_id,payload) VALUES(r.id,'reply_received','reply_ingest',p_provider_message_id,jsonb_build_object('reply_id',x.id));
    RETURN jsonb_build_object('decision','recorded','reply_id',x.id,'intent_id',r.id,'classification',x.classification,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.classify_outbound_reply(p_reply_id uuid,p_classification text,p_confidence numeric,p_actor text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x public.outbound_replies%ROWTYPE; r public.outbound_intents%ROWTYPE; v text:=lower(trim(p_classification));
BEGIN
    IF v NOT IN ('positive','negative','question','objection','later','unsubscribe','bounce','other') THEN RAISE EXCEPTION 'unsupported reply classification'; END IF;
    IF p_confidence IS NULL OR p_confidence<0 OR p_confidence>1 THEN RAISE EXCEPTION 'invalid reply confidence'; END IF;
    SELECT * INTO x FROM public.outbound_replies WHERE id=p_reply_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'reply not found'; END IF;
    SELECT * INTO r FROM public.outbound_intents WHERE id=x.intent_id FOR UPDATE;
    UPDATE public.outbound_replies SET classification=v,confidence=p_confidence,classified_at=clock_timestamp() WHERE id=x.id RETURNING * INTO x;
    INSERT INTO public.outbound_events(intent_id,event_type,actor,provider_message_id,payload)
      VALUES(r.id,'reply_classified',trim(p_actor),x.provider_message_id,jsonb_build_object('reply_id',x.id,'classification',v,'confidence',p_confidence));
    IF v IN ('unsubscribe','bounce') THEN
      INSERT INTO public.outbound_suppressions(normalized_contact,contact_type,reason,source)
      VALUES(r.normalized_recipient,CASE WHEN r.channel='email' THEN 'email' ELSE 'phone' END,v,'reply')
      ON CONFLICT(normalized_contact) DO NOTHING;
      UPDATE public.outbound_intents SET status='suppressed',updated_at=clock_timestamp() WHERE id=r.id;
      INSERT INTO public.outbound_events(intent_id,event_type,actor,payload) VALUES(r.id,'suppressed',trim(p_actor),jsonb_build_object('reason',v));
    END IF;
    RETURN jsonb_build_object('decision','classified','reply_id',x.id,'classification',v,'suppressed',(v IN ('unsubscribe','bounce')),'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.get_outbound_intent_review(p_intent_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.outbound_intents%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.outbound_intents WHERE id=p_intent_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'outbound intent not found'; END IF;
    RETURN jsonb_build_object(
        'decision','review','intent_id',r.id,'channel',r.channel,
        'recipient',r.recipient,'subject',r.subject,'body_text',r.body_text,
        'body_html',r.body_html,'offer_key',r.offer_key,'status',r.status,
        'approved_by',r.approved_by,'approved_at',r.approved_at,
        'expires_at',r.expires_at,'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_closer_events_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'closer events are append-only'; END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.open_closer_case(p_reply_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x public.outbound_replies%ROWTYPE; i public.outbound_intents%ROWTYPE; c public.closer_cases%ROWTYPE;
BEGIN
  SELECT * INTO x FROM public.outbound_replies WHERE id=p_reply_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply not found'; END IF;
  IF x.classification NOT IN ('positive','question','objection') THEN RAISE EXCEPTION 'commercially engaged reply required'; END IF;
  SELECT * INTO i FROM public.outbound_intents WHERE id=x.intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'outbound intent not found'; END IF;
  SELECT * INTO c FROM public.closer_cases WHERE reply_id=x.id;
  IF FOUND THEN RETURN jsonb_build_object('decision','existing','case_id',c.id,'state',c.state,'actual_revenue',false); END IF;
  INSERT INTO public.closer_cases(outbound_intent_id,reply_id,prospect_id,entity_id,buyer_id,opportunity_id,opened_from_classification)
  VALUES(i.id,x.id,i.prospect_id,i.entity_id,i.buyer_id,i.opportunity_id,x.classification) RETURNING * INTO c;
  INSERT INTO public.closer_events(case_id,event_type,actor,payload) VALUES(c.id,'case_opened','closer-planner',jsonb_build_object('reply_id',x.id,'classification',x.classification));
  RETURN jsonb_build_object('decision','opened','case_id',c.id,'state',c.state,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.record_closer_recommendation(
  p_case_id uuid,
  p_type text,
  p_confidence numeric,
  p_rationale jsonb,
  p_message text,
  p_model_key text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
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

CREATE OR REPLACE FUNCTION public.advance_closer_case(p_case_id uuid,p_next_state text,p_actor text,p_fulfilment_order_id uuid,p_note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE c public.closer_cases%ROWTYPE; o public.fulfilment_orders%ROWTYPE; v text:=lower(trim(p_next_state));
BEGIN
  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF v='won' THEN RAISE EXCEPTION 'won state requires verified payment/outcome gate'; END IF;
  IF NOT ((c.state='engaged' AND v IN ('qualified','lost','paused')) OR
          (c.state='qualified' AND v IN ('proposal_ready','lost','paused')) OR
          (c.state='proposal_ready' AND v IN ('proposal_approved','lost','paused')) OR
          (c.state='proposal_approved' AND v IN ('awaiting_payment','lost','paused')) OR
          (c.state='awaiting_payment' AND v IN ('lost','paused'))) THEN
    RAISE EXCEPTION 'invalid closer state transition';
  END IF;
  IF v IN ('proposal_ready','proposal_approved','awaiting_payment') THEN
    IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'canonical fulfilment order required'; END IF;
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=p_fulfilment_order_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    IF c.entity_id IS NOT NULL AND o.entity_id IS DISTINCT FROM c.entity_id THEN RAISE EXCEPTION 'fulfilment order entity mismatch'; END IF;
    IF COALESCE(o.price_cents,0)<=0 OR lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256','')) !~ '^[0-9a-f]{64}$' THEN
      RAISE EXCEPTION 'canonical priced commercial terms required';
    END IF;
    IF v='awaiting_payment' AND o.state NOT IN ('accepted','invoiced') THEN RAISE EXCEPTION 'accepted or invoiced order required before payment'; END IF;
  END IF;
  UPDATE public.closer_cases SET state=v,fulfilment_order_id=COALESCE(p_fulfilment_order_id,fulfilment_order_id),updated_at=clock_timestamp() WHERE id=c.id RETURNING * INTO c;
  INSERT INTO public.closer_events(case_id,event_type,actor,payload) VALUES(c.id,'state_advanced',trim(p_actor),jsonb_build_object('state',v,'fulfilment_order_id',c.fulfilment_order_id,'note',trim(COALESCE(p_note,''))));
  RETURN jsonb_build_object('decision','advanced','case_id',c.id,'state',c.state,'fulfilment_order_id',c.fulfilment_order_id,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.list_closer_work(p_limit integer DEFAULT 50)
RETURNS jsonb
LANGUAGE sql
SECURITY INVOKER
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

CREATE OR REPLACE FUNCTION public.provision_buyer_from_closer_case(
    p_case_id uuid,
    p_actor text DEFAULT 'empire_closer_planner'
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
    c public.closer_cases%ROWTYPE;
    i public.outbound_intents%ROWTYPE;
    p public.prospects%ROWTYPE;
    r public.buyer_candidate_reviews%ROWTYPE;
    b public.buyers%ROWTYPE;
    review_id uuid;
    v_buyer_name text;
    v_buyer_niche text;
    v_buyer_metro text;
    v_buyer_email text;
    v_buyer_contact text;
    actor text := trim(COALESCE(p_actor,''));
BEGIN
    IF p_case_id IS NULL THEN
        RAISE EXCEPTION 'closer case id required';
    END IF;
    IF actor='' THEN
        RAISE EXCEPTION 'actor required';
    END IF;

    SELECT * INTO c
      FROM public.closer_cases
     WHERE id=p_case_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'closer case not found';
    END IF;

    IF c.state NOT IN ('engaged','qualified') THEN
        RAISE EXCEPTION 'engaged or qualified closer case required';
    END IF;

    IF c.buyer_id IS NOT NULL THEN
        SELECT * INTO b FROM public.buyers WHERE id=c.buyer_id;
        IF FOUND THEN
            RETURN jsonb_build_object(
                'decision','existing',
                'case_id',c.id,
                'buyer_id',b.id,
                'commercial_activation_state',b.commercial_activation_state,
                'actual_revenue',false
            );
        END IF;
    END IF;

    SELECT * INTO i
      FROM public.outbound_intents
     WHERE id=c.outbound_intent_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF c.prospect_id IS NULL OR i.prospect_id IS DISTINCT FROM c.prospect_id THEN
        RAISE EXCEPTION 'canonical prospect binding required';
    END IF;

    SELECT * INTO p
      FROM public.prospects
     WHERE id=c.prospect_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'prospect not found';
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
       OR COALESCE(lower(r.evidence->>'outreach_ready'),'false')<>'true' THEN
        RAISE EXCEPTION 'approved outreach-ready buyer review required';
    END IF;

    IF r.prospect_id IS DISTINCT FROM p.id THEN
        RAISE EXCEPTION 'buyer review prospect mismatch';
    END IF;

    v_buyer_name := trim(COALESCE(r.evidence->>'business_name',p.business_name,''));
    v_buyer_niche := trim(COALESCE(r.evidence->>'niche',p.niche,''));
    v_buyer_metro := trim(COALESCE(r.evidence->>'metro',p.metro,''));
    v_buyer_email := lower(trim(COALESCE(r.contact_email,i.recipient,'')));
    v_buyer_contact := trim(COALESCE(r.contact_name,p.contact_name,''));

    IF v_buyer_name='' OR v_buyer_niche='' OR v_buyer_email='' THEN
        RAISE EXCEPTION 'buyer identity evidence incomplete';
    END IF;

    SELECT * INTO b
      FROM public.buyers
     WHERE lower(trim(COALESCE(email,'')))=v_buyer_email
     ORDER BY created_at ASC
     LIMIT 1
     FOR UPDATE;

    IF NOT FOUND THEN
        SELECT * INTO b
          FROM public.buyers
         WHERE buyer_name=v_buyer_name
           AND niche=v_buyer_niche
         ORDER BY created_at ASC
         LIMIT 1
         FOR UPDATE;
    END IF;

    IF NOT FOUND THEN
        BEGIN
            INSERT INTO public.buyers(
                buyer_name,
                niche,
                metro,
                email,
                contact_name,
                daily_cap,
                calls_today,
                is_active,
                status,
                commercial_activation_state,
                notes
            ) VALUES (
                v_buyer_name,
                v_buyer_niche,
                NULLIF(v_buyer_metro,''),
                v_buyer_email,
                NULLIF(v_buyer_contact,''),
                0,
                0,
                false,
                'pending_commercial_evidence',
                'prospective',
                'Provisioned from genuine closer case ' || c.id::text
            )
            RETURNING * INTO b;
        EXCEPTION WHEN unique_violation THEN
            SELECT * INTO b
              FROM public.buyers
             WHERE buyer_name=v_buyer_name
               AND niche=v_buyer_niche
             ORDER BY created_at ASC
             LIMIT 1
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE;
            END IF;
        END;
    END IF;

    UPDATE public.closer_cases
       SET buyer_id=b.id,
           updated_at=clock_timestamp()
     WHERE id=c.id
     RETURNING * INTO c;

    INSERT INTO public.closer_events(case_id,event_type,actor,payload)
    VALUES(
        c.id,
        'buyer_provisioned',
        actor,
        jsonb_build_object(
            'buyer_id',b.id,
            'buyer_name',b.buyer_name,
            'email',b.email,
            'commercial_activation_state',b.commercial_activation_state,
            'actual_revenue',false
        )
    );

    RETURN jsonb_build_object(
        'decision','provisioned',
        'case_id',c.id,
        'buyer_id',b.id,
        'commercial_activation_state',b.commercial_activation_state,
        'is_active',COALESCE(b.is_active,false),
        'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_closer_reply_context(
    p_case_id uuid,
    p_reply_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
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
SECURITY INVOKER
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

CREATE OR REPLACE FUNCTION public.record_buyer_capacity_intake(
  p_case_id uuid,
  p_reply_id uuid,
  p_territory text,
  p_daily_cap integer,
  p_delivery_route text,
  p_delivery_reference text,
  p_evidence jsonb,
  p_actor text DEFAULT 'empire_closer_planner'
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
  x public.buyer_capacity_intakes%ROWTYPE;
  v_territory text := NULLIF(trim(COALESCE(p_territory,'')),'');
  v_route text := NULLIF(lower(trim(COALESCE(p_delivery_route,''))),'');
  v_ref text := NULLIF(trim(COALESCE(p_delivery_reference,'')),'');
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_actor='' THEN RAISE EXCEPTION 'actor required'; END IF;

  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost','paused') THEN RAISE EXCEPTION 'active closer case required'; END IF;
  IF c.buyer_id IS NULL THEN RAISE EXCEPTION 'buyer-bound closer case required'; END IF;

  SELECT * INTO r FROM public.outbound_replies WHERE id=p_reply_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply not found'; END IF;

  SELECT * INTO i FROM public.outbound_intents WHERE id=r.intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply intent not found'; END IF;

  IF r.id IS DISTINCT FROM c.reply_id
     AND COALESCE(i.metadata->>'closer_case_id','') IS DISTINCT FROM c.id::text THEN
    RAISE EXCEPTION 'reply does not belong to closer case';
  END IF;

  IF r.classification NOT IN ('positive','question','objection') THEN
    RAISE EXCEPTION 'commercially engaged inbound reply required';
  END IF;

  IF p_daily_cap IS NOT NULL AND (p_daily_cap < 1 OR p_daily_cap > 10000) THEN
    RAISE EXCEPTION 'daily capacity must be between 1 and 10000';
  END IF;

  IF v_route IS NOT NULL AND v_route NOT IN ('email','webhook','phone','api') THEN
    RAISE EXCEPTION 'unsupported delivery route';
  END IF;

  IF v_territory IS NULL AND p_daily_cap IS NULL AND v_route IS NULL AND v_ref IS NULL THEN
    RAISE EXCEPTION 'at least one explicit capacity field required';
  END IF;

  INSERT INTO public.buyer_capacity_intakes(
    closer_case_id,buyer_id,source_reply_ids,
    territory,daily_cap,delivery_route,delivery_reference,
    evidence,state
  ) VALUES (
    c.id,c.buyer_id,ARRAY[r.id]::uuid[],
    v_territory,p_daily_cap,v_route,v_ref,
    COALESCE(p_evidence,'{}'::jsonb),
    CASE
      WHEN v_territory IS NOT NULL AND p_daily_cap IS NOT NULL AND v_route IS NOT NULL
      THEN 'complete'
      ELSE 'partial'
    END
  )
  ON CONFLICT (closer_case_id)
  DO UPDATE SET
    buyer_id=EXCLUDED.buyer_id,
    source_reply_ids=CASE
      WHEN r.id=ANY(public.buyer_capacity_intakes.source_reply_ids)
      THEN public.buyer_capacity_intakes.source_reply_ids
      ELSE array_append(public.buyer_capacity_intakes.source_reply_ids,r.id)
    END,
    territory=COALESCE(EXCLUDED.territory,public.buyer_capacity_intakes.territory),
    daily_cap=COALESCE(EXCLUDED.daily_cap,public.buyer_capacity_intakes.daily_cap),
    delivery_route=COALESCE(EXCLUDED.delivery_route,public.buyer_capacity_intakes.delivery_route),
    delivery_reference=COALESCE(EXCLUDED.delivery_reference,public.buyer_capacity_intakes.delivery_reference),
    evidence=public.buyer_capacity_intakes.evidence
      || COALESCE(EXCLUDED.evidence,'{}'::jsonb)
      || jsonb_build_object('latest_reply_id',r.id,'latest_actor',v_actor),
    state=CASE
      WHEN COALESCE(EXCLUDED.territory,public.buyer_capacity_intakes.territory) IS NOT NULL
       AND COALESCE(EXCLUDED.daily_cap,public.buyer_capacity_intakes.daily_cap) IS NOT NULL
       AND COALESCE(EXCLUDED.delivery_route,public.buyer_capacity_intakes.delivery_route) IS NOT NULL
      THEN 'complete'
      ELSE 'partial'
    END,
    updated_at=clock_timestamp()
  RETURNING * INTO x;

  INSERT INTO public.closer_events(case_id,event_type,actor,payload)
  VALUES(
    c.id,
    'buyer_capacity_intake_updated',
    v_actor,
    jsonb_build_object(
      'capacity_intake_id',x.id,
      'reply_id',r.id,
      'state',x.state,
      'territory_present',x.territory IS NOT NULL,
      'daily_cap_present',x.daily_cap IS NOT NULL,
      'delivery_route_present',x.delivery_route IS NOT NULL,
      'buyer_stated_only',true,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','recorded',
    'capacity_intake_id',x.id,
    'case_id',c.id,
    'buyer_id',c.buyer_id,
    'state',x.state,
    'territory',x.territory,
    'daily_cap',x.daily_cap,
    'delivery_route',x.delivery_route,
    'delivery_reference',x.delivery_reference,
    'buyer_stated_only',true,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.prepare_fulfilment_order_from_capacity(
  p_case_id uuid,
  p_actor text DEFAULT 'empire_closer_planner'
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  x public.buyer_capacity_intakes%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_actor='' THEN RAISE EXCEPTION 'actor required'; END IF;

  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost','paused') THEN RAISE EXCEPTION 'active closer case required'; END IF;
  IF c.buyer_id IS NULL OR c.prospect_id IS NULL THEN
    RAISE EXCEPTION 'buyer and prospect binding required';
  END IF;

  IF c.fulfilment_order_id IS NOT NULL THEN
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=c.fulfilment_order_id;
    IF FOUND THEN
      RETURN jsonb_build_object(
        'decision','existing',
        'fulfilment_order_id',o.id,
        'state',o.state,
        'actual_revenue',false
      );
    END IF;
  END IF;

  SELECT * INTO x
    FROM public.buyer_capacity_intakes
   WHERE closer_case_id=c.id
   FOR UPDATE;
  IF NOT FOUND OR x.state<>'complete' THEN
    RAISE EXCEPTION 'complete buyer-stated capacity intake required';
  END IF;

  INSERT INTO public.fulfilment_orders(
    opportunity_id,
    prospect_id,
    entity_id,
    buyer_id,
    state,
    quantity,
    price_cents,
    acquisition_cost_cents,
    fulfilment_cost_cents,
    expected_margin_cents,
    delivery_payload,
    commercial_payload
  ) VALUES (
    c.opportunity_id,
    c.prospect_id,
    c.entity_id,
    c.buyer_id,
    'qualified',
    1,
    0,
    0,
    0,
    0,
    jsonb_build_object(
      'territory',x.territory,
      'daily_cap',x.daily_cap,
      'delivery_route',x.delivery_route,
      'delivery_reference',x.delivery_reference,
      'capacity_source','buyer_stated'
    ),
    jsonb_build_object(
      'buyer_capacity_intake_id',x.id,
      'capacity_evidence_state','buyer_stated_unverified',
      'binding_commercial_terms',false,
      'actual_revenue',false
    )
  )
  RETURNING * INTO o;

  UPDATE public.closer_cases
     SET fulfilment_order_id=o.id,
         updated_at=clock_timestamp()
   WHERE id=c.id;

  INSERT INTO public.closer_events(case_id,event_type,actor,payload)
  VALUES(
    c.id,
    'fulfilment_order_prepared',
    v_actor,
    jsonb_build_object(
      'fulfilment_order_id',o.id,
      'order_state',o.state,
      'buyer_capacity_intake_id',x.id,
      'binding_commercial_terms',false,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','prepared',
    'fulfilment_order_id',o.id,
    'state',o.state,
    'buyer_capacity_intake_id',x.id,
    'binding_commercial_terms',false,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.propose_commercial_evidence(
  p_evidence_kind text,
  p_buyer_id uuid,
  p_closer_case_id uuid,
  p_fulfilment_order_id uuid,
  p_niche text,
  p_metro text,
  p_amount_cents bigint,
  p_unit text,
  p_source_type text,
  p_source_reference text,
  p_evidence jsonb,
  p_observed_at timestamptz,
  p_valid_until timestamptz DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  v_kind text := lower(trim(COALESCE(p_evidence_kind,'')));
  v_unit text := lower(trim(COALESCE(p_unit,'')));
  v_source text := lower(trim(COALESCE(p_source_type,'')));
  v_ref text := trim(COALESCE(p_source_reference,''));
  v_niche text := NULLIF(trim(COALESCE(p_niche,'')),'');
  v_metro text := NULLIF(trim(COALESCE(p_metro,'')),'');
BEGIN
  IF v_kind NOT IN ('price','acquisition_cost','fulfilment_cost') THEN
    RAISE EXCEPTION 'unsupported commercial evidence kind';
  END IF;
  IF v_unit NOT IN ('per_order','per_lead','per_call','per_month','flat') THEN
    RAISE EXCEPTION 'unsupported evidence unit';
  END IF;
  IF v_source NOT IN (
    'buyer_stated','founder_approved','observed_contract',
    'public_price','provider_invoice','internal_actual'
  ) THEN
    RAISE EXCEPTION 'unsupported commercial evidence source';
  END IF;
  IF v_ref='' OR p_observed_at IS NULL THEN
    RAISE EXCEPTION 'source reference and observed_at required';
  END IF;
  IF p_amount_cents IS NULL OR p_amount_cents < 0 THEN
    RAISE EXCEPTION 'nonnegative amount required';
  END IF;
  IF v_kind='price' AND p_amount_cents <= 0 THEN
    RAISE EXCEPTION 'positive price required';
  END IF;
  IF p_valid_until IS NOT NULL AND p_valid_until <= p_observed_at THEN
    RAISE EXCEPTION 'valid_until must be after observed_at';
  END IF;

  IF p_buyer_id IS NOT NULL THEN
    PERFORM 1 FROM public.buyers WHERE id=p_buyer_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer not found'; END IF;
  END IF;

  IF p_closer_case_id IS NOT NULL THEN
    PERFORM 1 FROM public.closer_cases WHERE id=p_closer_case_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  END IF;

  IF p_fulfilment_order_id IS NOT NULL THEN
    PERFORM 1 FROM public.fulfilment_orders WHERE id=p_fulfilment_order_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  END IF;

  INSERT INTO public.commercial_evidence_registry(
    evidence_kind,buyer_id,closer_case_id,fulfilment_order_id,
    niche,metro,amount_cents,currency,unit,
    source_type,source_reference,evidence,observed_at,valid_until
  ) VALUES (
    v_kind,p_buyer_id,p_closer_case_id,p_fulfilment_order_id,
    v_niche,v_metro,p_amount_cents,'USD',v_unit,
    v_source,v_ref,COALESCE(p_evidence,'{}'::jsonb),
    p_observed_at,p_valid_until
  )
  ON CONFLICT (evidence_kind,source_type,source_reference)
  DO UPDATE SET
    buyer_id=EXCLUDED.buyer_id,
    closer_case_id=EXCLUDED.closer_case_id,
    fulfilment_order_id=EXCLUDED.fulfilment_order_id,
    niche=EXCLUDED.niche,
    metro=EXCLUDED.metro,
    amount_cents=EXCLUDED.amount_cents,
    unit=EXCLUDED.unit,
    evidence=EXCLUDED.evidence,
    observed_at=EXCLUDED.observed_at,
    valid_until=EXCLUDED.valid_until,
    updated_at=clock_timestamp()
  WHERE public.commercial_evidence_registry.status='pending'
  RETURNING * INTO x;

  IF x.id IS NULL THEN
    SELECT * INTO x
      FROM public.commercial_evidence_registry
     WHERE evidence_kind=v_kind
       AND source_type=v_source
       AND source_reference=v_ref;
  END IF;

  RETURN jsonb_build_object(
    'decision',
      CASE WHEN x.status='pending' THEN 'proposed' ELSE 'existing' END,
    'evidence_id',x.id,
    'evidence_kind',x.evidence_kind,
    'status',x.status,
    'amount_cents',x.amount_cents,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.verify_commercial_evidence(
  p_evidence_id uuid,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF p_evidence_id IS NULL OR v_actor='' THEN
    RAISE EXCEPTION 'evidence id and actor required';
  END IF;

  SELECT * INTO x
    FROM public.commercial_evidence_registry
   WHERE id=p_evidence_id
   FOR UPDATE;

  IF NOT FOUND THEN RAISE EXCEPTION 'commercial evidence not found'; END IF;

  IF x.status='verified' THEN
    RETURN jsonb_build_object(
      'decision','existing_verification',
      'evidence_id',x.id,
      'status',x.status,
      'actual_revenue',false
    );
  END IF;

  IF x.status<>'pending' THEN
    RAISE EXCEPTION 'pending commercial evidence required';
  END IF;

  IF x.valid_until IS NOT NULL AND x.valid_until <= clock_timestamp() THEN
    RAISE EXCEPTION 'commercial evidence expired';
  END IF;

  IF x.source_type='buyer_stated' THEN
    IF x.closer_case_id IS NULL OR x.buyer_id IS NULL THEN
      RAISE EXCEPTION 'buyer-stated evidence requires buyer and closer case';
    END IF;
    IF COALESCE(x.evidence->>'reply_id','')='' THEN
      RAISE EXCEPTION 'buyer-stated evidence requires reply_id';
    END IF;
  ELSIF x.source_type='public_price' THEN
    IF COALESCE(x.evidence->>'source_url','')='' THEN
      RAISE EXCEPTION 'public price evidence requires source_url';
    END IF;
  ELSIF x.source_type='observed_contract' THEN
    IF COALESCE(x.evidence->>'contract_reference','')='' THEN
      RAISE EXCEPTION 'observed contract evidence requires contract_reference';
    END IF;
  ELSIF x.source_type='provider_invoice' THEN
    IF COALESCE(x.evidence->>'invoice_reference','')='' THEN
      RAISE EXCEPTION 'provider invoice evidence requires invoice_reference';
    END IF;
  ELSIF x.source_type='internal_actual' THEN
    IF COALESCE(x.evidence->>'cost_reference','')='' THEN
      RAISE EXCEPTION 'internal actual cost requires cost_reference';
    END IF;
  ELSIF x.source_type='founder_approved' THEN
    IF COALESCE(x.evidence->>'approval_reference','')='' THEN
      RAISE EXCEPTION 'founder-approved evidence requires approval_reference';
    END IF;
  END IF;

  UPDATE public.commercial_evidence_registry
     SET status='verified',
         verified_at=clock_timestamp(),
         verified_by=v_actor,
         updated_at=clock_timestamp()
   WHERE id=x.id
   RETURNING * INTO x;

  RETURN jsonb_build_object(
    'decision','verified',
    'evidence_id',x.id,
    'evidence_kind',x.evidence_kind,
    'status',x.status,
    'amount_cents',x.amount_cents,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_commercial_evidence(
  p_evidence_id uuid,
  p_actor text,
  p_reason text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
  v_reason text := trim(COALESCE(p_reason,''));
BEGIN
  IF p_evidence_id IS NULL OR v_actor='' OR v_reason='' THEN
    RAISE EXCEPTION 'evidence id, actor and reason required';
  END IF;

  SELECT * INTO x
    FROM public.commercial_evidence_registry
   WHERE id=p_evidence_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'commercial evidence not found'; END IF;

  IF x.status<>'pending' THEN
    RETURN jsonb_build_object(
      'decision','existing',
      'evidence_id',x.id,
      'status',x.status,
      'actual_revenue',false
    );
  END IF;

  UPDATE public.commercial_evidence_registry
     SET status='rejected',
         rejected_at=clock_timestamp(),
         rejected_by=v_actor,
         rejection_reason=v_reason,
         updated_at=clock_timestamp()
   WHERE id=x.id
   RETURNING * INTO x;

  RETURN jsonb_build_object(
    'decision','rejected',
    'evidence_id',x.id,
    'status',x.status,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_verified_terms_evidence(
  p_fulfilment_order_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  p public.prospects%ROWTYPE;
  price public.commercial_evidence_registry%ROWTYPE;
  acq public.commercial_evidence_registry%ROWTYPE;
  fulfil public.commercial_evidence_registry%ROWTYPE;
BEGIN
  SELECT * INTO o
    FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;

  SELECT * INTO p FROM public.prospects WHERE id=o.prospect_id;

  SELECT * INTO price
    FROM public.commercial_evidence_registry e
   WHERE e.evidence_kind='price'
     AND e.status='verified'
     AND (e.valid_until IS NULL OR e.valid_until>clock_timestamp())
     AND (e.fulfilment_order_id IS NULL OR e.fulfilment_order_id=o.id)
     AND (e.buyer_id IS NULL OR e.buyer_id=o.buyer_id)
     AND (e.niche IS NULL OR e.niche=p.niche)
     AND (e.metro IS NULL OR e.metro=p.metro)
   ORDER BY
     (e.fulfilment_order_id=o.id) DESC,
     (e.buyer_id=o.buyer_id) DESC,
     e.observed_at DESC,
     e.id DESC
   LIMIT 1;

  SELECT * INTO acq
    FROM public.commercial_evidence_registry e
   WHERE e.evidence_kind='acquisition_cost'
     AND e.status='verified'
     AND (e.valid_until IS NULL OR e.valid_until>clock_timestamp())
     AND (e.fulfilment_order_id IS NULL OR e.fulfilment_order_id=o.id)
     AND (e.niche IS NULL OR e.niche=p.niche)
     AND (e.metro IS NULL OR e.metro=p.metro)
   ORDER BY
     (e.fulfilment_order_id=o.id) DESC,
     e.observed_at DESC,
     e.id DESC
   LIMIT 1;

  SELECT * INTO fulfil
    FROM public.commercial_evidence_registry e
   WHERE e.evidence_kind='fulfilment_cost'
     AND e.status='verified'
     AND (e.valid_until IS NULL OR e.valid_until>clock_timestamp())
     AND (e.fulfilment_order_id IS NULL OR e.fulfilment_order_id=o.id)
     AND (e.niche IS NULL OR e.niche=p.niche)
     AND (e.metro IS NULL OR e.metro=p.metro)
   ORDER BY
     (e.fulfilment_order_id=o.id) DESC,
     e.observed_at DESC,
     e.id DESC
   LIMIT 1;

  RETURN jsonb_build_object(
    'fulfilment_order_id',o.id,
    'buyer_id',o.buyer_id,
    'prospect_id',o.prospect_id,
    'niche',p.niche,
    'metro',p.metro,
    'price',CASE WHEN price.id IS NULL THEN NULL ELSE jsonb_build_object(
      'evidence_id',price.id,
      'amount_cents',price.amount_cents,
      'unit',price.unit,
      'source_type',price.source_type,
      'source_reference',price.source_reference,
      'observed_at',price.observed_at
    ) END,
    'acquisition_cost',CASE WHEN acq.id IS NULL THEN NULL ELSE jsonb_build_object(
      'evidence_id',acq.id,
      'amount_cents',acq.amount_cents,
      'unit',acq.unit,
      'source_type',acq.source_type,
      'source_reference',acq.source_reference,
      'observed_at',acq.observed_at
    ) END,
    'fulfilment_cost',CASE WHEN fulfil.id IS NULL THEN NULL ELSE jsonb_build_object(
      'evidence_id',fulfil.id,
      'amount_cents',fulfil.amount_cents,
      'unit',fulfil.unit,
      'source_type',fulfil.source_type,
      'source_reference',fulfil.source_reference,
      'observed_at',fulfil.observed_at
    ) END,
    'pricing_authority','none',
    'settlement_authority','none',
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_commercial_product_catalog(
  p_product_code text DEFAULT NULL,
  p_limit integer DEFAULT 100
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path=''
AS $$
  WITH ranked AS (
    SELECT
      v.*,
      row_number() OVER (
        PARTITION BY v.product_id
        ORDER BY
          CASE
            WHEN v.version_state='VERIFIED'
             AND (v.effective_from IS NULL OR v.effective_from <= now())
             AND (v.effective_until IS NULL OR v.effective_until > now())
            THEN 0
            ELSE 1
          END,
          v.version DESC
      ) AS readiness_rank
    FROM public.commercial_product_versions v
  ),
  latest AS (
    SELECT *
    FROM ranked
    WHERE readiness_rank=1
  )
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'product_id',p.id,
        'product_code',p.product_code,
        'product_name',p.product_name,
        'product_family',p.product_family,
        'active',p.active,
        'catalog_state',p.catalog_state,
        'currency',p.currency,
        'product_provenance',p.provenance,
        'version_id',v.id,
        'version',v.version,
        'version_state',COALESCE(v.version_state,'UNKNOWN'),
        'billing_model',COALESCE(v.billing_model,p.billing_model),
        'price_basis',COALESCE(v.price_basis,'{"state":"UNKNOWN"}'::jsonb),
        'acquisition_cost_basis',COALESCE(v.acquisition_cost_basis,'{"state":"UNKNOWN"}'::jsonb),
        'fulfilment_cost_basis',COALESCE(v.fulfilment_cost_basis,'{"state":"UNKNOWN"}'::jsonb),
        'margin_policy',COALESCE(v.margin_policy,'{"state":"UNKNOWN"}'::jsonb),
        'provenance',COALESCE(v.provenance,'{}'::jsonb),
        'evidence_refs',COALESCE(v.evidence_refs,'[]'::jsonb),
        'effective_from',v.effective_from,
        'effective_until',v.effective_until,
        'verified_at',v.verified_at,
        'verified_by',v.verified_by,
        'binding_terms_ready',(
          p.active IS TRUE
          AND p.catalog_state='VERIFIED'
          AND v.version_state='VERIFIED'
          AND COALESCE(v.price_basis->>'state','UNKNOWN')='VERIFIED'
          AND COALESCE(v.acquisition_cost_basis->>'state','UNKNOWN')='VERIFIED'
          AND COALESCE(v.fulfilment_cost_basis->>'state','UNKNOWN')='VERIFIED'
          AND COALESCE(v.margin_policy->>'state','UNKNOWN')='VERIFIED'
          AND (v.effective_from IS NULL OR v.effective_from <= now())
          AND (v.effective_until IS NULL OR v.effective_until > now())
        ),
        'actual_revenue',false
      )
      ORDER BY p.product_code
    ),
    '[]'::jsonb
  )
  FROM (
    SELECT *
    FROM public.commercial_products
    WHERE p_product_code IS NULL OR product_code=p_product_code
    ORDER BY product_code
    LIMIT LEAST(GREATEST(COALESCE(p_limit,100),1),500)
  ) p
  LEFT JOIN latest v ON v.product_id=p.id;
$$;

CREATE OR REPLACE FUNCTION public.get_commercial_product_readiness(
  p_product_code text
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path=''
AS $$
  WITH rows AS (
    SELECT public.get_commercial_product_catalog(p_product_code,1) AS payload
  ),
  item AS (
    SELECT payload->0 AS x FROM rows
  )
  SELECT CASE
    WHEN x IS NULL THEN jsonb_build_object(
      'product_code',p_product_code,
      'exists',false,
      'binding_terms_ready',false,
      'blockers',jsonb_build_array('product_not_found'),
      'actual_revenue',false
    )
    ELSE jsonb_build_object(
      'product_code',x->>'product_code',
      'exists',true,
      'binding_terms_ready',COALESCE((x->>'binding_terms_ready')::boolean,false),
      'blockers',to_jsonb(ARRAY_REMOVE(ARRAY[
        CASE WHEN COALESCE((x->>'active')::boolean,false) IS NOT TRUE THEN 'product_inactive' END,
        CASE WHEN COALESCE(x->>'catalog_state','UNKNOWN')<>'VERIFIED' THEN 'catalog_unverified' END,
        CASE WHEN COALESCE(x->>'version_state','UNKNOWN')<>'VERIFIED' THEN 'version_unverified' END,
        CASE WHEN COALESCE(x->'price_basis'->>'state','UNKNOWN')<>'VERIFIED' THEN 'price_basis_unverified' END,
        CASE WHEN COALESCE(x->'acquisition_cost_basis'->>'state','UNKNOWN')<>'VERIFIED' THEN 'acquisition_cost_basis_unverified' END,
        CASE WHEN COALESCE(x->'fulfilment_cost_basis'->>'state','UNKNOWN')<>'VERIFIED' THEN 'fulfilment_cost_basis_unverified' END,
        CASE WHEN COALESCE(x->'margin_policy'->>'state','UNKNOWN')<>'VERIFIED' THEN 'margin_policy_unverified' END,
        CASE
          WHEN x->>'effective_from' IS NOT NULL
           AND (x->>'effective_from')::timestamptz > now()
          THEN 'version_not_yet_effective'
        END,
        CASE
          WHEN x->>'effective_until' IS NOT NULL
           AND (x->>'effective_until')::timestamptz <= now()
          THEN 'version_expired'
        END
      ],NULL)),
      'catalog',x,
      'actual_revenue',false
    )
  END
  FROM item;
$$;

CREATE OR REPLACE FUNCTION public.guard_commercial_terms_events_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'commercial terms events are append-only'; END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.propose_commercial_terms(
  p_fulfilment_order_id uuid,
  p_price_cents bigint,
  p_acquisition_cost_cents bigint,
  p_fulfilment_cost_cents bigint,
  p_terms jsonb,
  p_idempotency_key text,
  p_actor text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  r public.commercial_terms_reviews%ROWTYPE;
  v_margin bigint;
  v_hash text;
  v_key text := trim(COALESCE(p_idempotency_key,''));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF p_price_cents IS NULL OR p_price_cents <= 0 THEN RAISE EXCEPTION 'positive price required'; END IF;
  IF COALESCE(p_acquisition_cost_cents,0) < 0 OR COALESCE(p_fulfilment_cost_cents,0) < 0 THEN
    RAISE EXCEPTION 'costs cannot be negative';
  END IF;
  v_margin := p_price_cents-COALESCE(p_acquisition_cost_cents,0)-COALESCE(p_fulfilment_cost_cents,0);
  IF v_margin <= 0 THEN RAISE EXCEPTION 'positive expected margin required'; END IF;
  IF jsonb_typeof(p_terms) <> 'object' OR p_terms='{}'::jsonb THEN RAISE EXCEPTION 'commercial terms object required'; END IF;
  IF lower(trim(COALESCE(p_terms->>'currency',''))) <> 'usd'
     OR upper(trim(COALESCE(p_terms->>'settlement_asset',''))) <> 'USDT'
     OR upper(trim(COALESCE(p_terms->>'settlement_chain',''))) <> 'BSC' THEN
    RAISE EXCEPTION 'canonical USD price with USDT/BSC settlement terms required';
  END IF;
  IF v_actor='' OR length(v_key)<8 THEN RAISE EXCEPTION 'actor and idempotency key required'; END IF;
  v_hash := encode(sha256(convert_to(p_terms::text,'UTF8')),'hex');

  SELECT * INTO o FROM public.fulfilment_orders WHERE id=p_fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.buyer_id IS NULL OR o.prospect_id IS NULL THEN RAISE EXCEPTION 'allocated buyer and prospect required'; END IF;
  IF o.state NOT IN ('matched','qualified') THEN RAISE EXCEPTION 'matched or qualified order required'; END IF;

  SELECT * INTO r FROM public.commercial_terms_reviews WHERE idempotency_key=v_key;
  IF FOUND THEN
    IF r.fulfilment_order_id IS DISTINCT FROM o.id OR r.price_cents IS DISTINCT FROM p_price_cents
       OR r.commercial_terms_sha256 IS DISTINCT FROM v_hash THEN
      RAISE EXCEPTION 'idempotency key belongs to different commercial terms';
    END IF;
    RETURN jsonb_build_object('decision','existing','review_id',r.id,'status',r.status,
                              'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false);
  END IF;

  INSERT INTO public.commercial_terms_reviews(
    fulfilment_order_id,price_cents,acquisition_cost_cents,fulfilment_cost_cents,
    expected_margin_cents,terms,commercial_terms_sha256,idempotency_key,proposed_by
  ) VALUES (o.id,p_price_cents,COALESCE(p_acquisition_cost_cents,0),COALESCE(p_fulfilment_cost_cents,0),
            v_margin,p_terms,v_hash,v_key,v_actor) RETURNING * INTO r;
  INSERT INTO public.commercial_terms_events(review_id,fulfilment_order_id,event_type,actor,payload)
  VALUES(r.id,o.id,'proposed',v_actor,jsonb_build_object(
    'price_cents',r.price_cents,'expected_margin_cents',r.expected_margin_cents,
    'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false));
  RETURN jsonb_build_object('decision','proposed','review_id',r.id,'status',r.status,
                            'price_cents',r.price_cents,'expected_margin_cents',r.expected_margin_cents,
                            'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.decide_commercial_terms(
  p_review_id uuid,
  p_decision text,
  p_actor text,
  p_note text DEFAULT ''
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
  r public.commercial_terms_reviews%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
  v_decision text := lower(trim(COALESCE(p_decision,'')));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_decision NOT IN ('approved','rejected') THEN RAISE EXCEPTION 'approved or rejected decision required'; END IF;
  IF v_actor='' THEN RAISE EXCEPTION 'decision actor required'; END IF;
  SELECT * INTO r FROM public.commercial_terms_reviews WHERE id=p_review_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'commercial terms review not found'; END IF;
  IF r.status<>'pending' THEN
    RETURN jsonb_build_object('decision','existing','review_id',r.id,'status',r.status,'actual_revenue',false);
  END IF;
  SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.state NOT IN ('matched','qualified') THEN RAISE EXCEPTION 'order is no longer reviewable'; END IF;

  UPDATE public.commercial_terms_reviews
     SET status=v_decision,decided_by=v_actor,decided_at=clock_timestamp(),decision_note=trim(COALESCE(p_note,''))
   WHERE id=r.id RETURNING * INTO r;

  IF v_decision='approved' THEN
    UPDATE public.fulfilment_orders
       SET state='offered',price_cents=r.price_cents,
           acquisition_cost_cents=r.acquisition_cost_cents,
           fulfilment_cost_cents=r.fulfilment_cost_cents,
           expected_margin_cents=r.expected_margin_cents,
           commercial_payload=COALESCE(commercial_payload,'{}'::jsonb) || jsonb_build_object(
             'commercial_terms_sha256',r.commercial_terms_sha256,
             'commercial_terms_review_id',r.id,
             'commercial_terms',r.terms,
             'terms_approved_by',v_actor,
             'terms_approved_at',r.decided_at
           ),updated_at=clock_timestamp()
     WHERE id=o.id;
  END IF;

  INSERT INTO public.commercial_terms_events(review_id,fulfilment_order_id,event_type,actor,payload)
  VALUES(r.id,o.id,v_decision,v_actor,jsonb_build_object('note',trim(COALESCE(p_note,'')),
         'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false));
  RETURN jsonb_build_object('decision',v_decision,'review_id',r.id,'status',r.status,
                            'fulfilment_order_id',o.id,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.record_commercial_acceptance(
  p_review_id uuid,
  p_evidence_kind text,
  p_evidence_reference text,
  p_accepted_at timestamptz,
  p_actor text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
  r public.commercial_terms_reviews%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
  v_kind text := lower(trim(COALESCE(p_evidence_kind,'')));
  v_ref text := trim(COALESCE(p_evidence_reference,''));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_kind NOT IN ('outbound_reply','signed_agreement','manual_verified') THEN
    RAISE EXCEPTION 'supported buyer acceptance evidence required';
  END IF;
  IF v_ref='' OR v_actor='' OR p_accepted_at IS NULL THEN RAISE EXCEPTION 'acceptance evidence, time and actor required'; END IF;
  IF p_accepted_at > clock_timestamp()+interval '5 minutes' THEN RAISE EXCEPTION 'acceptance time cannot be in the future'; END IF;

  SELECT * INTO r FROM public.commercial_terms_reviews WHERE id=p_review_id FOR UPDATE;
  IF NOT FOUND OR r.status<>'approved' THEN RAISE EXCEPTION 'approved commercial terms review required'; END IF;
  IF p_accepted_at < r.decided_at THEN RAISE EXCEPTION 'acceptance cannot predate approved terms'; END IF;
  SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.state='accepted' THEN
    RETURN jsonb_build_object('decision','existing_acceptance','fulfilment_order_id',o.id,'actual_revenue',false);
  END IF;
  IF o.state<>'offered' THEN RAISE EXCEPTION 'offered fulfilment order required'; END IF;
  UPDATE public.fulfilment_orders
     SET state='accepted',updated_at=clock_timestamp(),
         commercial_payload=COALESCE(commercial_payload,'{}'::jsonb) || jsonb_build_object(
           'buyer_acceptance_kind',v_kind,
           'buyer_acceptance_reference',v_ref,
           'buyer_accepted_at',p_accepted_at,
           'buyer_acceptance_recorded_by',v_actor
         )
   WHERE id=o.id;
  INSERT INTO public.commercial_terms_events(review_id,fulfilment_order_id,event_type,actor,payload)
  VALUES(r.id,o.id,'accepted',v_actor,jsonb_build_object(
    'evidence_kind',v_kind,'evidence_reference',v_ref,'accepted_at',p_accepted_at,
    'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false));
  RETURN jsonb_build_object('decision','accepted','review_id',r.id,
                            'fulfilment_order_id',o.id,'state','accepted','actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.get_commercial_terms_review(p_review_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
  SELECT jsonb_build_object(
    'review_id',r.id,'fulfilment_order_id',r.fulfilment_order_id,'status',r.status,
    'price_cents',r.price_cents,'acquisition_cost_cents',r.acquisition_cost_cents,
    'fulfilment_cost_cents',r.fulfilment_cost_cents,'expected_margin_cents',r.expected_margin_cents,
    'terms',r.terms,'commercial_terms_sha256',r.commercial_terms_sha256,
    'proposed_by',r.proposed_by,'proposed_at',r.proposed_at,
    'decided_by',r.decided_by,'decided_at',r.decided_at,'decision_note',r.decision_note,
    'actual_revenue',false)
  FROM public.commercial_terms_reviews r WHERE r.id=p_review_id;
$$;

CREATE OR REPLACE FUNCTION public.guard_bsc_payment_request()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'payment requests cannot be deleted';
    END IF;
    IF OLD.status <> 'pending' AND (
        (to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status')
        OR NEW.status NOT IN (OLD.status, 'cancelled', 'expired')
    ) THEN
        RAISE EXCEPTION 'approved payment terms are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_bsc_payment_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    o public.fulfilment_orders%ROWTYPE;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment evidence is append-only';
    END IF;
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=NEW.request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF r.status <> 'approved' OR r.approved_at IS NULL
       OR r.approved_at > clock_timestamp() OR r.expires_at <= clock_timestamp()
       OR NULLIF(trim(r.approved_by),'') IS NULL THEN
        RAISE EXCEPTION 'current human-approved request required';
    END IF;
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'order missing'; END IF;
    IF o.buyer_id IS DISTINCT FROM r.buyer_id
       OR o.state NOT IN ('accepted','invoiced','delivered','confirmed')
       OR o.state IS NULL
       OR (o.commercial_payload->>'commercial_terms_sha256')
           IS DISTINCT FROM r.commercial_terms_sha256 THEN
        RAISE EXCEPTION 'order or terms mismatch';
    END IF;
    IF NEW.fulfilment_order_id IS DISTINCT FROM r.fulfilment_order_id
       OR NEW.sender_address IS DISTINCT FROM r.payer_address
       OR NEW.treasury_address IS DISTINCT FROM r.treasury_address
       OR NEW.commercial_terms_sha256 IS DISTINCT FROM r.commercial_terms_sha256
       OR NEW.amount_raw < r.amount_usdt * 1000000000000000000
       OR NEW.block_number < r.min_block_number THEN
        RAISE EXCEPTION 'payment evidence does not match approved request';
    END IF;
    IF NEW.verified_at < clock_timestamp() - interval '5 minutes'
       OR NEW.verified_at > clock_timestamp() + interval '5 seconds' THEN
        RAISE EXCEPTION 'fresh verification required';
    END IF;
    NEW.recorded_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_bsc_payment_request_event()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment request audit events are append-only';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.propose_bsc_payment_request(
    p_fulfilment_order_id uuid,
    p_amount_usdt numeric,
    p_payer_address text,
    p_treasury_address text,
    p_min_block_number bigint,
    p_expires_at timestamptz,
    p_idempotency_key text,
    p_actor text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    o public.fulfilment_orders%ROWTYPE;
    r public.bsc_payment_requests%ROWTYPE;
    v_terms text;
    v_payer text := lower(trim(COALESCE(p_payer_address,'')));
    v_treasury text := lower(trim(COALESCE(p_treasury_address,'')));
    v_key text := trim(COALESCE(p_idempotency_key,''));
    v_actor text := trim(COALESCE(p_actor,''));
BEGIN
    IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'fulfilment_order_id is required'; END IF;
    IF p_amount_usdt IS NULL OR p_amount_usdt <= 0 THEN RAISE EXCEPTION 'positive amount_usdt is required'; END IF;
    IF v_payer !~ '^0x[0-9a-f]{40}$' OR v_treasury !~ '^0x[0-9a-f]{40}$' THEN
        RAISE EXCEPTION 'canonical BSC payer and treasury addresses are required';
    END IF;
    IF v_payer = v_treasury THEN RAISE EXCEPTION 'payer and treasury must differ'; END IF;
    IF COALESCE(p_min_block_number,0) <= 0 THEN RAISE EXCEPTION 'positive min_block_number is required'; END IF;
    IF length(v_key) < 8 OR length(v_key) > 128 THEN RAISE EXCEPTION 'idempotency_key length is invalid'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'actor is required'; END IF;
    IF p_expires_at IS NULL OR p_expires_at < clock_timestamp() + interval '10 minutes'
       OR p_expires_at > clock_timestamp() + interval '7 days' THEN
        RAISE EXCEPTION 'expires_at must be 10 minutes to 7 days in the future';
    END IF;
    SELECT * INTO o
      FROM public.fulfilment_orders
     WHERE id=p_fulfilment_order_id
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    IF o.buyer_id IS NULL THEN RAISE EXCEPTION 'fulfilment order buyer is required'; END IF;
    IF o.state IS NULL OR o.state NOT IN ('accepted','invoiced','delivered','confirmed') THEN
        RAISE EXCEPTION 'fulfilment order is not payment-eligible';
    END IF;
    v_terms := lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''));
    IF v_terms !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'fulfilment order requires commercial_terms_sha256';
    END IF;

    SELECT * INTO r
      FROM public.bsc_payment_requests
     WHERE idempotency_key=v_key
     FOR UPDATE;
    IF FOUND THEN
        IF r.fulfilment_order_id IS DISTINCT FROM p_fulfilment_order_id
           OR r.buyer_id IS DISTINCT FROM o.buyer_id
           OR r.amount_usdt IS DISTINCT FROM p_amount_usdt
           OR r.payer_address IS DISTINCT FROM v_payer
           OR r.treasury_address IS DISTINCT FROM v_treasury
           OR r.commercial_terms_sha256 IS DISTINCT FROM v_terms
           OR r.min_block_number IS DISTINCT FROM p_min_block_number
           OR r.expires_at IS DISTINCT FROM p_expires_at THEN
            RAISE EXCEPTION 'idempotency_key already belongs to different payment terms';
        END IF;
        RETURN jsonb_build_object(
            'decision','existing_request','request_id',r.id,
            'status',r.status,'actual_revenue',false
        );
    END IF;
    SELECT * INTO r
      FROM public.bsc_payment_requests
     WHERE fulfilment_order_id=p_fulfilment_order_id
       AND status IN ('pending','approved')
     FOR UPDATE;
    IF FOUND THEN
        RAISE EXCEPTION 'fulfilment order already has an open payment request';
    END IF;

    INSERT INTO public.bsc_payment_requests (
        buyer_id, fulfilment_order_id, amount_usdt, payer_address, treasury_address,
        commercial_terms_sha256, min_block_number, status, expires_at, idempotency_key
    ) VALUES (
        o.buyer_id, p_fulfilment_order_id, p_amount_usdt, v_payer, v_treasury,
        v_terms, p_min_block_number, 'pending', p_expires_at, v_key
    ) RETURNING * INTO r;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'proposed',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object(
            'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
            'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
            'treasury_address',r.treasury_address,'commercial_terms_sha256',v_terms,
            'min_block_number',r.min_block_number,'expires_at',r.expires_at,
            'idempotency_key',v_key,'actual_revenue',false
        ));
    RETURN jsonb_build_object(
        'decision','proposed','request_id',r.id,'status',r.status,
        'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
        'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.cancel_bsc_payment_request(
    p_request_id uuid,
    p_actor text,
    p_reason text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    v_actor text := trim(COALESCE(p_actor,''));
    v_reason text := trim(COALESCE(p_reason,''));
BEGIN
    IF p_request_id IS NULL THEN RAISE EXCEPTION 'request_id is required'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'actor is required'; END IF;
    IF length(v_reason) < 4 OR length(v_reason) > 1000 THEN RAISE EXCEPTION 'cancellation reason is required'; END IF;

    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    IF r.status='cancelled' THEN
        RETURN jsonb_build_object('decision','existing_cancellation','request_id',r.id,'actual_revenue',false);
    END IF;
    IF r.status='expired' THEN
        RETURN jsonb_build_object('decision','already_expired','request_id',r.id,'actual_revenue',false);
    END IF;
    PERFORM 1 FROM public.bsc_payment_evidence WHERE request_id=r.id;
    IF FOUND THEN RAISE EXCEPTION 'payment evidence already recorded; cancellation is not permitted'; END IF;

    UPDATE public.bsc_payment_requests SET status='cancelled' WHERE id=r.id RETURNING * INTO r;
    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'cancelled',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object('reason',v_reason,'previous_status','open','actual_revenue',false));
    RETURN jsonb_build_object('decision','cancelled','request_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.get_bsc_payment_request_review(p_request_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    o public.fulfilment_orders%ROWTYPE;
    e public.bsc_payment_evidence%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    SELECT * INTO e FROM public.bsc_payment_evidence WHERE request_id=r.id;
    RETURN jsonb_build_object(
        'request_id',r.id,'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
        'status',r.status,'amount_usdt',r.amount_usdt::text,
        'payer_address',r.payer_address,'treasury_address',r.treasury_address,
        'commercial_terms_sha256',r.commercial_terms_sha256,
        'min_block_number',r.min_block_number,'expires_at',r.expires_at,
        'approved_by',r.approved_by,'approved_at',r.approved_at,
        'idempotency_key',r.idempotency_key,'created_at',r.created_at,
        'order_state',o.state,
        'order_commercial_terms_sha256',lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256','')),
        'evidence_id',e.id,'evidence_transaction_hash',e.transaction_hash,
        'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.approve_bsc_payment_request(
    p_request_id uuid,
    p_approved_by text,
    p_approval_note text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    o public.fulfilment_orders%ROWTYPE;
    v_actor text := trim(COALESCE(p_approved_by,''));
    v_note text := trim(COALESCE(p_approval_note,''));
    v_terms text;
BEGIN
    IF p_request_id IS NULL THEN RAISE EXCEPTION 'request_id is required'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'approved_by is required'; END IF;
    IF length(v_note) < 4 OR length(v_note) > 1000 THEN RAISE EXCEPTION 'approval_note is required'; END IF;

    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    IF r.status='approved' THEN
        RETURN jsonb_build_object(
            'decision','existing_approval','request_id',r.id,
            'approved_by',r.approved_by,'approved_at',r.approved_at,
            'actual_revenue',false
        );
    END IF;
    IF r.status NOT IN ('pending') THEN RAISE EXCEPTION 'pending payment request required'; END IF;
    IF r.expires_at <= clock_timestamp() THEN
        UPDATE public.bsc_payment_requests SET status='expired' WHERE id=r.id;
        INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
        VALUES (r.id,'expired',v_actor,
            COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
            jsonb_build_object('reason','expired before human approval','actual_revenue',false));
        RETURN jsonb_build_object('decision','expired','request_id',r.id,'actual_revenue',false);
    END IF;
    SELECT * INTO o
      FROM public.fulfilment_orders
     WHERE id=r.fulfilment_order_id
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    v_terms := lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''));
    IF o.buyer_id IS DISTINCT FROM r.buyer_id
       OR o.state IS NULL OR o.state NOT IN ('accepted','invoiced','delivered','confirmed')
       OR v_terms IS DISTINCT FROM r.commercial_terms_sha256 THEN
        RAISE EXCEPTION 'fulfilment order or commercial terms changed since proposal';
    END IF;

    UPDATE public.bsc_payment_requests
       SET status='approved', approved_by=v_actor, approved_at=clock_timestamp()
     WHERE id=r.id
     RETURNING * INTO r;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'approved',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object(
            'approval_note',v_note,'buyer_id',r.buyer_id,
            'fulfilment_order_id',r.fulfilment_order_id,
            'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
            'treasury_address',r.treasury_address,
            'commercial_terms_sha256',r.commercial_terms_sha256,
            'min_block_number',r.min_block_number,'expires_at',r.expires_at,
            'actual_revenue',false
        ));
    RETURN jsonb_build_object(
        'decision','approved','request_id',r.id,'status',r.status,
        'approved_by',r.approved_by,'approved_at',r.approved_at,
        'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.record_bsc_payment_evidence(
    p_request_id uuid, p_evidence jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    e public.bsc_payment_evidence%ROWTYPE;
    v_db_role text := COALESCE(NULLIF(current_setting('role',true),'none'),session_user);
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF (p_evidence->>'verified') IS DISTINCT FROM 'true'
       OR (p_evidence->>'token_decimals') IS DISTINCT FROM '18' THEN
        RAISE EXCEPTION 'verified BSC USDT proof required';
    END IF;
    SELECT * INTO e FROM public.bsc_payment_evidence WHERE request_id=p_request_id;
    IF FOUND THEN
        IF e.transaction_hash IS DISTINCT FROM p_evidence->>'transaction_hash'
           OR e.block_hash IS DISTINCT FROM p_evidence->>'block_hash'
           OR e.amount_raw IS DISTINCT FROM (p_evidence->>'amount_raw')::numeric
           OR e.log_index IS DISTINCT FROM (p_evidence->>'log_index')::bigint
           OR e.chain_id IS DISTINCT FROM (p_evidence->>'chain_id')::integer
           OR e.token_contract IS DISTINCT FROM p_evidence->>'token_contract'
           OR e.block_number IS DISTINCT FROM (p_evidence->>'block_number')::bigint
           OR e.sender_address IS DISTINCT FROM p_evidence->>'sender_address'
           OR e.treasury_address IS DISTINCT FROM p_evidence->>'treasury_address'
           OR e.commercial_terms_sha256 IS DISTINCT FROM p_evidence->>'commercial_terms_sha256' THEN
            RAISE EXCEPTION 'request already recorded with different evidence';
        END IF;
        RETURN jsonb_build_object('decision','already_recorded','evidence_id',e.id,
                                  'request_id',e.request_id,'actual_revenue',false);
    END IF;
    INSERT INTO public.bsc_payment_evidence (
        request_id,fulfilment_order_id,chain_id,token_contract,transaction_hash,
        block_hash,block_number,log_index,amount_raw,confirmations,verified_at,
        sender_address,treasury_address,commercial_terms_sha256
    ) VALUES (
        p_request_id,r.fulfilment_order_id,(p_evidence->>'chain_id')::integer,
        p_evidence->>'token_contract',p_evidence->>'transaction_hash',
        p_evidence->>'block_hash',(p_evidence->>'block_number')::bigint,
        (p_evidence->>'log_index')::bigint,(p_evidence->>'amount_raw')::numeric,
        (p_evidence->>'confirmations')::integer,(p_evidence->>'verified_at')::timestamptz,
        p_evidence->>'sender_address',p_evidence->>'treasury_address',
        p_evidence->>'commercial_terms_sha256'
    ) RETURNING * INTO e;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'evidence_recorded',v_db_role,v_db_role,
        jsonb_build_object(
            'evidence_id',e.id,'transaction_hash',e.transaction_hash,
            'block_hash',e.block_hash,'block_number',e.block_number,
            'confirmations',e.confirmations,'amount_raw',e.amount_raw::text,
            'verified_at',e.verified_at,'actual_revenue',false
        ));
    RETURN jsonb_build_object('decision','recorded','evidence_id',e.id,
                              'request_id',e.request_id,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_bsc_escrow_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'escrow evidence is append-only';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.propose_bsc_escrow_request(
    p_fulfilment_order_id uuid,
    p_amount_usdt numeric,
    p_payer_address text,
    p_beneficiary_address text,
    p_min_block_number bigint,
    p_expires_at timestamptz,
    p_idempotency_key text,
    p_actor text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    o public.fulfilment_orders%ROWTYPE;
    r public.bsc_payment_requests%ROWTYPE;
    v_terms text;
    v_payer text := lower(trim(COALESCE(p_payer_address,'')));
    v_beneficiary text := lower(trim(COALESCE(p_beneficiary_address,'')));
    v_key text := trim(COALESCE(p_idempotency_key,''));
    v_actor text := trim(COALESCE(p_actor,''));
BEGIN
    IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'fulfilment_order_id is required'; END IF;
    IF p_amount_usdt IS NULL OR p_amount_usdt <= 0 THEN RAISE EXCEPTION 'positive amount_usdt is required'; END IF;
    IF v_payer !~ '^0x[0-9a-f]{40}$' OR v_beneficiary !~ '^0x[0-9a-f]{40}$' THEN
        RAISE EXCEPTION 'canonical BSC payer and beneficiary addresses are required';
    END IF;
    IF v_payer = v_beneficiary THEN RAISE EXCEPTION 'payer and beneficiary must differ'; END IF;
    IF COALESCE(p_min_block_number,0) <= 0 THEN RAISE EXCEPTION 'positive min_block_number is required'; END IF;
    IF length(v_key) < 8 OR length(v_key) > 128 THEN RAISE EXCEPTION 'idempotency_key length is invalid'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'actor is required'; END IF;
    IF p_expires_at IS NULL OR p_expires_at < clock_timestamp() + interval '10 minutes'
       OR p_expires_at > clock_timestamp() + interval '7 days' THEN
        RAISE EXCEPTION 'expires_at must be 10 minutes to 7 days in the future';
    END IF;
    SELECT * INTO o FROM public.fulfilment_orders
     WHERE id=p_fulfilment_order_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    IF o.buyer_id IS NULL OR o.state NOT IN ('accepted','invoiced','delivered','confirmed') THEN
        RAISE EXCEPTION 'fulfilment order is not payment-eligible';
    END IF;
    v_terms := lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''));
    IF v_terms !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'fulfilment order requires commercial_terms_sha256';
    END IF;

    SELECT * INTO r FROM public.bsc_payment_requests
     WHERE idempotency_key=v_key FOR UPDATE;
    IF FOUND THEN
        IF r.settlement_mode <> 'escrow'
           OR r.fulfilment_order_id IS DISTINCT FROM p_fulfilment_order_id
           OR r.buyer_id IS DISTINCT FROM o.buyer_id
           OR r.amount_usdt IS DISTINCT FROM p_amount_usdt
           OR r.payer_address IS DISTINCT FROM v_payer
           OR r.treasury_address IS DISTINCT FROM v_beneficiary
           OR r.commercial_terms_sha256 IS DISTINCT FROM v_terms
           OR r.min_block_number IS DISTINCT FROM p_min_block_number
           OR r.expires_at IS DISTINCT FROM p_expires_at THEN
            RAISE EXCEPTION 'idempotency_key already belongs to different escrow terms';
        END IF;
        RETURN jsonb_build_object('decision','existing_request','request_id',r.id,
            'status',r.status,'settlement_mode','escrow','actual_revenue',false);
    END IF;
    PERFORM 1 FROM public.bsc_payment_requests
     WHERE fulfilment_order_id=p_fulfilment_order_id
       AND status IN ('pending','approved');
    IF FOUND THEN RAISE EXCEPTION 'fulfilment order already has an open payment request'; END IF;
    INSERT INTO public.bsc_payment_requests (
        buyer_id, fulfilment_order_id, amount_usdt, payer_address, treasury_address,
        commercial_terms_sha256, min_block_number, status, expires_at,
        idempotency_key, settlement_mode
    ) VALUES (
        o.buyer_id, p_fulfilment_order_id, p_amount_usdt, v_payer, v_beneficiary,
        v_terms, p_min_block_number, 'pending', p_expires_at, v_key, 'escrow'
    ) RETURNING * INTO r;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'proposed',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object(
            'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
            'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
            'beneficiary_address',r.treasury_address,'commercial_terms_sha256',v_terms,
            'min_block_number',r.min_block_number,'expires_at',r.expires_at,
            'idempotency_key',v_key,'settlement_mode','escrow','actual_revenue',false
        ));
    RETURN jsonb_build_object('decision','proposed','request_id',r.id,
        'status',r.status,'settlement_mode','escrow','actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.record_bsc_escrow_creation(
    p_request_id uuid, p_evidence jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    a public.bsc_escrow_agreements%ROWTYPE;
    v_expected_id text;
    v_verified_at timestamptz;
    v_chain_time timestamptz;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF r.settlement_mode <> 'escrow' THEN RAISE EXCEPTION 'escrow payment request required'; END IF;
    IF r.status <> 'approved' OR r.approved_at IS NULL OR r.expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'current human-approved escrow request required';
    END IF;
    IF (p_evidence->>'verified') IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'verified escrow creation proof required';
    END IF;
    IF (p_evidence->>'confirmations')::integer < 12
       OR (p_evidence->>'block_number')::bigint < r.min_block_number THEN
        RAISE EXCEPTION 'escrow creation confirmations or block floor are insufficient';
    END IF;
    IF lower(COALESCE(p_evidence->>'transaction_hash','')) !~ '^0x[0-9a-f]{64}$'
       OR lower(COALESCE(p_evidence->>'block_hash','')) !~ '^0x[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'canonical escrow creation transaction and block hashes are required';
    END IF;
    v_expected_id := '0x' || lpad(replace(r.id::text,'-',''),64,'0');
    IF lower(COALESCE(p_evidence->>'escrow_id','')) IS DISTINCT FROM v_expected_id THEN
        RAISE EXCEPTION 'escrow id does not match payment request';
    END IF;
    IF lower(COALESCE(p_evidence->>'payer_address','')) IS DISTINCT FROM r.payer_address
       OR (p_evidence->>'amount_raw')::numeric IS DISTINCT FROM r.amount_usdt * 1000000000000000000
       OR lower(COALESCE(p_evidence->>'terms_hash','')) IS DISTINCT FROM ('0x' || r.commercial_terms_sha256) THEN
        RAISE EXCEPTION 'escrow creation proof does not match approved terms';
    END IF;
    IF lower(COALESCE(p_evidence->>'beneficiary_address','')) IS DISTINCT FROM r.treasury_address THEN
        RAISE EXCEPTION 'escrow beneficiary does not match approved request';
    END IF;
    IF lower(COALESCE(p_evidence->>'contract_address','')) !~ '^0x[0-9a-f]{40}$'
       OR lower(COALESCE(p_evidence->>'runtime_sha256','')) !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'canonical escrow contract identity is required';
    END IF;
    v_verified_at := (p_evidence->>'verified_at')::timestamptz;
    v_chain_time := to_timestamp((p_evidence->>'block_timestamp')::bigint);
    IF v_verified_at < clock_timestamp() - interval '5 minutes'
       OR v_verified_at > clock_timestamp() + interval '5 seconds' THEN
        RAISE EXCEPTION 'fresh escrow creation verification required';
    END IF;
    IF v_chain_time < r.approved_at - interval '5 minutes' OR v_chain_time >= r.expires_at THEN
        RAISE EXCEPTION 'escrow creation is outside approved request window';
    END IF;
    IF to_timestamp((p_evidence->>'funding_deadline')::bigint) <= v_chain_time
       OR to_timestamp((p_evidence->>'funding_deadline')::bigint) > r.expires_at
       OR to_timestamp((p_evidence->>'refund_after')::bigint) <= to_timestamp((p_evidence->>'funding_deadline')::bigint)
       OR to_timestamp((p_evidence->>'refund_after')::bigint) > v_chain_time + interval '365 days' THEN
        RAISE EXCEPTION 'escrow deadlines exceed approved bounds';
    END IF;
    SELECT * INTO a FROM public.bsc_escrow_agreements WHERE request_id=r.id;
    IF FOUND THEN
        RETURN jsonb_build_object('decision','already_recorded','agreement_id',a.id,
            'request_id',r.id,'status',a.status,'actual_revenue',false);
    END IF;

    INSERT INTO public.bsc_escrow_agreements(
        request_id,escrow_id,contract_address,beneficiary_address,runtime_sha256,
        creation_transaction_hash,creation_block_hash,creation_block_number,
        creation_confirmations,creation_chain_timestamp,payer_address,amount_raw,commercial_terms_sha256,
        funding_deadline,refund_after,creation_verified_at
    ) VALUES (
        r.id,v_expected_id,lower(p_evidence->>'contract_address'),r.treasury_address,
        lower(p_evidence->>'runtime_sha256'),lower(p_evidence->>'transaction_hash'),
        lower(p_evidence->>'block_hash'),(p_evidence->>'block_number')::bigint,
        (p_evidence->>'confirmations')::integer,v_chain_time,r.payer_address,(p_evidence->>'amount_raw')::numeric,r.commercial_terms_sha256,
        to_timestamp((p_evidence->>'funding_deadline')::bigint),
        to_timestamp((p_evidence->>'refund_after')::bigint),v_verified_at
    ) RETURNING * INTO a;
    RETURN jsonb_build_object('decision','recorded','agreement_id',a.id,
        'request_id',r.id,'status',a.status,'actual_revenue',false);
END;
$$;

CREATE OR REPLACE FUNCTION public.record_bsc_escrow_lifecycle(
    p_agreement_id uuid, p_action text, p_evidence jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    a public.bsc_escrow_agreements%ROWTYPE;
    e public.bsc_escrow_evidence%ROWTYPE;
    v_action text := lower(trim(COALESCE(p_action,'')));
    v_verified_at timestamptz;
    v_chain_time timestamptz;
    v_next text;
BEGIN
    IF v_action NOT IN ('funded','released','refunded') THEN
        RAISE EXCEPTION 'unsupported escrow lifecycle action';
    END IF;
    SELECT * INTO a FROM public.bsc_escrow_agreements WHERE id=p_agreement_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'escrow agreement missing'; END IF;
    IF (p_evidence->>'verified') IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'verified escrow lifecycle proof required';
    END IF;
    IF lower(COALESCE(p_evidence->>'escrow_id','')) IS DISTINCT FROM a.escrow_id
       OR (p_evidence->>'amount_raw')::numeric IS DISTINCT FROM a.amount_raw THEN
        RAISE EXCEPTION 'escrow lifecycle proof does not match agreement';
    END IF;
    IF v_action='funded' THEN
        IF a.status <> 'open' THEN RAISE EXCEPTION 'open escrow agreement required for funding'; END IF;
        IF lower(COALESCE(p_evidence->>'party_address','')) IS DISTINCT FROM a.payer_address THEN
            RAISE EXCEPTION 'escrow funding party mismatch';
        END IF;
        v_next := 'funded';
    ELSIF v_action='released' THEN
        IF a.status <> 'funded' THEN RAISE EXCEPTION 'funded escrow agreement required for release'; END IF;
        IF lower(COALESCE(p_evidence->>'party_address','')) IS DISTINCT FROM a.beneficiary_address THEN
            RAISE EXCEPTION 'escrow release beneficiary mismatch';
        END IF;
        v_next := 'released';
    ELSE
        IF a.status <> 'funded' THEN RAISE EXCEPTION 'funded escrow agreement required for refund'; END IF;
        IF lower(COALESCE(p_evidence->>'party_address','')) IS DISTINCT FROM a.payer_address THEN
            RAISE EXCEPTION 'escrow refund payer mismatch';
        END IF;
        v_next := 'refunded';
    END IF;
    v_verified_at := (p_evidence->>'verified_at')::timestamptz;
    v_chain_time := to_timestamp((p_evidence->>'block_timestamp')::bigint);
    IF v_verified_at < clock_timestamp() - interval '5 minutes'
       OR v_verified_at > clock_timestamp() + interval '5 seconds' THEN
        RAISE EXCEPTION 'fresh escrow lifecycle verification required';
    END IF;
    IF (p_evidence->>'confirmations')::integer < 12 THEN
        RAISE EXCEPTION 'at least 12 escrow confirmations are required';
    END IF;
    IF lower(COALESCE(p_evidence->>'transaction_hash','')) !~ '^0x[0-9a-f]{64}$'
       OR lower(COALESCE(p_evidence->>'block_hash','')) !~ '^0x[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'canonical escrow transaction and block hashes are required';
    END IF;

    SELECT * INTO e FROM public.bsc_escrow_evidence
     WHERE agreement_id=a.id AND action=v_action;
    IF FOUND THEN
        IF e.transaction_hash IS DISTINCT FROM lower(p_evidence->>'transaction_hash')
           OR e.block_hash IS DISTINCT FROM lower(p_evidence->>'block_hash')
           OR e.block_number IS DISTINCT FROM (p_evidence->>'block_number')::bigint
           OR e.amount_raw IS DISTINCT FROM (p_evidence->>'amount_raw')::numeric
           OR e.party_address IS DISTINCT FROM lower(p_evidence->>'party_address') THEN
            RAISE EXCEPTION 'escrow action already recorded with different evidence';
        END IF;
        RETURN jsonb_build_object('decision','already_recorded','evidence_id',e.id,
            'agreement_id',a.id,'action',v_action,'status',a.status,'actual_revenue',false);
    END IF;

    INSERT INTO public.bsc_escrow_evidence(
        agreement_id,action,transaction_hash,block_hash,block_number,
        amount_raw,party_address,confirmations,chain_timestamp,verified_at
    ) VALUES (
        a.id,v_action,lower(p_evidence->>'transaction_hash'),
        lower(p_evidence->>'block_hash'),(p_evidence->>'block_number')::bigint,
        (p_evidence->>'amount_raw')::numeric,lower(p_evidence->>'party_address'),
        (p_evidence->>'confirmations')::integer,v_chain_time,v_verified_at
    ) RETURNING * INTO e;

    UPDATE public.bsc_escrow_agreements
       SET status=v_next, updated_at=clock_timestamp()
     WHERE id=a.id
     RETURNING * INTO a;

    RETURN jsonb_build_object(
        'decision','recorded','evidence_id',e.id,'agreement_id',a.id,
        'action',v_action,'status',a.status,
        'revenue_eligible',(v_action='released'),'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_direct_bsc_payment_mode()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.bsc_payment_requests%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=NEW.request_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF r.settlement_mode <> 'direct' THEN
        RAISE EXCEPTION 'direct payment evidence cannot satisfy an escrow request';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_bsc_escrow_request_review(p_request_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    a public.bsc_escrow_agreements%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    IF r.settlement_mode <> 'escrow' THEN RAISE EXCEPTION 'escrow payment request required'; END IF;
    SELECT * INTO a FROM public.bsc_escrow_agreements WHERE request_id=r.id;
    RETURN jsonb_build_object(
        'request_id',r.id,'status',r.status,'settlement_mode',r.settlement_mode,
        'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
        'beneficiary_address',r.treasury_address,
        'commercial_terms_sha256',r.commercial_terms_sha256,
        'approved_by',r.approved_by,'approved_at',r.approved_at,'expires_at',r.expires_at,
        'agreement_id',a.id,'escrow_id',a.escrow_id,'contract_address',a.contract_address,
        'runtime_sha256',a.runtime_sha256,'escrow_status',a.status,
        'funding_deadline',a.funding_deadline,'refund_after',a.refund_after,
        'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_empire_conversation_events_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'conversation events are append-only';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.ingest_conversation_provider_event(
  p_conversation_id uuid,
  p_provider text,
  p_external_conversation_id text,
  p_provider_event_id text,
  p_event_type text,
  p_direction text,
  p_actor text,
  p_body_text text,
  p_evidence jsonb,
  p_occurred_at timestamptz
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  c public.empire_conversations%ROWTYPE;
  e public.empire_conversation_events%ROWTYPE;
  incoming_hash text;
  existing_hash text;
BEGIN
  IF trim(COALESCE(p_provider,''))='' THEN
    RAISE EXCEPTION 'provider required';
  END IF;
  IF trim(COALESCE(p_external_conversation_id,''))='' THEN
    RAISE EXCEPTION 'external conversation id required';
  END IF;
  IF trim(COALESCE(p_provider_event_id,''))='' THEN
    RAISE EXCEPTION 'provider event id required';
  END IF;
  IF trim(COALESCE(p_event_type,''))='' THEN
    RAISE EXCEPTION 'event type required';
  END IF;
  IF p_direction NOT IN ('inbound','outbound','internal') THEN
    RAISE EXCEPTION 'unsupported conversation direction';
  END IF;
  IF p_occurred_at IS NULL THEN
    RAISE EXCEPTION 'occurred_at required';
  END IF;

  incoming_hash := trim(
    COALESCE(p_evidence->>'payload_sha256','')
  );
  IF incoming_hash='' THEN
    RAISE EXCEPTION 'payload_sha256 evidence required';
  END IF;

  SELECT * INTO c
  FROM public.empire_conversations
  WHERE id=p_conversation_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'canonical conversation required';
  END IF;
  IF c.provider IS NOT NULL AND c.provider <> p_provider THEN
    RAISE EXCEPTION 'provider does not match canonical conversation';
  END IF;
  IF c.external_conversation_id IS NOT NULL
     AND c.external_conversation_id <> p_external_conversation_id THEN
    RAISE EXCEPTION 'external conversation id mismatch';
  END IF;

  SELECT * INTO e
  FROM public.empire_conversation_events
  WHERE conversation_id=p_conversation_id
    AND provider_event_id=p_provider_event_id;

  IF FOUND THEN
    existing_hash := trim(
      COALESCE(e.evidence->>'payload_sha256','')
    );
    IF existing_hash='' OR existing_hash <> incoming_hash THEN
      RETURN jsonb_build_object(
        'status','conflict',
        'reason','provider_event_payload_mismatch',
        'event_id',e.id,
        'conversation_id',e.conversation_id
      );
    END IF;
    RETURN jsonb_build_object(
      'status','existing',
      'event_id',e.id,
      'conversation_id',e.conversation_id
    );
  END IF;

  INSERT INTO public.empire_conversation_events(
    conversation_id,
    event_type,
    direction,
    actor,
    body_text,
    provider_event_id,
    evidence,
    occurred_at
  )
  VALUES(
    p_conversation_id,
    trim(p_event_type),
    p_direction,
    NULLIF(trim(COALESCE(p_actor,'')),''),
    p_body_text,
    trim(p_provider_event_id),
    COALESCE(p_evidence,'{}'::jsonb) ||
      jsonb_build_object(
        'provider',trim(p_provider),
        'external_conversation_id',
        trim(p_external_conversation_id)
      ),
    p_occurred_at
  )
  RETURNING * INTO e;

  RETURN jsonb_build_object(
    'status','recorded',
    'event_id',e.id,
    'conversation_id',e.conversation_id
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.record_revenue_exchange_observation(
  p_observation_key text,
  p_niche text,
  p_metro text,
  p_qualified_inventory_count integer,
  p_active_buyer_capacity integer,
  p_verified_price_per_lead_cents integer[],
  p_observed_at timestamptz,
  p_source text,
  p_evidence jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  o public.revenue_exchange_observations%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_observation_key,''))='' THEN
    RAISE EXCEPTION 'observation_key required';
  END IF;
  IF trim(COALESCE(p_niche,''))='' OR trim(COALESCE(p_metro,''))='' THEN
    RAISE EXCEPTION 'niche and metro required';
  END IF;
  IF p_qualified_inventory_count IS NULL
     OR p_qualified_inventory_count < 0 THEN
    RAISE EXCEPTION 'qualified inventory must be nonnegative';
  END IF;
  IF p_active_buyer_capacity IS NULL OR p_active_buyer_capacity < 0 THEN
    RAISE EXCEPTION 'buyer capacity must be nonnegative';
  END IF;
  IF p_observed_at IS NULL THEN
    RAISE EXCEPTION 'observed_at required';
  END IF;
  IF trim(COALESCE(p_source,''))='' THEN
    RAISE EXCEPTION 'source required';
  END IF;
  IF EXISTS (
    SELECT 1 FROM unnest(
      COALESCE(p_verified_price_per_lead_cents,'{}'::integer[])
    ) AS price
    WHERE price <= 0
  ) THEN
    RAISE EXCEPTION 'verified prices must be positive';
  END IF;

  SELECT * INTO o
  FROM public.revenue_exchange_observations
  WHERE observation_key=trim(p_observation_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'observation_id',o.id,
      'observation_key',o.observation_key
    );
  END IF;

  INSERT INTO public.revenue_exchange_observations(
    observation_key,
    niche,
    metro,
    qualified_inventory_count,
    active_buyer_capacity,
    verified_price_per_lead_cents,
    observed_at,
    source,
    evidence
  )
  VALUES(
    trim(p_observation_key),
    trim(p_niche),
    trim(p_metro),
    p_qualified_inventory_count,
    p_active_buyer_capacity,
    COALESCE(p_verified_price_per_lead_cents,'{}'::integer[]),
    p_observed_at,
    trim(p_source),
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO o;

  RETURN jsonb_build_object(
    'status','recorded',
    'observation_id',o.id,
    'observation_key',o.observation_key
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_commercial_outcomes_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'commercial outcomes are append-only';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_commercial_events_integrity()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
  v_role text := COALESCE(NULLIF(current_setting('role',true),'none'),session_user);
  v_amount bigint;
  v_cost bigint;
  v_margin bigint;
BEGIN
  IF TG_OP IN ('UPDATE','DELETE') THEN
    RAISE EXCEPTION 'commercial events are append-only';
  END IF;

  v_amount := COALESCE(NEW.amount_cents,0);
  v_cost := COALESCE(NEW.cost_cents,0);
  v_margin := COALESCE(NEW.margin_cents,0);

  IF (
    NEW.event_type='revenue_recognized'
    OR v_amount<>0 OR v_cost<>0 OR v_margin<>0
  ) AND v_role<>'empire_revenue_recognizer' THEN
    RAISE EXCEPTION 'financial commercial events require revenue recognizer role';
  END IF;

  IF NEW.event_type='outcome_recorded'
     AND v_role<>'empire_outcome_recorder' THEN
    RAISE EXCEPTION 'outcome commercial events require outcome recorder role';
  END IF;

  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.record_commercial_outcome(
  p_fulfilment_order_id uuid,
  p_delivery_outcome text,
  p_conversion_outcome text,
  p_buyer_satisfaction numeric,
  p_evidence_kind text,
  p_evidence_reference text,
  p_evidence jsonb,
  p_idempotency_key text,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  x public.commercial_outcomes%ROWTYPE;
  v_delivery text := lower(trim(COALESCE(p_delivery_outcome,'')));
  v_conversion text := lower(trim(COALESCE(p_conversion_outcome,'')));
  v_kind text := lower(trim(COALESCE(p_evidence_kind,'')));
  v_ref text := trim(COALESCE(p_evidence_reference,''));
  v_key text := trim(COALESCE(p_idempotency_key,''));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'fulfilment order required'; END IF;
  IF v_delivery NOT IN ('delivered','confirmed','rejected','failed','refunded','unknown') THEN
    RAISE EXCEPTION 'unsupported delivery outcome';
  END IF;
  IF v_conversion NOT IN ('unknown','qualified','booked','won','lost','no_response') THEN
    RAISE EXCEPTION 'unsupported conversion outcome';
  END IF;
  IF p_buyer_satisfaction IS NOT NULL
     AND (p_buyer_satisfaction < 1 OR p_buyer_satisfaction > 5) THEN
    RAISE EXCEPTION 'buyer satisfaction must be 1-5';
  END IF;
  IF v_kind NOT IN (
    'outbound_reply','buyer_feedback','delivery_receipt',
    'crm','provider_event','manual_verified'
  ) THEN RAISE EXCEPTION 'supported outcome evidence required'; END IF;
  IF v_ref='' OR length(v_key)<8 OR length(v_key)>160 OR v_actor='' THEN
    RAISE EXCEPTION 'evidence reference, idempotency key and actor required';
  END IF;
  IF jsonb_typeof(COALESCE(p_evidence,'{}'::jsonb)) <> 'object' THEN
    RAISE EXCEPTION 'outcome evidence object required';
  END IF;

  SELECT * INTO o FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.state NOT IN (
    'delivered','confirmed','invoiced','paid','settled','outcome_captured'
  ) THEN RAISE EXCEPTION 'post-delivery fulfilment order required'; END IF;

  SELECT * INTO x FROM public.commercial_outcomes WHERE idempotency_key=v_key;
  IF FOUND THEN
    IF x.fulfilment_order_id IS DISTINCT FROM o.id
       OR x.delivery_outcome IS DISTINCT FROM v_delivery
       OR x.conversion_outcome IS DISTINCT FROM v_conversion
       OR x.evidence_kind IS DISTINCT FROM v_kind
       OR x.evidence_reference IS DISTINCT FROM v_ref THEN
      RAISE EXCEPTION 'idempotency key belongs to different outcome';
    END IF;
    RETURN jsonb_build_object(
      'decision','existing_outcome','outcome_id',x.id,
      'fulfilment_order_id',o.id,'actual_revenue',false
    );
  END IF;

  INSERT INTO public.commercial_outcomes(
    fulfilment_order_id,delivery_outcome,conversion_outcome,buyer_satisfaction,
    evidence_kind,evidence_reference,evidence,idempotency_key,actor
  ) VALUES (
    o.id,v_delivery,v_conversion,p_buyer_satisfaction,v_kind,v_ref,
    COALESCE(p_evidence,'{}'::jsonb),v_key,v_actor
  ) RETURNING * INTO x;

  UPDATE public.fulfilment_orders
     SET outcome_at=COALESCE(outcome_at,x.recorded_at),
         state=CASE WHEN state='settled' THEN 'outcome_captured' ELSE state END,
         updated_at=clock_timestamp()
   WHERE id=o.id;

  INSERT INTO public.commercial_events(
    event_type,opportunity_id,fulfilment_order_id,prospect_id,entity_id,buyer_id,
    product_id,channel,actor,amount_cents,cost_cents,margin_cents,payload,
    occurred_at,idempotency_key
  ) VALUES (
    'outcome_recorded',o.opportunity_id,o.id,o.prospect_id,o.entity_id,o.buyer_id,
    o.product_id,'outcome_feedback',v_actor,0,0,0,
    jsonb_build_object(
      'outcome_id',x.id,'delivery_outcome',x.delivery_outcome,
      'conversion_outcome',x.conversion_outcome,
      'buyer_satisfaction',x.buyer_satisfaction,
      'evidence_kind',x.evidence_kind,'evidence_reference',x.evidence_reference,
      'actual_revenue',false
    ),
    x.recorded_at,'outcome:'||x.id::text
  );

  RETURN jsonb_build_object(
    'decision','recorded_outcome','outcome_id',x.id,
    'fulfilment_order_id',o.id,'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.recognize_bsc_revenue(
  p_fulfilment_order_id uuid,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  r public.bsc_payment_requests%ROWTYPE;
  d public.bsc_payment_evidence%ROWTYPE;
  a public.bsc_escrow_agreements%ROWTYPE;
  e public.bsc_escrow_evidence%ROWTYPE;
  existing public.commercial_events%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
  v_source text;
  v_evidence_id uuid;
  v_tx text;
  v_paid_at timestamptz;
  v_cost bigint;
  v_margin bigint;
  v_key text;
BEGIN
  IF p_fulfilment_order_id IS NULL OR v_actor='' THEN
    RAISE EXCEPTION 'fulfilment order and actor required';
  END IF;

  v_key := 'revenue:'||p_fulfilment_order_id::text||':v1';

  SELECT * INTO existing
    FROM public.commercial_events
   WHERE idempotency_key=v_key;
  IF FOUND THEN
    RETURN jsonb_build_object(
      'decision','existing_revenue',
      'fulfilment_order_id',existing.fulfilment_order_id,
      'amount_cents',existing.amount_cents,
      'cost_cents',existing.cost_cents,
      'margin_cents',existing.margin_cents,
      'actual_revenue',true
    );
  END IF;

  SELECT * INTO o
    FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.buyer_id IS NULL OR o.price_cents<=0 THEN
    RAISE EXCEPTION 'priced buyer fulfilment order required';
  END IF;
  IF lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''))
     !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'approved commercial terms required';
  END IF;

  SELECT rr.* INTO r
    FROM public.bsc_payment_requests rr
    JOIN public.bsc_payment_evidence dd ON dd.request_id=rr.id
   WHERE rr.fulfilment_order_id=o.id
     AND rr.settlement_mode='direct'
     AND rr.status='approved'
     AND rr.approved_at IS NOT NULL
     AND NULLIF(trim(COALESCE(rr.approved_by,'')),'') IS NOT NULL
   ORDER BY dd.verified_at DESC
   LIMIT 1;

  IF FOUND THEN
    SELECT * INTO d
      FROM public.bsc_payment_evidence
     WHERE request_id=r.id
     ORDER BY verified_at DESC
     LIMIT 1;
    v_source := 'direct_payment';
    v_evidence_id := d.id;
    v_tx := d.transaction_hash;
    v_paid_at := d.verified_at;
  ELSE
    SELECT rr.* INTO r
      FROM public.bsc_payment_requests rr
      JOIN public.bsc_escrow_agreements aa ON aa.request_id=rr.id
      JOIN public.bsc_escrow_evidence ee
        ON ee.agreement_id=aa.id AND ee.action='released'
     WHERE rr.fulfilment_order_id=o.id
       AND rr.settlement_mode='escrow'
       AND rr.status='approved'
       AND rr.approved_at IS NOT NULL
       AND NULLIF(trim(COALESCE(rr.approved_by,'')),'') IS NOT NULL
       AND aa.status='released'
     ORDER BY ee.verified_at DESC
     LIMIT 1;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'no revenue-eligible verified BSC settlement evidence';
    END IF;

    SELECT * INTO a
      FROM public.bsc_escrow_agreements
     WHERE request_id=r.id;
    SELECT * INTO e
      FROM public.bsc_escrow_evidence
     WHERE agreement_id=a.id AND action='released'
     ORDER BY verified_at DESC
     LIMIT 1;

    v_source := 'escrow_release';
    v_evidence_id := e.id;
    v_tx := e.transaction_hash;
    v_paid_at := e.verified_at;
  END IF;

  IF r.commercial_terms_sha256 IS DISTINCT FROM
     lower(o.commercial_payload->>'commercial_terms_sha256') THEN
    RAISE EXCEPTION 'payment evidence commercial terms mismatch';
  END IF;
  IF r.amount_usdt*100 IS DISTINCT FROM o.price_cents::numeric THEN
    RAISE EXCEPTION 'settlement amount does not equal approved USD price';
  END IF;

  v_cost := COALESCE(o.acquisition_cost_cents,0)
          + COALESCE(o.fulfilment_cost_cents,0);
  v_margin := o.price_cents-v_cost;
  IF v_cost<0 OR v_margin<=0 THEN
    RAISE EXCEPTION 'positive realized margin required';
  END IF;

  INSERT INTO public.commercial_events(
    event_type,opportunity_id,fulfilment_order_id,prospect_id,entity_id,buyer_id,
    product_id,channel,actor,amount_cents,cost_cents,margin_cents,payload,
    occurred_at,idempotency_key
  ) VALUES (
    'revenue_recognized',o.opportunity_id,o.id,o.prospect_id,o.entity_id,o.buyer_id,
    o.product_id,'bsc_usdt',v_actor,o.price_cents,v_cost,v_margin,
    jsonb_build_object(
      'settlement_source',v_source,
      'payment_request_id',r.id,
      'evidence_id',v_evidence_id,
      'transaction_hash',v_tx,
      'commercial_terms_sha256',r.commercial_terms_sha256,
      'settlement_asset','USDT','settlement_chain','BSC',
      'actual_revenue',true
    ),
    v_paid_at,v_key
  );

  UPDATE public.fulfilment_orders
     SET state=CASE
           WHEN EXISTS(
             SELECT 1 FROM public.commercial_outcomes co
              WHERE co.fulfilment_order_id=o.id
           ) THEN 'outcome_captured'
           ELSE 'settled'
         END,
         actual_margin_cents=v_margin,
         paid_at=COALESCE(paid_at,v_paid_at),
         settled_at=COALESCE(settled_at,v_paid_at),
         commercial_payload=COALESCE(commercial_payload,'{}'::jsonb) ||
           jsonb_build_object(
             'recognized_revenue_cents',o.price_cents,
             'recognized_revenue_source',v_source,
             'recognized_revenue_evidence_id',v_evidence_id,
             'recognized_revenue_transaction_hash',v_tx,
             'recognized_revenue_at',v_paid_at
           ),
         updated_at=clock_timestamp()
   WHERE id=o.id;

  RETURN jsonb_build_object(
    'decision','revenue_recognized',
    'fulfilment_order_id',o.id,
    'amount_cents',o.price_cents,
    'cost_cents',v_cost,
    'margin_cents',v_margin,
    'settlement_source',v_source,
    'evidence_id',v_evidence_id,
    'actual_revenue',true
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.list_revenue_recognition_work(
  p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  result jsonb;
BEGIN
  IF p_limit IS NULL OR p_limit<1 OR p_limit>100 THEN
    RAISE EXCEPTION 'revenue recognition work limit must be 1-100';
  END IF;

  WITH candidates AS (
    SELECT
      o.id AS fulfilment_order_id,
      o.price_cents,
      EXISTS(
        SELECT 1
          FROM public.bsc_payment_requests r
          JOIN public.bsc_payment_evidence d ON d.request_id=r.id
         WHERE r.fulfilment_order_id=o.id
           AND r.settlement_mode='direct'
           AND r.status='approved'
      ) AS direct_evidence,
      EXISTS(
        SELECT 1
          FROM public.bsc_payment_requests r
          JOIN public.bsc_escrow_agreements a ON a.request_id=r.id
          JOIN public.bsc_escrow_evidence e
            ON e.agreement_id=a.id AND e.action='released'
         WHERE r.fulfilment_order_id=o.id
           AND r.settlement_mode='escrow'
           AND r.status='approved'
           AND a.status='released'
      ) AS escrow_release,
      EXISTS(
        SELECT 1
          FROM public.bsc_payment_requests r
          LEFT JOIN public.bsc_payment_evidence d
            ON d.request_id=r.id AND r.settlement_mode='direct'
          LEFT JOIN public.bsc_escrow_agreements a
            ON a.request_id=r.id AND r.settlement_mode='escrow'
          LEFT JOIN public.bsc_escrow_evidence e
            ON e.agreement_id=a.id AND e.action='released'
         WHERE r.fulfilment_order_id=o.id
           AND r.status='approved'
           AND r.amount_usdt*100=o.price_cents::numeric
           AND (
             (r.settlement_mode='direct' AND d.id IS NOT NULL)
             OR
             (r.settlement_mode='escrow' AND a.status='released' AND e.id IS NOT NULL)
           )
      ) AS amount_matches
    FROM public.fulfilment_orders o
    WHERE o.price_cents>0
      AND NOT EXISTS(
        SELECT 1 FROM public.commercial_events ce
         WHERE ce.idempotency_key='revenue:'||o.id::text||':v1'
      )
      AND (
        EXISTS(
          SELECT 1 FROM public.bsc_payment_requests r
          JOIN public.bsc_payment_evidence d ON d.request_id=r.id
          WHERE r.fulfilment_order_id=o.id AND r.settlement_mode='direct'
        )
        OR EXISTS(
          SELECT 1 FROM public.bsc_payment_requests r
          JOIN public.bsc_escrow_agreements a ON a.request_id=r.id
          JOIN public.bsc_escrow_evidence e
            ON e.agreement_id=a.id AND e.action='released'
          WHERE r.fulfilment_order_id=o.id AND r.settlement_mode='escrow'
        )
      )
    ORDER BY o.updated_at,o.id
    LIMIT p_limit
  )
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'fulfilment_order_id',fulfilment_order_id,
    'price_cents',price_cents,
    'direct_evidence',direct_evidence,
    'escrow_release',escrow_release,
    'amount_matches',amount_matches
  )), '[]'::jsonb)
  INTO result
  FROM candidates;

  RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_commercial_outcome_feedback(
  p_limit integer DEFAULT 100
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  result jsonb;
BEGIN
  IF p_limit IS NULL OR p_limit<1 OR p_limit>1000 THEN
    RAISE EXCEPTION 'feedback limit must be 1-1000';
  END IF;

  SELECT COALESCE(jsonb_agg(row_data ORDER BY updated_at DESC), '[]'::jsonb)
  INTO result
  FROM (
    SELECT
      o.updated_at,
      jsonb_build_object(
        'fulfilment_order_id',o.id,
        'opportunity_id',o.opportunity_id,
        'prospect_id',o.prospect_id,
        'entity_id',o.entity_id,
        'buyer_id',o.buyer_id,
        'product_id',o.product_id,
        'state',o.state,
        'price_cents',o.price_cents,
        'acquisition_cost_cents',o.acquisition_cost_cents,
        'fulfilment_cost_cents',o.fulfilment_cost_cents,
        'actual_margin_cents',o.actual_margin_cents,
        'delivery_outcome',co.delivery_outcome,
        'conversion_outcome',co.conversion_outcome,
        'buyer_satisfaction',co.buyer_satisfaction,
        'outcome_recorded_at',co.recorded_at,
        'actual_revenue',ce.id IS NOT NULL,
        'actual_revenue_cents',COALESCE(ce.amount_cents,0),
        'actual_cost_cents',COALESCE(ce.cost_cents,0),
        'gross_profit_cents',COALESCE(ce.margin_cents,0),
        'revenue_recognized_at',ce.occurred_at,
        'previous_purchase',(ce.id IS NOT NULL),
        'booked',(co.conversion_outcome IN ('booked','won')),
        'converted',(co.conversion_outcome='won')
      ) AS row_data
    FROM public.fulfilment_orders o
    LEFT JOIN LATERAL (
      SELECT x.*
        FROM public.commercial_outcomes x
       WHERE x.fulfilment_order_id=o.id
       ORDER BY x.recorded_at DESC,x.id DESC
       LIMIT 1
    ) co ON true
    LEFT JOIN LATERAL (
      SELECT x.*
        FROM public.commercial_events x
       WHERE x.idempotency_key='revenue:'||o.id::text||':v1'
       LIMIT 1
    ) ce ON true
    WHERE co.id IS NOT NULL OR ce.id IS NOT NULL
    ORDER BY o.updated_at DESC
    LIMIT p_limit
  ) q;

  RETURN result;
END;
$$;

DROP TRIGGER IF EXISTS guard_outbound_events_append_only ON public.outbound_events;
CREATE TRIGGER guard_outbound_events_append_only
BEFORE UPDATE OR DELETE ON public.outbound_events
FOR EACH ROW EXECUTE FUNCTION public.guard_outbound_events_append_only();

DROP TRIGGER IF EXISTS guard_closer_events_append_only ON public.closer_events;
CREATE TRIGGER guard_closer_events_append_only
BEFORE UPDATE OR DELETE ON public.closer_events
FOR EACH ROW EXECUTE FUNCTION public.guard_closer_events_append_only();

DROP TRIGGER IF EXISTS guard_commercial_terms_events_append_only ON public.commercial_terms_events;
CREATE TRIGGER guard_commercial_terms_events_append_only
BEFORE UPDATE OR DELETE ON public.commercial_terms_events
FOR EACH ROW EXECUTE FUNCTION public.guard_commercial_terms_events_append_only();

DROP TRIGGER IF EXISTS guard_bsc_payment_request ON public.bsc_payment_requests;
CREATE TRIGGER guard_bsc_payment_request
BEFORE UPDATE OR DELETE ON public.bsc_payment_requests
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_payment_request();

DROP TRIGGER IF EXISTS guard_bsc_payment_evidence ON public.bsc_payment_evidence;
CREATE TRIGGER guard_bsc_payment_evidence
BEFORE INSERT OR UPDATE OR DELETE ON public.bsc_payment_evidence
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_payment_evidence();

DROP TRIGGER IF EXISTS guard_bsc_payment_request_event ON public.bsc_payment_request_events;
CREATE TRIGGER guard_bsc_payment_request_event
BEFORE UPDATE OR DELETE ON public.bsc_payment_request_events
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_payment_request_event();

DROP TRIGGER IF EXISTS guard_bsc_escrow_evidence ON public.bsc_escrow_evidence;
CREATE TRIGGER guard_bsc_escrow_evidence
BEFORE UPDATE OR DELETE ON public.bsc_escrow_evidence
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_escrow_evidence();

DROP TRIGGER IF EXISTS guard_direct_bsc_payment_mode ON public.bsc_payment_evidence;
CREATE TRIGGER guard_direct_bsc_payment_mode
BEFORE INSERT ON public.bsc_payment_evidence
FOR EACH ROW EXECUTE FUNCTION public.guard_direct_bsc_payment_mode();

DROP TRIGGER IF EXISTS guard_empire_conversation_events_append_only
ON public.empire_conversation_events;
CREATE TRIGGER guard_empire_conversation_events_append_only
BEFORE UPDATE OR DELETE ON public.empire_conversation_events
FOR EACH ROW EXECUTE FUNCTION public.guard_empire_conversation_events_append_only();

DROP TRIGGER IF EXISTS guard_commercial_outcomes_append_only ON public.commercial_outcomes;
CREATE TRIGGER guard_commercial_outcomes_append_only
BEFORE UPDATE OR DELETE ON public.commercial_outcomes
FOR EACH ROW EXECUTE FUNCTION public.guard_commercial_outcomes_append_only();

DROP TRIGGER IF EXISTS guard_commercial_events_integrity ON public.commercial_events;
CREATE TRIGGER guard_commercial_events_integrity
BEFORE INSERT OR UPDATE OR DELETE ON public.commercial_events
FOR EACH ROW EXECUTE FUNCTION public.guard_commercial_events_integrity();

RESET ROLE;
