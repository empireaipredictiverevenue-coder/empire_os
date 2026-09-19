-- Phase 3E: enforce send-readiness after buyer review approval.
-- Forward-only. Prevents review-only candidates from becoming outbound intents.
BEGIN;

CREATE OR REPLACE FUNCTION public.propose_reviewed_outbound_intent(
    p_review_id uuid, p_subject text, p_body_text text, p_body_html text,
    p_idempotency_key text, p_proposed_by text, p_expires_at timestamptz,
    p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r public.buyer_candidate_reviews%ROWTYPE; result jsonb; merged jsonb;
BEGIN
    SELECT * INTO r FROM public.buyer_candidate_reviews WHERE id=p_review_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer candidate review not found'; END IF;
    IF r.status<>'approved' THEN RAISE EXCEPTION 'approved buyer candidate review required'; END IF;
    IF r.reviewed_at IS NULL OR r.reviewed_at < clock_timestamp()-interval '7 days' THEN
      RAISE EXCEPTION 'fresh buyer candidate approval required';
    END IF;
    IF COALESCE(lower(r.evidence->>'outreach_ready'),'false') <> 'true' THEN
      RAISE EXCEPTION 'outreach-ready evidence required';
    END IF;
    merged := COALESCE(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'buyer_candidate_review_id',r.id,'decision_score',r.decision_score,
      'company_score',r.company_score,'candidate_evidence',r.evidence
    );    result := public.propose_outbound_intent(
      r.entity_id,r.prospect_id,NULL,NULL,'email',r.contact_email,p_subject,p_body_text,
      p_body_html,r.offer_key,p_idempotency_key,p_proposed_by,p_expires_at,merged
    );
    INSERT INTO public.buyer_candidate_review_events(review_id,event_type,actor,payload)
    VALUES(r.id,'outbound_proposed',trim(p_proposed_by),jsonb_build_object('intent_id',result->>'intent_id'));
    RETURN result || jsonb_build_object('buyer_candidate_review_id',r.id);
END;
$$;

REVOKE ALL ON FUNCTION public.propose_reviewed_outbound_intent(uuid,text,text,text,text,text,timestamptz,jsonb)
FROM PUBLIC,anon,authenticated,empire_outbound_approver,empire_outbound_sender,empire_reply_ingest;
GRANT EXECUTE ON FUNCTION public.propose_reviewed_outbound_intent(
    uuid,text,text,text,text,text,timestamptz,jsonb
) TO service_role;

COMMENT ON FUNCTION public.propose_reviewed_outbound_intent(uuid,text,text,text,text,text,timestamptz,jsonb) IS
'Creates a pending outbound intent only from a fresh human-approved buyer candidate review whose evidence is explicitly outreach-ready.';
COMMIT;
