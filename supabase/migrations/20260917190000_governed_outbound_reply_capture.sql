-- Empire Phase 3E: governed outbound and reply capture.
-- Forward-only, fail-closed. Creates no messages and sends nothing.
BEGIN;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_outbound_approver') THEN
        CREATE ROLE empire_outbound_approver NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_outbound_sender') THEN
        CREATE ROLE empire_outbound_sender NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_reply_ingest') THEN
        CREATE ROLE empire_reply_ingest NOLOGIN NOINHERIT;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_outbound_approver, empire_outbound_sender, empire_reply_ingest;
REVOKE empire_outbound_approver, empire_outbound_sender, empire_reply_ingest FROM service_role;

CREATE TABLE public.outbound_suppressions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_contact text NOT NULL UNIQUE,
    contact_type text NOT NULL CHECK (contact_type IN ('email','phone','domain')),
    reason text NOT NULL,
    source text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE public.outbound_intents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id uuid REFERENCES public.prospects(id) ON DELETE RESTRICT,
    entity_id uuid REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    buyer_id uuid REFERENCES public.buyers(id) ON DELETE RESTRICT,
    opportunity_id uuid REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
    channel text NOT NULL CHECK (channel IN ('email','sms','voice','a2a')),
    recipient text NOT NULL,
    normalized_recipient text NOT NULL,
    subject text,
    body_text text NOT NULL,
    body_html text,
    offer_key text,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','pending_approval','approved','rejected','sent','delivered',
        'replied','suppressed','failed','cancelled'
    )),
    idempotency_key text NOT NULL UNIQUE,
    proposed_by text NOT NULL,
    approved_by text,
    approved_at timestamptz,
    expires_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (prospect_id IS NOT NULL OR entity_id IS NOT NULL OR buyer_id IS NOT NULL)
);
CREATE INDEX outbound_intents_state_idx ON public.outbound_intents(status, created_at);
CREATE INDEX outbound_intents_entity_idx ON public.outbound_intents(entity_id, created_at DESC);
CREATE TABLE public.outbound_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id uuid NOT NULL REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN (
        'proposed','approved','rejected','send_attempt','sent','delivered','failed',
        'reply_received','reply_classified','suppressed','cancelled'
    )),
    actor text NOT NULL,
    provider_message_id text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX outbound_events_intent_idx ON public.outbound_events(intent_id, occurred_at);

CREATE TABLE public.outbound_replies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id uuid NOT NULL REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
    provider_message_id text,
    from_contact text NOT NULL,
    normalized_from_contact text NOT NULL,
    subject text,
    body_text text NOT NULL,
    classification text NOT NULL DEFAULT 'unclassified' CHECK (classification IN (
        'unclassified','positive','negative','question','objection','later','unsubscribe','bounce','other'
    )),
    confidence numeric(5,4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    received_at timestamptz NOT NULL,
    classified_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(intent_id, provider_message_id)
);
CREATE INDEX outbound_replies_state_idx ON public.outbound_replies(classification, received_at DESC);
ALTER TABLE public.outbound_suppressions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_replies ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.outbound_suppressions, public.outbound_intents,
    public.outbound_events, public.outbound_replies
FROM PUBLIC, anon, authenticated, service_role,
    empire_outbound_approver, empire_outbound_sender, empire_reply_ingest;

GRANT SELECT ON public.outbound_suppressions, public.outbound_intents,
    public.outbound_events, public.outbound_replies TO service_role;

CREATE FUNCTION public.guard_outbound_events_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'outbound events are append-only';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_outbound_events_append_only
BEFORE UPDATE OR DELETE ON public.outbound_events
FOR EACH ROW EXECUTE FUNCTION public.guard_outbound_events_append_only();
CREATE FUNCTION public.propose_outbound_intent(
    p_entity_id uuid, p_prospect_id uuid, p_buyer_id uuid, p_opportunity_id uuid,
    p_channel text, p_recipient text, p_subject text, p_body_text text,
    p_body_html text, p_offer_key text, p_idempotency_key text,
    p_proposed_by text, p_expires_at timestamptz, p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
CREATE FUNCTION public.approve_outbound_intent(p_intent_id uuid,p_approved_by text,p_note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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

CREATE FUNCTION public.claim_outbound_send(p_intent_id uuid,p_actor text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
CREATE FUNCTION public.record_outbound_delivery(p_intent_id uuid,p_event_type text,p_actor text,p_provider_message_id text,p_payload jsonb DEFAULT '{}'::jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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

CREATE FUNCTION public.ingest_outbound_reply(p_intent_id uuid,p_provider_message_id text,p_from_contact text,p_subject text,p_body_text text,p_received_at timestamptz,p_metadata jsonb DEFAULT '{}'::jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
CREATE FUNCTION public.classify_outbound_reply(p_reply_id uuid,p_classification text,p_confidence numeric,p_actor text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
CREATE FUNCTION public.get_outbound_intent_review(p_intent_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
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
REVOKE ALL ON FUNCTION public.get_outbound_intent_review(uuid)
FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.get_outbound_intent_review(uuid)
TO service_role,empire_outbound_approver,empire_outbound_sender;
REVOKE ALL ON FUNCTION public.guard_outbound_events_append_only()
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_approver,empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.propose_outbound_intent(uuid,uuid,uuid,uuid,text,text,text,text,text,text,text,text,timestamptz,jsonb)
FROM PUBLIC,anon,authenticated,empire_outbound_approver,empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.approve_outbound_intent(uuid,text,text)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.claim_outbound_send(uuid,text)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_approver,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.record_outbound_delivery(uuid,text,text,text,jsonb)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_approver,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.ingest_outbound_reply(uuid,text,text,text,text,timestamptz,jsonb)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_approver,empire_outbound_sender;
REVOKE ALL ON FUNCTION public.classify_outbound_reply(uuid,text,numeric,text)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_approver,empire_outbound_sender;

GRANT EXECUTE ON FUNCTION public.propose_outbound_intent(uuid,uuid,uuid,uuid,text,text,text,text,text,text,text,text,timestamptz,jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.approve_outbound_intent(uuid,text,text) TO empire_outbound_approver;
GRANT EXECUTE ON FUNCTION public.claim_outbound_send(uuid,text) TO empire_outbound_sender;
GRANT EXECUTE ON FUNCTION public.record_outbound_delivery(uuid,text,text,text,jsonb) TO empire_outbound_sender;
GRANT EXECUTE ON FUNCTION public.ingest_outbound_reply(uuid,text,text,text,text,timestamptz,jsonb) TO empire_reply_ingest;
GRANT EXECUTE ON FUNCTION public.classify_outbound_reply(uuid,text,numeric,text) TO empire_reply_ingest;

COMMENT ON TABLE public.outbound_intents IS 'Governed outbound proposals. No intent can send without explicit human approval and dedicated sender role.';
COMMENT ON TABLE public.outbound_replies IS 'Inbound replies tied to canonical outbound intent; classification may suppress future contact.';
COMMIT;
