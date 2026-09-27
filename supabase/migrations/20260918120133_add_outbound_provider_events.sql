-- Phase 3E/3F bridge: ingest verified Resend delivery lifecycle events
-- through the inbound-only runtime role. This path can never claim a send.
BEGIN;

ALTER TABLE public.outbound_events
DROP CONSTRAINT IF EXISTS outbound_events_event_type_check;

ALTER TABLE public.outbound_events
ADD CONSTRAINT outbound_events_event_type_check CHECK (event_type IN (
    'proposed','approved','rejected','send_attempt','sent','delivered','failed',
    'reply_received','reply_classified','suppressed','cancelled',
    'delivery_delayed','bounced','complained','opened','clicked'
));

CREATE FUNCTION public.record_outbound_provider_event(
    p_intent_id uuid,
    p_event_type text,
    p_provider_message_id text,
    p_recipient text,
    p_suppress boolean,
    p_payload jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE
    r public.outbound_intents%ROWTYPE;
    v_type text := lower(trim(COALESCE(p_event_type,'')));
    v_recipient text := lower(trim(COALESCE(p_recipient,'')));
    v_message text := trim(COALESCE(p_provider_message_id,''));
    v_suppress boolean := COALESCE(p_suppress,false);
BEGIN
    IF v_type NOT IN (
        'delivered','delivery_delayed','bounced','complained',
        'opened','clicked','failed','suppressed'
    ) THEN
        RAISE EXCEPTION 'unsupported provider event';
    END IF;
    IF v_message='' OR v_recipient='' THEN
        RAISE EXCEPTION 'provider message id and recipient required';
    END IF;

    SELECT * INTO r
      FROM public.outbound_intents
     WHERE id=p_intent_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;
    IF v_recipient<>r.normalized_recipient THEN
        RAISE EXCEPTION 'provider event recipient mismatch';
    END IF;
    IF r.status NOT IN ('sent','delivered','replied','failed','suppressed') THEN
        RAISE EXCEPTION 'provider event requires a sent intent';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.outbound_events e
         WHERE e.intent_id=r.id
           AND e.event_type=v_type
           AND e.provider_message_id=v_message
    ) THEN
        RETURN jsonb_build_object(
            'decision','existing_provider_event',
            'intent_id',r.id,
            'status',r.status,
            'event_type',v_type,
            'actual_revenue',false
        );
    END IF;
    IF v_type IN ('complained','suppressed') THEN
        v_suppress := true;
    ELSIF v_type<>'bounced' THEN
        v_suppress := false;
    END IF;

    IF v_suppress THEN
        INSERT INTO public.outbound_suppressions(
            normalized_contact,contact_type,reason,source
        ) VALUES(
            r.normalized_recipient,'email',v_type,'resend_webhook'
        )
        ON CONFLICT(normalized_contact) DO NOTHING;
        UPDATE public.outbound_intents
           SET status='suppressed',updated_at=clock_timestamp()
         WHERE id=r.id
        RETURNING * INTO r;
    ELSIF v_type='delivered' AND r.status IN ('sent','failed') THEN
        UPDATE public.outbound_intents
           SET status='delivered',updated_at=clock_timestamp()
         WHERE id=r.id
        RETURNING * INTO r;
    ELSIF v_type IN ('bounced','failed') AND r.status='sent' THEN
        UPDATE public.outbound_intents
           SET status='failed',updated_at=clock_timestamp()
         WHERE id=r.id
        RETURNING * INTO r;
    END IF;

    INSERT INTO public.outbound_events(
        intent_id,event_type,actor,provider_message_id,payload
    ) VALUES(
        r.id,v_type,'resend_webhook',v_message,
        COALESCE(p_payload,'{}'::jsonb) ||
        jsonb_build_object('suppress',v_suppress)
    );
    RETURN jsonb_build_object(
        'decision','recorded_provider_event',
        'intent_id',r.id,
        'status',r.status,
        'event_type',v_type,
        'suppressed',v_suppress,
        'actual_revenue',false
    );
END;
$$;

REVOKE ALL ON FUNCTION public.record_outbound_provider_event(
    uuid,text,text,text,boolean,jsonb
) FROM PUBLIC,anon,authenticated,service_role,
       empire_outbound_approver,empire_outbound_sender,empire_reply_ingest;

GRANT EXECUTE ON FUNCTION public.record_outbound_provider_event(
    uuid,text,text,text,boolean,jsonb
) TO empire_reply_ingest;

COMMENT ON FUNCTION public.record_outbound_provider_event(
    uuid,text,text,text,boolean,jsonb
) IS
'Verified provider lifecycle event ingest; cannot send or approve outbound.';

COMMIT;
