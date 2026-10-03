BEGIN;

-- Migration 034
--
-- Corrects the 033 event-idempotency implementation without widening
-- empire_reply_ingest authority.
--
-- empire_conversation_events remains append-only for this role:
-- SELECT + INSERT only, never UPDATE/DELETE.

CREATE OR REPLACE FUNCTION public.ingest_outbound_reply(
    p_intent_id uuid,
    p_provider_message_id text,
    p_from_contact text,
    p_subject text,
    p_body_text text,
    p_received_at timestamptz,
    p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO ''
AS $function$
DECLARE
    r public.outbound_intents%ROWTYPE;
    x public.outbound_replies%ROWTYPE;
    c public.empire_conversations%ROWTYPE;
    e public.empire_conversation_events%ROWTYPE;

    v_from text :=
        lower(trim(COALESCE(p_from_contact,'')));

    v_provider text :=
        lower(trim(COALESCE(p_metadata->>'provider','')));

    v_hash text :=
        lower(trim(COALESCE(
            p_metadata->>'payload_sha256',
            ''
        )));

    v_existing_hash text;
    v_external text;
    v_event_status text := NULL;
BEGIN
    IF p_intent_id IS NULL THEN
        RAISE EXCEPTION 'outbound intent required';
    END IF;

    SELECT *
      INTO r
      FROM public.outbound_intents
     WHERE id = p_intent_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    -- A suppressed intent may only receive an idempotent replay of
    -- a reply already recorded before suppression.
    IF r.status = 'suppressed' THEN
        SELECT *
          INTO x
          FROM public.outbound_replies
         WHERE intent_id = r.id
           AND provider_message_id = p_provider_message_id
         FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION
                'suppressed intent only accepts existing reply replay';
        END IF;

    ELSIF r.status NOT IN (
        'sent',
        'delivered',
        'replied'
    ) THEN
        RAISE EXCEPTION 'reply requires a sent intent';
    END IF;

    -- Resend canonicalization requires exact signed-body evidence.
    IF v_provider = 'resend' THEN
        IF r.channel <> 'email' THEN
            RAISE EXCEPTION
                'resend reply requires email intent';
        END IF;

        IF trim(COALESCE(
            p_provider_message_id,
            ''
        )) = '' THEN
            RAISE EXCEPTION
                'provider message id required';
        END IF;

        IF p_received_at IS NULL THEN
            RAISE EXCEPTION
                'received_at required';
        END IF;

        IF v_hash = ''
           OR v_hash !~ '^[0-9a-f]{64}$' THEN
            RAISE EXCEPTION
                'valid payload_sha256 evidence required';
        END IF;
    END IF;

    -- Existing suppressed replay may already have loaded x.
    IF x.id IS NULL THEN
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
            p_provider_message_id,
            p_from_contact,
            v_from,
            p_subject,
            p_body_text,
            p_received_at,
            COALESCE(p_metadata,'{}'::jsonb)
        )
        ON CONFLICT(intent_id, provider_message_id)
        DO NOTHING
        RETURNING *
        INTO x;

        IF NOT FOUND THEN
            SELECT *
              INTO x
              FROM public.outbound_replies
             WHERE intent_id = r.id
               AND provider_message_id =
                   p_provider_message_id
             FOR UPDATE;
        END IF;
    END IF;

    IF x.id IS NULL THEN
        RAISE EXCEPTION
            'reply canonicalization failed';
    END IF;

    -- Provider replay conflict detection.
    IF v_provider = 'resend' THEN
        v_existing_hash := lower(trim(COALESCE(
            x.metadata->>'payload_sha256',
            ''
        )));

        IF v_existing_hash <> ''
           AND v_existing_hash <> v_hash THEN
            RAISE EXCEPTION
                'provider event payload mismatch';
        END IF;

        -- Historical rows may have been written before hashes were
        -- persisted. A genuine signed replay may safely add the hash
        -- observed NOW; no evidence is fabricated.
        IF v_existing_hash = '' THEN
            UPDATE public.outbound_replies
               SET metadata =
                   COALESCE(metadata,'{}'::jsonb)
                   || COALESCE(p_metadata,'{}'::jsonb)
             WHERE id = x.id
             RETURNING *
             INTO x;
        END IF;
    END IF;

    -- Never undo an opt-out/bounce suppression during replay.
    IF r.status <> 'suppressed' THEN
        UPDATE public.outbound_intents
           SET status = 'replied',
               updated_at = clock_timestamp()
         WHERE id = r.id
         RETURNING *
         INTO r;
    END IF;

    -- Legacy event becomes replay-safe under the intent row lock.
    IF NOT EXISTS (
        SELECT 1
        FROM public.outbound_events oe
        WHERE oe.intent_id = r.id
          AND oe.event_type = 'reply_received'
          AND oe.provider_message_id =
              p_provider_message_id
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
            'reply_received',
            'reply_ingest',
            p_provider_message_id,
            jsonb_build_object(
                'reply_id', x.id
            )
        );
    END IF;

    -- --------------------------------------------------------
    -- Canonical Conversation OS write for verified Resend email.
    -- --------------------------------------------------------

    IF v_provider = 'resend' THEN
        v_external :=
            'resend:outbound-intent:' || r.id::text;

        SELECT *
          INTO c
          FROM public.empire_conversations
         WHERE channel = 'email'
           AND outbound_intent_id = r.id
         FOR UPDATE;

        IF NOT FOUND THEN
            INSERT INTO public.empire_conversations(
                channel,
                state,
                prospect_id,
                entity_id,
                buyer_id,
                opportunity_id,
                outbound_intent_id,
                external_conversation_id,
                provider
            )
            VALUES(
                'email',
                'engaged',
                r.prospect_id,
                r.entity_id,
                r.buyer_id,
                r.opportunity_id,
                r.id,
                v_external,
                'email'
            )
            RETURNING *
            INTO c;
        ELSE
            IF c.provider IS NOT NULL
               AND c.provider <> 'email' THEN
                RAISE EXCEPTION
                    'canonical conversation provider mismatch';
            END IF;

            IF c.external_conversation_id IS NOT NULL
               AND c.external_conversation_id <>
                   v_external THEN
                RAISE EXCEPTION
                    'canonical conversation external id mismatch';
            END IF;

            UPDATE public.empire_conversations
               SET provider =
                       COALESCE(provider,'email'),
                   external_conversation_id =
                       COALESCE(
                           external_conversation_id,
                           v_external
                       ),
                   state =
                       CASE
                           WHEN state = 'open'
                               THEN 'engaged'
                           ELSE state
                       END,
                   updated_at = clock_timestamp()
             WHERE id = c.id
             RETURNING *
             INTO c;
        END IF;

        -- Conversation events are append-only. Do not acquire a row lock:
        -- empire_reply_ingest intentionally has no UPDATE authority here.
        SELECT *
          INTO e
          FROM public.empire_conversation_events
         WHERE conversation_id = c.id
           AND provider_event_id =
               p_provider_message_id;

        IF FOUND THEN
            v_existing_hash := lower(trim(COALESCE(
                e.evidence->>'payload_sha256',
                ''
            )));

            IF v_existing_hash = ''
               OR v_existing_hash <> v_hash THEN
                RAISE EXCEPTION
                    'provider event payload mismatch';
            END IF;

            v_event_status := 'existing';

        ELSE
            INSERT INTO public.empire_conversation_events(
                conversation_id,
                event_type,
                direction,
                actor,
                body_text,
                provider_event_id,
                evidence,
                occurred_at
            )
            VALUES(
                c.id,
                'email.received',
                'inbound',
                NULLIF(v_from,''),
                p_body_text,
                p_provider_message_id,
                COALESCE(p_metadata,'{}'::jsonb)
                || jsonb_build_object(
                    'provider','resend',
                    'outbound_intent_id',r.id,
                    'reply_id',x.id,
                    'subject',p_subject,
                    'from_contact',p_from_contact,
                    'untrusted_content',true,
                    'executable',false
                ),
                p_received_at
            )
            ON CONFLICT (
                conversation_id,
                provider_event_id
            )
            WHERE provider_event_id IS NOT NULL
            DO NOTHING
            RETURNING *
            INTO e;

            IF FOUND THEN
                v_event_status := 'recorded';

            ELSE
                -- Concurrent replay won the unique insert. Re-read
                -- append-only evidence and require the same payload hash.
                SELECT *
                  INTO e
                  FROM public.empire_conversation_events
                 WHERE conversation_id = c.id
                   AND provider_event_id =
                       p_provider_message_id;

                IF NOT FOUND THEN
                    RAISE EXCEPTION
                        'canonical provider event unavailable after conflict';
                END IF;

                v_existing_hash := lower(trim(COALESCE(
                    e.evidence->>'payload_sha256',
                    ''
                )));

                IF v_existing_hash = ''
                   OR v_existing_hash <> v_hash THEN
                    RAISE EXCEPTION
                        'provider event payload mismatch';
                END IF;

                v_event_status := 'existing';
            END IF;
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'decision','recorded',
        'reply_id',x.id,
        'intent_id',r.id,
        'classification',x.classification,
        'conversation_id',
            CASE
                WHEN c.id IS NULL THEN NULL
                ELSE c.id
            END,
        'conversation_event_status',v_event_status,
        'actual_revenue',false
    );
END;
$function$;

COMMENT ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
)
IS
'Migration 034: atomic Resend reply canonicalization with append-only, race-safe provider-event idempotency. No event UPDATE authority; actual_revenue=false.';

COMMIT;
