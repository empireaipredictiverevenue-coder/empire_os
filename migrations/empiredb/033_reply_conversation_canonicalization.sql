BEGIN;

-- ------------------------------------------------------------
-- Exactly one canonical email conversation per outbound intent.
-- ------------------------------------------------------------

CREATE UNIQUE INDEX
    uq_empire_email_conversation_outbound_intent
ON public.empire_conversations(outbound_intent_id)
WHERE channel = 'email'
  AND outbound_intent_id IS NOT NULL;

-- Provider event identity inside one canonical conversation.
-- This invariant predates migration 033 in some production databases.
-- Reuse it only when its existing definition is exactly compatible.
DO $index_guard$
DECLARE
    v_unique boolean;
    v_def text;
    v_predicate text;
BEGIN
    IF to_regclass(
        'public.uq_empire_conversation_provider_event'
    ) IS NULL THEN

        CREATE UNIQUE INDEX
            uq_empire_conversation_provider_event
        ON public.empire_conversation_events(
            conversation_id,
            provider_event_id
        )
        WHERE provider_event_id IS NOT NULL;

    ELSE
        SELECT
            i.indisunique,
            pg_get_indexdef(i.indexrelid),
            COALESCE(
                pg_get_expr(i.indpred,i.indrelid),
                ''
            )
        INTO
            v_unique,
            v_def,
            v_predicate
        FROM pg_index i
        JOIN pg_class idx
          ON idx.oid=i.indexrelid
        JOIN pg_class tbl
          ON tbl.oid=i.indrelid
        JOIN pg_namespace n
          ON n.oid=tbl.relnamespace
        WHERE n.nspname='public'
          AND tbl.relname='empire_conversation_events'
          AND idx.relname=
              'uq_empire_conversation_provider_event';

        IF NOT COALESCE(v_unique,false)
           OR v_def NOT ILIKE
              '%(conversation_id, provider_event_id)%'
           OR v_predicate NOT ILIKE
              '%provider_event_id IS NOT NULL%' THEN

            RAISE EXCEPTION
                'existing provider-event index contract mismatch';
        END IF;
    END IF;
END
$index_guard$;

-- ------------------------------------------------------------
-- Least-privilege reply-ingest authority.
-- Existing broad rights are cleared first.
-- ------------------------------------------------------------

REVOKE ALL
ON public.empire_conversations
FROM empire_reply_ingest;

REVOKE ALL
ON public.empire_conversation_events
FROM empire_reply_ingest;

GRANT SELECT, INSERT, UPDATE
ON public.empire_conversations
TO empire_reply_ingest;

GRANT SELECT, INSERT
ON public.empire_conversation_events
TO empire_reply_ingest;

ALTER TABLE public.empire_conversations
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.empire_conversation_events
ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS
    reply_ingest_email_conversation_select
ON public.empire_conversations;

DROP POLICY IF EXISTS
    reply_ingest_email_conversation_insert
ON public.empire_conversations;

DROP POLICY IF EXISTS
    reply_ingest_email_conversation_update
ON public.empire_conversations;

DROP POLICY IF EXISTS
    reply_ingest_email_event_select
ON public.empire_conversation_events;

DROP POLICY IF EXISTS
    reply_ingest_email_event_insert
ON public.empire_conversation_events;

CREATE POLICY reply_ingest_email_conversation_select
ON public.empire_conversations
FOR SELECT
TO empire_reply_ingest
USING (
    channel = 'email'
    AND outbound_intent_id IS NOT NULL
);

CREATE POLICY reply_ingest_email_conversation_insert
ON public.empire_conversations
FOR INSERT
TO empire_reply_ingest
WITH CHECK (
    channel = 'email'
    AND outbound_intent_id IS NOT NULL
    AND provider = 'email'
);

CREATE POLICY reply_ingest_email_conversation_update
ON public.empire_conversations
FOR UPDATE
TO empire_reply_ingest
USING (
    channel = 'email'
    AND outbound_intent_id IS NOT NULL
)
WITH CHECK (
    channel = 'email'
    AND outbound_intent_id IS NOT NULL
    AND provider = 'email'
);

CREATE POLICY reply_ingest_email_event_select
ON public.empire_conversation_events
FOR SELECT
TO empire_reply_ingest
USING (
    EXISTS (
        SELECT 1
        FROM public.empire_conversations c
        WHERE c.id = conversation_id
          AND c.channel = 'email'
          AND c.outbound_intent_id IS NOT NULL
    )
);

CREATE POLICY reply_ingest_email_event_insert
ON public.empire_conversation_events
FOR INSERT
TO empire_reply_ingest
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.empire_conversations c
        WHERE c.id = conversation_id
          AND c.channel = 'email'
          AND c.outbound_intent_id IS NOT NULL
    )
);

-- ------------------------------------------------------------
-- Upgrade the EXISTING authoritative reply transaction.
--
-- Resend:
--   legacy reply
--   + outbound event
--   + canonical conversation
--   + canonical inbound event
--
-- become one atomic transaction.
--
-- Other/non-Resend callers retain the legacy behavior.
-- ------------------------------------------------------------

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

        SELECT *
          INTO e
          FROM public.empire_conversation_events
         WHERE conversation_id = c.id
           AND provider_event_id =
               p_provider_message_id
         FOR UPDATE;

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
            RETURNING *
            INTO e;

            v_event_status := 'recorded';
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

REVOKE ALL
ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
)
FROM PUBLIC;

GRANT EXECUTE
ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
)
TO empire_reply_ingest;

COMMENT ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
)
IS
'Migration 033: atomically records verified Resend replies into legacy reply evidence and canonical Conversation OS. actual_revenue=false; no send/payment/terms/fulfilment authority.';

COMMIT;
