-- Phase 3E: bind inbound replies to the exact intended recipient.
-- A valid reply alias alone is not sufficient authority to write a reply.
BEGIN;

CREATE OR REPLACE FUNCTION public.ingest_outbound_reply(
    p_intent_id uuid,
    p_provider_message_id text,
    p_from_contact text,
    p_subject text,
    p_body_text text,
    p_received_at timestamptz,
    p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE
    r public.outbound_intents%ROWTYPE;
    x public.outbound_replies%ROWTYPE;
    v_from text := lower(trim(COALESCE(p_from_contact,'')));
BEGIN
    SELECT * INTO r
      FROM public.outbound_intents
     WHERE id=p_intent_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;
    IF r.status NOT IN ('sent','delivered','replied') THEN
        RAISE EXCEPTION 'reply requires a sent intent';
    END IF;
    IF v_from='' OR v_from<>r.normalized_recipient THEN
        RAISE EXCEPTION 'reply sender does not match intended recipient';
    END IF;

    INSERT INTO public.outbound_replies(
        intent_id,provider_message_id,from_contact,normalized_from_contact,
        subject,body_text,received_at,metadata
    )
    VALUES(
        r.id,p_provider_message_id,p_from_contact,v_from,
        p_subject,p_body_text,p_received_at,COALESCE(p_metadata,'{}')
    )
    ON CONFLICT(intent_id,provider_message_id) DO NOTHING
    RETURNING * INTO x;

    IF NOT FOUND THEN
        SELECT * INTO x
          FROM public.outbound_replies
         WHERE intent_id=r.id AND provider_message_id=p_provider_message_id;
    END IF;
    UPDATE public.outbound_intents
       SET status='replied',updated_at=clock_timestamp()
     WHERE id=r.id;

    INSERT INTO public.outbound_events(
        intent_id,event_type,actor,provider_message_id,payload
    ) VALUES(
        r.id,'reply_received','reply_ingest',p_provider_message_id,
        jsonb_build_object('reply_id',x.id,'sender_bound',true)
    );

    RETURN jsonb_build_object(
        'decision','recorded',
        'reply_id',x.id,
        'intent_id',r.id,
        'classification',x.classification,
        'sender_bound',true,
        'actual_revenue',false
    );
END;
$$;

REVOKE ALL ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
) FROM PUBLIC,anon,authenticated,service_role,
       empire_outbound_approver,empire_outbound_sender;
GRANT EXECUTE ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
) TO empire_reply_ingest;

COMMIT;
