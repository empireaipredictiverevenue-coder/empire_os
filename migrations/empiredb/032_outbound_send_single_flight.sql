-- EmpireOS outbound single-flight hardening.
-- Prevents two workers from claiming the same approved outbound intent.
-- No provider authority is granted here.

ALTER TABLE public.outbound_intents
DROP CONSTRAINT outbound_intents_status_check;

ALTER TABLE public.outbound_intents
ADD CONSTRAINT outbound_intents_status_check
CHECK (
    status = ANY (
        ARRAY[
            'draft',
            'pending_approval',
            'approved',
            'sending',
            'reconciliation_required',
            'rejected',
            'sent',
            'delivered',
            'replied',
            'suppressed',
            'failed',
            'cancelled'
        ]::text[]
    )
);

CREATE OR REPLACE FUNCTION public.claim_outbound_send(
    p_intent_id uuid,
    p_actor text
)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path TO ''
AS $function$
DECLARE
    r public.outbound_intents%ROWTYPE;
BEGIN
    SELECT *
    INTO r
    FROM public.outbound_intents
    WHERE id = p_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF r.status <> 'approved'
       OR r.expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'approved unexpired outbound intent required';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_suppressions
        WHERE normalized_contact = r.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    UPDATE public.outbound_intents
    SET
        status = 'sending',
        updated_at = clock_timestamp()
    WHERE id = r.id
      AND status = 'approved'
    RETURNING *
    INTO r;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent already claimed';
    END IF;

    INSERT INTO public.outbound_events(
        intent_id,
        event_type,
        actor,
        payload
    )
    VALUES (
        r.id,
        'send_attempt',
        trim(p_actor),
        jsonb_build_object(
            'channel', r.channel,
            'state', 'sending',
            'single_flight', true
        )
    );

    RETURN jsonb_build_object(
        'decision', 'authorized_send',
        'intent_id', r.id,
        'channel', r.channel,
        'recipient', r.recipient,
        'subject', r.subject,
        'body_text', r.body_text,
        'body_html', r.body_html,
        'actual_revenue', false
    );
END;
$function$;


CREATE OR REPLACE FUNCTION public.record_outbound_delivery(
    p_intent_id uuid,
    p_event_type text,
    p_actor text,
    p_provider_message_id text,
    p_payload jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path TO ''
AS $function$
DECLARE
    r public.outbound_intents%ROWTYPE;
    v_type text := lower(trim(p_event_type));
BEGIN
    IF v_type NOT IN (
        'sent',
        'delivered',
        'failed',
        'reconciliation_required'
    ) THEN
        RAISE EXCEPTION 'unsupported delivery event';
    END IF;

    SELECT *
    INTO r
    FROM public.outbound_intents
    WHERE id = p_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF v_type = 'sent'
       AND r.status NOT IN ('sending', 'sent') THEN
        RAISE EXCEPTION 'claimed outbound intent required';
    END IF;

    IF v_type = 'delivered'
       AND r.status NOT IN ('sent', 'delivered') THEN
        RAISE EXCEPTION 'sent intent required';
    END IF;

    IF v_type = 'reconciliation_required'
       AND r.status NOT IN ('sending', 'reconciliation_required') THEN
        RAISE EXCEPTION 'sending intent required';
    END IF;

    UPDATE public.outbound_intents
    SET
        status = CASE
            WHEN v_type = 'failed' THEN 'failed'
            ELSE v_type
        END,
        updated_at = clock_timestamp()
    WHERE id = r.id
    RETURNING *
    INTO r;

    INSERT INTO public.outbound_events(
        intent_id,
        event_type,
        actor,
        provider_message_id,
        payload
    )
    VALUES (
        r.id,
        v_type,
        trim(p_actor),
        NULLIF(trim(p_provider_message_id), ''),
        COALESCE(p_payload, '{}'::jsonb)
    );

    RETURN jsonb_build_object(
        'decision', 'recorded',
        'intent_id', r.id,
        'status', r.status,
        'actual_revenue', false
    );
END;
$function$;
