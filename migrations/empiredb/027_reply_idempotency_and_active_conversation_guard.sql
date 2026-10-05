-- EmpireDB reply idempotency + active-conversation send guard.
-- Canonical EmpireDB only. No Supabase dependency.
-- This migration changes no execution authority and performs no sends.
--
-- Guarantees:
-- 1. A provider reply id is recorded once per intent.
-- 2. Duplicate reply delivery does not append duplicate reply_received events.
-- 3. Repeating the same classification is a no-op.
-- 4. Cold/follow-up email cannot be claimed after that recipient has replied;
--    only the governed closer_reply lane may continue the conversation.

BEGIN;

SET LOCAL ROLE empiredb_migrator;

DO $guard$
BEGIN
    IF current_database() <> 'empiredb' THEN
        RAISE EXCEPTION 'migration 027 must run against empiredb';
    END IF;

    IF to_regclass('public.outbound_intents') IS NULL
       OR to_regclass('public.outbound_replies') IS NULL
       OR to_regclass('public.outbound_events') IS NULL
       OR to_regclass('public.outbound_suppressions') IS NULL THEN
        RAISE EXCEPTION 'required governed outbound relations missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname='empire_reply_ingest'
          AND NOT rolcanlogin
          AND NOT rolsuper
    ) THEN
        RAISE EXCEPTION 'empire_reply_ingest capability role missing or unsafe';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname='empire_outbound_sender'
          AND NOT rolcanlogin
          AND NOT rolsuper
    ) THEN
        RAISE EXCEPTION 'empire_outbound_sender capability role missing or unsafe';
    END IF;
END
$guard$;

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
SECURITY INVOKER
SET search_path=''
AS $reply_ingest$
DECLARE
    r public.outbound_intents%ROWTYPE;
    x public.outbound_replies%ROWTYPE;
    v_from text := lower(trim(COALESCE(p_from_contact,'')));
    v_message text := trim(COALESCE(p_provider_message_id,''));
BEGIN
    IF v_message='' THEN
        RAISE EXCEPTION 'provider message id required';
    END IF;

    SELECT *
    INTO r
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
        intent_id,
        provider_message_id,
        from_contact,
        normalized_from_contact,
        subject,
        body_text,
        received_at,
        metadata
    )
    VALUES(
        r.id,
        v_message,
        p_from_contact,
        v_from,
        p_subject,
        p_body_text,
        p_received_at,
        COALESCE(p_metadata,'{}'::jsonb)
    )
    ON CONFLICT(intent_id,provider_message_id) DO NOTHING
    RETURNING * INTO x;

    IF NOT FOUND THEN
        SELECT *
        INTO x
        FROM public.outbound_replies
        WHERE intent_id=r.id
          AND provider_message_id=v_message;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'reply idempotency lookup failed';
        END IF;

        RETURN jsonb_build_object(
            'decision','existing_reply',
            'reply_id',x.id,
            'intent_id',r.id,
            'classification',x.classification,
            'sender_bound',true,
            'actual_revenue',false
        );
    END IF;

    UPDATE public.outbound_intents
    SET status='replied',
        updated_at=clock_timestamp()
    WHERE id=r.id;

    INSERT INTO public.outbound_events(
        intent_id,
        event_type,
        actor,
        provider_message_id,
        payload
    )
    VALUES(
        r.id,
        'reply_received',
        'reply_ingest',
        v_message,
        jsonb_build_object(
            'reply_id',x.id,
            'sender_bound',true,
            'idempotent',true
        )
    );

    RETURN jsonb_build_object(
        'decision','recorded',
        'reply_id',x.id,
        'intent_id',r.id,
        'classification',x.classification,
        'sender_bound',true,
        'actual_revenue',false
    );
END
$reply_ingest$;

CREATE OR REPLACE FUNCTION public.classify_outbound_reply(
    p_reply_id uuid,
    p_classification text,
    p_confidence numeric,
    p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $reply_classify$
DECLARE
    x public.outbound_replies%ROWTYPE;
    r public.outbound_intents%ROWTYPE;
    v text := lower(trim(COALESCE(p_classification,'')));
BEGIN
    IF v NOT IN (
        'positive','negative','question','objection',
        'later','unsubscribe','bounce','other'
    ) THEN
        RAISE EXCEPTION 'unsupported reply classification';
    END IF;

    IF p_confidence IS NULL OR p_confidence<0 OR p_confidence>1 THEN
        RAISE EXCEPTION 'invalid reply confidence';
    END IF;

    SELECT *
    INTO x
    FROM public.outbound_replies
    WHERE id=p_reply_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply not found';
    END IF;

    SELECT *
    INTO r
    FROM public.outbound_intents
    WHERE id=x.intent_id
    FOR UPDATE;

    IF x.classification=v
       AND x.confidence IS NOT DISTINCT FROM p_confidence THEN
        RETURN jsonb_build_object(
            'decision','existing_classification',
            'reply_id',x.id,
            'classification',x.classification,
            'suppressed',(x.classification IN ('unsubscribe','bounce')),
            'actual_revenue',false
        );
    END IF;

    UPDATE public.outbound_replies
    SET classification=v,
        confidence=p_confidence,
        classified_at=clock_timestamp()
    WHERE id=x.id
    RETURNING * INTO x;

    INSERT INTO public.outbound_events(
        intent_id,
        event_type,
        actor,
        provider_message_id,
        payload
    )
    VALUES(
        r.id,
        'reply_classified',
        trim(p_actor),
        x.provider_message_id,
        jsonb_build_object(
            'reply_id',x.id,
            'classification',v,
            'confidence',p_confidence
        )
    );

    IF v IN ('unsubscribe','bounce') THEN
        INSERT INTO public.outbound_suppressions(
            normalized_contact,
            contact_type,
            reason,
            source
        )
        VALUES(
            r.normalized_recipient,
            CASE WHEN r.channel='email' THEN 'email' ELSE 'phone' END,
            v,
            'reply'
        )
        ON CONFLICT(normalized_contact) DO NOTHING;

        UPDATE public.outbound_intents
        SET status='suppressed',
            updated_at=clock_timestamp()
        WHERE id=r.id;

        IF NOT EXISTS (
            SELECT 1
            FROM public.outbound_events e
            WHERE e.intent_id=r.id
              AND e.event_type='suppressed'
              AND e.provider_message_id IS NOT DISTINCT FROM x.provider_message_id
        ) THEN
            INSERT INTO public.outbound_events(
                intent_id,
                event_type,
                actor,
                provider_message_id,
                payload
            )
            VALUES(
                r.id,
                'suppressed',
                trim(p_actor),
                x.provider_message_id,
                jsonb_build_object('reason',v,'reply_id',x.id)
            );
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'decision','classified',
        'reply_id',x.id,
        'classification',v,
        'suppressed',(v IN ('unsubscribe','bounce')),
        'actual_revenue',false
    );
END
$reply_classify$;

CREATE OR REPLACE FUNCTION public.claim_outbound_send(
    p_intent_id uuid,
    p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $claim_send$
DECLARE
    r public.outbound_intents%ROWTYPE;
    sequence_kind text;
BEGIN
    SELECT *
    INTO r
    FROM public.outbound_intents
    WHERE id=p_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF r.status<>'approved'
       OR r.expires_at<=clock_timestamp() THEN
        RAISE EXCEPTION 'approved unexpired outbound intent required';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_suppressions
        WHERE normalized_contact=r.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    sequence_kind := lower(trim(COALESCE(
        r.metadata->>'sequence_kind',
        'first_touch'
    )));

    IF r.channel='email'
       AND sequence_kind<>'closer_reply'
       AND EXISTS (
           SELECT 1
           FROM public.outbound_intents prior
           WHERE prior.id<>r.id
             AND prior.normalized_recipient=r.normalized_recipient
             AND prior.status='replied'
       ) THEN
        RAISE EXCEPTION
            'active conversation requires governed closer reply lane';
    END IF;

    INSERT INTO public.outbound_events(
        intent_id,
        event_type,
        actor,
        payload
    )
    VALUES(
        r.id,
        'send_attempt',
        trim(p_actor),
        jsonb_build_object(
            'channel',r.channel,
            'sequence_kind',sequence_kind,
            'active_conversation_guard',true
        )
    );

    RETURN jsonb_build_object(
        'decision','authorized_send',
        'intent_id',r.id,
        'channel',r.channel,
        'recipient',r.recipient,
        'subject',r.subject,
        'body_text',r.body_text,
        'body_html',r.body_html,
        'actual_revenue',false
    );
END
$claim_send$;

-- Preserve least-privilege function authority explicitly.
REVOKE ALL ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
)
FROM PUBLIC,empiredb_app,empire_outbound_approver,
     empire_outbound_sender,empire_reply_ingest;

REVOKE ALL ON FUNCTION public.classify_outbound_reply(
    uuid,text,numeric,text
)
FROM PUBLIC,empiredb_app,empire_outbound_approver,
     empire_outbound_sender,empire_reply_ingest;

REVOKE ALL ON FUNCTION public.claim_outbound_send(uuid,text)
FROM PUBLIC,empiredb_app,empire_outbound_approver,
     empire_outbound_sender,empire_reply_ingest;

GRANT EXECUTE ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
)
TO empire_reply_ingest;

GRANT EXECUTE ON FUNCTION public.classify_outbound_reply(
    uuid,text,numeric,text
)
TO empire_reply_ingest;

GRANT EXECUTE ON FUNCTION public.claim_outbound_send(uuid,text)
TO empire_outbound_sender;

COMMENT ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
) IS
'Idempotent canonical EmpireDB reply ingest. Duplicate provider-message delivery returns existing_reply and appends no duplicate reply_received event.';

COMMENT ON FUNCTION public.claim_outbound_send(uuid,text) IS
'Final outbound claim gate; blocks non-closer email sends once the recipient has entered a replied conversation.';

COMMIT;
