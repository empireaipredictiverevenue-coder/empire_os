-- Correct provider-event state ordering after migration 024.
-- HELD until explicit founder database activation approval.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $provider_event_ordering_guard$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'EmpireDB required';
  END IF;

  IF to_regprocedure(
    'public.record_outbound_provider_event(uuid,text,text,text,boolean,jsonb)'
  ) IS NULL THEN
    RAISE EXCEPTION 'provider-event ingest function required';
  END IF;
END;
$provider_event_ordering_guard$;

CREATE OR REPLACE FUNCTION public.record_outbound_provider_event(
    p_intent_id uuid,
    p_event_type text,
    p_provider_message_id text,
    p_recipient text,
    p_suppress boolean,
    p_payload jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $provider_event$
DECLARE
    r public.outbound_intents%ROWTYPE;
    v_type text := lower(trim(COALESCE(p_event_type,'')));
    v_recipient text := lower(trim(COALESCE(p_recipient,'')));
    v_message text := trim(COALESCE(p_provider_message_id,''));
    v_suppress boolean := COALESCE(p_suppress,false);
BEGIN
    IF v_type NOT IN (
        'delivered',
        'delivery_delayed',
        'bounced',
        'complained',
        'opened',
        'clicked',
        'failed',
        'suppressed'
    ) THEN
        RAISE EXCEPTION 'unsupported provider event';
    END IF;

    IF v_message='' OR v_recipient='' THEN
        RAISE EXCEPTION 'provider message id and recipient required';
    END IF;

    SELECT *
    INTO r
    FROM public.outbound_intents
    WHERE id=p_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF v_recipient<>r.normalized_recipient THEN
        RAISE EXCEPTION 'provider event recipient mismatch';
    END IF;

    IF r.status NOT IN (
        'sent',
        'delivered',
        'replied',
        'failed',
        'suppressed'
    ) THEN
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
            normalized_contact,
            contact_type,
            reason,
            source
        )
        VALUES(
            r.normalized_recipient,
            'email',
            v_type,
            'resend_webhook'
        )
        ON CONFLICT(normalized_contact) DO NOTHING;

        UPDATE public.outbound_intents
        SET status='suppressed',
            updated_at=clock_timestamp()
        WHERE id=r.id
        RETURNING * INTO r;

    ELSIF v_type='delivered'
          AND r.status='sent' THEN

        UPDATE public.outbound_intents
        SET status='delivered',
            updated_at=clock_timestamp()
        WHERE id=r.id
        RETURNING * INTO r;

    ELSIF v_type IN ('bounced','failed')
          AND r.status IN ('sent','delivered') THEN

        UPDATE public.outbound_intents
        SET status='failed',
            updated_at=clock_timestamp()
        WHERE id=r.id
        RETURNING * INTO r;
    END IF;

    INSERT INTO public.outbound_events(
        intent_id,
        event_type,
        actor,
        provider_message_id,
        payload
    )
    VALUES(
        r.id,
        v_type,
        'resend_webhook',
        v_message,
        COALESCE(p_payload,'{}'::jsonb)
        || jsonb_build_object('suppress',v_suppress)
    );

    RETURN jsonb_build_object(
        'decision','recorded_provider_event',
        'intent_id',r.id,
        'status',r.status,
        'event_type',v_type,
        'suppressed',v_suppress,
        'actual_revenue',false
    );
END
$provider_event$;


UPDATE public.outbound_intents i
SET status='failed',
    updated_at=clock_timestamp()
WHERE i.status='delivered'
  AND EXISTS (
    SELECT 1
    FROM public.outbound_events terminal
    WHERE terminal.intent_id=i.id
      AND terminal.event_type IN ('bounced','failed')
      AND terminal.occurred_at > COALESCE(
        (
          SELECT max(delivered.occurred_at)
          FROM public.outbound_events delivered
          WHERE delivered.intent_id=i.id
            AND delivered.event_type='delivered'
        ),
        '-infinity'::timestamptz
      )
  );

COMMIT;
