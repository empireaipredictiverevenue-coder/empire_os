-- Phase 7 provider-event ingestion boundary.
-- Staged only: append-only inbound/provider evidence; no sends/calls/bookings.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_conversation_ingest'
  ) THEN
    CREATE ROLE empire_conversation_ingest NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_conversation_ingest;
REVOKE empire_conversation_ingest FROM service_role;

REVOKE ALL ON public.empire_conversation_events
FROM empire_conversation_ingest;

CREATE OR REPLACE FUNCTION public.ingest_conversation_provider_event(
  p_conversation_id uuid,
  p_provider text,
  p_external_conversation_id text,
  p_provider_event_id text,
  p_event_type text,
  p_direction text,
  p_actor text,
  p_body_text text,
  p_evidence jsonb,
  p_occurred_at timestamptz
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  c public.empire_conversations%ROWTYPE;
  e public.empire_conversation_events%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_provider,''))='' THEN
    RAISE EXCEPTION 'provider required';
  END IF;
  IF trim(COALESCE(p_external_conversation_id,''))='' THEN
    RAISE EXCEPTION 'external conversation id required';
  END IF;
  IF trim(COALESCE(p_provider_event_id,''))='' THEN
    RAISE EXCEPTION 'provider event id required';
  END IF;
  IF trim(COALESCE(p_event_type,''))='' THEN
    RAISE EXCEPTION 'event type required';
  END IF;
  IF p_direction NOT IN ('inbound','outbound','internal') THEN
    RAISE EXCEPTION 'unsupported conversation direction';
  END IF;
  IF p_occurred_at IS NULL THEN
    RAISE EXCEPTION 'occurred_at required';
  END IF;

  SELECT * INTO c
  FROM public.empire_conversations
  WHERE id=p_conversation_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'canonical conversation required';
  END IF;
  IF c.provider IS NOT NULL AND c.provider <> p_provider THEN
    RAISE EXCEPTION 'provider does not match canonical conversation';
  END IF;
  IF c.external_conversation_id IS NOT NULL
     AND c.external_conversation_id <> p_external_conversation_id THEN
    RAISE EXCEPTION 'external conversation id mismatch';
  END IF;

  SELECT * INTO e
  FROM public.empire_conversation_events
  WHERE conversation_id=p_conversation_id
    AND provider_event_id=p_provider_event_id;

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'event_id',e.id,
      'conversation_id',e.conversation_id
    );
  END IF;

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
    p_conversation_id,
    trim(p_event_type),
    p_direction,
    NULLIF(trim(COALESCE(p_actor,'')),''),
    p_body_text,
    trim(p_provider_event_id),
    COALESCE(p_evidence,'{}'::jsonb) ||
      jsonb_build_object(
        'provider',trim(p_provider),
        'external_conversation_id',
        trim(p_external_conversation_id)
      ),
    p_occurred_at
  )
  RETURNING * INTO e;

  RETURN jsonb_build_object(
    'status','recorded',
    'event_id',e.id,
    'conversation_id',e.conversation_id
  );
END;
$$;

REVOKE ALL ON FUNCTION public.ingest_conversation_provider_event(
  uuid,text,text,text,text,text,text,text,jsonb,timestamptz
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.ingest_conversation_provider_event(
  uuid,text,text,text,text,text,text,text,jsonb,timestamptz
) TO empire_conversation_ingest;

COMMIT;
