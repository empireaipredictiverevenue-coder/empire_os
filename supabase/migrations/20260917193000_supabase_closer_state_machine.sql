-- Empire Phase 3E: Supabase-backed closer state machine.
-- Replaces legacy LLM-driven SQLite settlement behavior. No autonomous close/payment/revenue.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_closer_approver') THEN
    CREATE ROLE empire_closer_approver NOLOGIN NOINHERIT;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO empire_closer_approver;
REVOKE empire_closer_approver FROM service_role;

CREATE TABLE public.closer_cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  outbound_intent_id uuid NOT NULL REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
  reply_id uuid NOT NULL UNIQUE REFERENCES public.outbound_replies(id) ON DELETE RESTRICT,
  prospect_id uuid REFERENCES public.prospects(id) ON DELETE RESTRICT,
  entity_id uuid REFERENCES public.business_entities(id) ON DELETE RESTRICT,
  buyer_id uuid REFERENCES public.buyers(id) ON DELETE RESTRICT,
  opportunity_id uuid REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
  fulfilment_order_id uuid REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  state text NOT NULL DEFAULT 'engaged' CHECK (state IN (
    'engaged','qualified','proposal_ready','proposal_approved','awaiting_payment',
    'won','lost','paused'
  )),
  opened_from_classification text NOT NULL,
  opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX closer_cases_state_idx ON public.closer_cases(state,updated_at DESC);
CREATE TABLE public.closer_recommendations (
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
CREATE INDEX closer_recommendations_case_idx ON public.closer_recommendations(case_id,created_at DESC);

CREATE TABLE public.closer_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  event_type text NOT NULL,
  actor text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX closer_events_case_idx ON public.closer_events(case_id,occurred_at DESC);

ALTER TABLE public.closer_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.closer_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.closer_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.closer_cases,public.closer_recommendations,public.closer_events
FROM PUBLIC,anon,authenticated,service_role,empire_closer_approver;
GRANT SELECT ON public.closer_cases,public.closer_recommendations,public.closer_events TO service_role;
CREATE FUNCTION public.guard_closer_events_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'closer events are append-only'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER guard_closer_events_append_only
BEFORE UPDATE OR DELETE ON public.closer_events
FOR EACH ROW EXECUTE FUNCTION public.guard_closer_events_append_only();

CREATE FUNCTION public.open_closer_case(p_reply_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
CREATE FUNCTION public.record_closer_recommendation(p_case_id uuid,p_type text,p_confidence numeric,p_rationale jsonb,p_message text,p_model_key text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE c public.closer_cases%ROWTYPE; r public.closer_recommendations%ROWTYPE; v text:=lower(trim(p_type));
BEGIN
  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost') THEN RAISE EXCEPTION 'terminal closer case'; END IF;
  IF v NOT IN ('qualify','follow_up','answer_question','handle_objection','prepare_proposal','await_payment','pause','mark_lost','escalate_human') THEN RAISE EXCEPTION 'unsupported closer recommendation'; END IF;
  IF p_confidence IS NULL OR p_confidence<0 OR p_confidence>1 THEN RAISE EXCEPTION 'invalid confidence'; END IF;
  INSERT INTO public.closer_recommendations(case_id,recommendation_type,confidence,rationale,proposed_message,model_key)
  VALUES(c.id,v,p_confidence,COALESCE(p_rationale,'{}'),p_message,trim(p_model_key)) RETURNING * INTO r;
  INSERT INTO public.closer_events(case_id,event_type,actor,payload) VALUES(c.id,'recommendation_recorded','closer-planner',jsonb_build_object('recommendation_id',r.id,'type',v,'confidence',p_confidence,'model_key',r.model_key));
  RETURN jsonb_build_object('decision','recorded','recommendation_id',r.id,'case_id',c.id,'state',c.state,'actual_revenue',false);
END;
$$;

CREATE FUNCTION public.advance_closer_case(p_case_id uuid,p_next_state text,p_actor text,p_fulfilment_order_id uuid,p_note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
REVOKE ALL ON FUNCTION public.guard_closer_events_append_only()
FROM PUBLIC,anon,authenticated,service_role,empire_closer_approver;
REVOKE ALL ON FUNCTION public.open_closer_case(uuid)
FROM PUBLIC,anon,authenticated,empire_closer_approver;
REVOKE ALL ON FUNCTION public.record_closer_recommendation(uuid,text,numeric,jsonb,text,text)
FROM PUBLIC,anon,authenticated,empire_closer_approver;
REVOKE ALL ON FUNCTION public.advance_closer_case(uuid,text,text,uuid,text)
FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.open_closer_case(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.record_closer_recommendation(uuid,text,numeric,jsonb,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.advance_closer_case(uuid,text,text,uuid,text) TO empire_closer_approver;

COMMENT ON TABLE public.closer_cases IS 'Supabase-backed commercial conversation state. The closer cannot activate buyers, settle payments or recognize revenue.';
COMMENT ON TABLE public.closer_recommendations IS 'Append-only model recommendations for human-governed commercial action and later outcome calibration.';
COMMIT;
