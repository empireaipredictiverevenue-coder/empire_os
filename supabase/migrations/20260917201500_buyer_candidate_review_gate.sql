-- Phase 3E buyer candidate review gate.
-- Forward-only; creates no outreach and sends nothing.
BEGIN;

CREATE TABLE public.buyer_candidate_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id uuid NOT NULL REFERENCES public.prospects(id) ON DELETE RESTRICT,
    entity_id uuid REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    contact_name text NOT NULL,
    contact_title text NOT NULL,
    contact_email text NOT NULL,
    offer_key text NOT NULL,
    company_score numeric(6,2) NOT NULL CHECK (company_score BETWEEN 0 AND 100),
    decision_score numeric(5,4) NOT NULL CHECK (decision_score BETWEEN 0 AND 1),
    evidence jsonb NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired')),
    proposed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reviewed_at timestamptz,
    reviewed_by text,
    review_note text
);
CREATE INDEX buyer_candidate_reviews_state_idx
ON public.buyer_candidate_reviews(status, proposed_at DESC);
CREATE TABLE public.buyer_candidate_review_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id uuid NOT NULL REFERENCES public.buyer_candidate_reviews(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (event_type IN ('proposed','approved','rejected','outbound_proposed')),
    actor text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX buyer_candidate_review_events_idx
ON public.buyer_candidate_review_events(review_id, occurred_at);

ALTER TABLE public.buyer_candidate_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.buyer_candidate_review_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.buyer_candidate_reviews, public.buyer_candidate_review_events
FROM PUBLIC, anon, authenticated, service_role,
     empire_outbound_approver, empire_outbound_sender, empire_reply_ingest;
GRANT SELECT ON public.buyer_candidate_reviews, public.buyer_candidate_review_events
TO service_role;

CREATE FUNCTION public.guard_buyer_candidate_review_events_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'buyer candidate review events are append-only'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER guard_buyer_candidate_review_events_append_only
BEFORE UPDATE OR DELETE ON public.buyer_candidate_review_events
FOR EACH ROW EXECUTE FUNCTION public.guard_buyer_candidate_review_events_append_only();

CREATE FUNCTION public.propose_buyer_candidate_review(
    p_prospect_id uuid, p_entity_id uuid, p_contact_name text, p_contact_title text,
    p_contact_email text, p_offer_key text, p_company_score numeric,
    p_decision_score numeric, p_evidence jsonb, p_idempotency_key text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r public.buyer_candidate_reviews%ROWTYPE; v_email text:=lower(trim(COALESCE(p_contact_email,'')));
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.prospects WHERE id=p_prospect_id) THEN RAISE EXCEPTION 'canonical prospect required'; END IF;
    IF p_entity_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.business_entities WHERE id=p_entity_id) THEN RAISE EXCEPTION 'canonical entity required'; END IF;
    IF length(trim(COALESCE(p_contact_name,'')))<3 OR length(trim(COALESCE(p_contact_title,'')))<2 THEN RAISE EXCEPTION 'verified decision maker required'; END IF;
    IF v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' THEN RAISE EXCEPTION 'verified contact email required'; END IF;
    IF p_company_score IS NULL OR p_company_score<0 OR p_company_score>100 OR p_decision_score IS NULL OR p_decision_score<0.5 OR p_decision_score>1 THEN RAISE EXCEPTION 'candidate score threshold not met'; END IF;
    IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN RAISE EXCEPTION 'candidate evidence required'; END IF;
    SELECT * INTO r FROM public.buyer_candidate_reviews WHERE idempotency_key=trim(p_idempotency_key);
    IF FOUND THEN RETURN jsonb_build_object('decision','existing','review_id',r.id,'status',r.status,'actual_revenue',false); END IF;
    INSERT INTO public.buyer_candidate_reviews(
        prospect_id,entity_id,contact_name,contact_title,contact_email,offer_key,
        company_score,decision_score,evidence,idempotency_key
    ) VALUES(
        p_prospect_id,p_entity_id,trim(p_contact_name),trim(p_contact_title),v_email,trim(p_offer_key),
        p_company_score,p_decision_score,p_evidence,trim(p_idempotency_key)
    ) RETURNING * INTO r;
    INSERT INTO public.buyer_candidate_review_events(review_id,event_type,actor,payload)
    VALUES(r.id,'proposed','buyer-discovery',jsonb_build_object('prospect_id',r.prospect_id,'offer_key',r.offer_key));
    RETURN jsonb_build_object('decision','proposed','review_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;

CREATE FUNCTION public.review_buyer_candidate(
    p_review_id uuid, p_decision text, p_actor text, p_note text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r public.buyer_candidate_reviews%ROWTYPE; v text:=lower(trim(p_decision));
BEGIN
    IF v NOT IN ('approved','rejected') THEN RAISE EXCEPTION 'review decision must be approved or rejected'; END IF;
    SELECT * INTO r FROM public.buyer_candidate_reviews WHERE id=p_review_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer candidate review not found'; END IF;
    IF r.status<>'pending' THEN RAISE EXCEPTION 'pending buyer candidate review required'; END IF;
    IF r.proposed_at < clock_timestamp()-interval '7 days' THEN
      UPDATE public.buyer_candidate_reviews SET status='expired' WHERE id=r.id;
      RAISE EXCEPTION 'buyer candidate review expired';
    END IF;
    UPDATE public.buyer_candidate_reviews
    SET status=v,reviewed_at=clock_timestamp(),reviewed_by=trim(p_actor),review_note=trim(COALESCE(p_note,''))
    WHERE id=r.id RETURNING * INTO r;
    INSERT INTO public.buyer_candidate_review_events(review_id,event_type,actor,payload)
    VALUES(r.id,v,trim(p_actor),jsonb_build_object('note',r.review_note));
    RETURN jsonb_build_object('decision',v,'review_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;

CREATE FUNCTION public.propose_reviewed_outbound_intent(
    p_review_id uuid, p_subject text, p_body_text text, p_body_html text,
    p_idempotency_key text, p_proposed_by text, p_expires_at timestamptz,
    p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r public.buyer_candidate_reviews%ROWTYPE; result jsonb; merged jsonb;
BEGIN
    SELECT * INTO r FROM public.buyer_candidate_reviews WHERE id=p_review_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer candidate review not found'; END IF;
    IF r.status<>'approved' THEN RAISE EXCEPTION 'approved buyer candidate review required'; END IF;
    IF r.reviewed_at IS NULL OR r.reviewed_at < clock_timestamp()-interval '7 days' THEN RAISE EXCEPTION 'fresh buyer candidate approval required'; END IF;
    merged := COALESCE(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'buyer_candidate_review_id',r.id,'decision_score',r.decision_score,
      'company_score',r.company_score,'candidate_evidence',r.evidence
    );
    result := public.propose_outbound_intent(
      r.entity_id,r.prospect_id,NULL,NULL,'email',r.contact_email,p_subject,p_body_text,
      p_body_html,r.offer_key,p_idempotency_key,p_proposed_by,p_expires_at,merged
    );
    INSERT INTO public.buyer_candidate_review_events(review_id,event_type,actor,payload)
    VALUES(r.id,'outbound_proposed',trim(p_proposed_by),jsonb_build_object('intent_id',result->>'intent_id'));
    RETURN result || jsonb_build_object('buyer_candidate_review_id',r.id);
END;
$$;

REVOKE EXECUTE ON FUNCTION public.propose_outbound_intent(
    uuid,uuid,uuid,uuid,text,text,text,text,text,text,text,text,timestamptz,jsonb
) FROM service_role;
REVOKE ALL ON FUNCTION public.guard_buyer_candidate_review_events_append_only()
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_approver,empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.propose_buyer_candidate_review(uuid,uuid,text,text,text,text,numeric,numeric,jsonb,text)
FROM PUBLIC,anon,authenticated,empire_outbound_approver,empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.review_buyer_candidate(uuid,text,text,text)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_sender,empire_reply_ingest;
REVOKE ALL ON FUNCTION public.propose_reviewed_outbound_intent(uuid,text,text,text,text,text,timestamptz,jsonb)
FROM PUBLIC,anon,authenticated,empire_outbound_approver,empire_outbound_sender,empire_reply_ingest;
GRANT EXECUTE ON FUNCTION public.propose_buyer_candidate_review(
    uuid,uuid,text,text,text,text,numeric,numeric,jsonb,text
) TO service_role;
GRANT EXECUTE ON FUNCTION public.review_buyer_candidate(uuid,text,text,text)
TO empire_outbound_approver;
GRANT EXECUTE ON FUNCTION public.propose_reviewed_outbound_intent(
    uuid,text,text,text,text,text,timestamptz,jsonb
) TO service_role;

COMMENT ON TABLE public.buyer_candidate_reviews IS
'Human-reviewed bridge between buyer intelligence and outbound intent. Candidate approval is required before service_role may propose outreach.';
COMMENT ON FUNCTION public.propose_reviewed_outbound_intent(uuid,text,text,text,text,text,timestamptz,jsonb) IS
'Creates a pending outbound intent only from a fresh human-approved buyer candidate review.';
COMMIT;
