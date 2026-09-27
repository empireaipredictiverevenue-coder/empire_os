-- Phase 3E: allow a human approver to cancel a stale pending outbound proposal.
-- Forward-only. Does not send, approve, or mutate message content.
BEGIN;

CREATE FUNCTION public.cancel_outbound_intent(
    p_intent_id uuid,
    p_cancelled_by text,
    p_reason text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE r public.outbound_intents%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.outbound_intents WHERE id=p_intent_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'outbound intent not found'; END IF;
    IF r.status='cancelled' THEN
        RETURN jsonb_build_object('decision','existing_cancellation','intent_id',r.id,'status',r.status,'actual_revenue',false);
    END IF;
    IF r.status<>'pending_approval' THEN
        RAISE EXCEPTION 'pending outbound intent required for cancellation';
    END IF;
    IF length(trim(COALESCE(p_cancelled_by,'')))<1 OR length(trim(COALESCE(p_reason,'')))<1 THEN
        RAISE EXCEPTION 'cancellation actor and reason required';
    END IF;
    UPDATE public.outbound_intents
       SET status='cancelled', updated_at=clock_timestamp()
     WHERE id=r.id RETURNING * INTO r;
    INSERT INTO public.outbound_events(intent_id,event_type,actor,payload)
    VALUES(r.id,'cancelled',trim(p_cancelled_by),jsonb_build_object('reason',trim(p_reason)));
    RETURN jsonb_build_object('decision','cancelled','intent_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;

REVOKE ALL ON FUNCTION public.cancel_outbound_intent(uuid,text,text)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_sender,empire_reply_ingest;
GRANT EXECUTE ON FUNCTION public.cancel_outbound_intent(uuid,text,text)
TO empire_outbound_approver;
COMMENT ON FUNCTION public.cancel_outbound_intent(uuid,text,text) IS
'Human-governed cancellation for a pending outbound proposal. Cancellation never sends or approves an intent.';
COMMIT;
