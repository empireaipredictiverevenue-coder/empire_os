-- Phase 7 Conversation OS canonical foundation.
-- Staged only: no provider activation, outbound, booking or production apply.
BEGIN;

CREATE TABLE IF NOT EXISTS public.empire_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel text NOT NULL CHECK (channel IN ('email','sms','voice','a2a')),
  state text NOT NULL DEFAULT 'open' CHECK (
    state IN ('open','engaged','paused','closed')
  ),
  prospect_id uuid REFERENCES public.prospects(id) ON DELETE RESTRICT,
  entity_id uuid REFERENCES public.business_entities(id) ON DELETE RESTRICT,
  buyer_id uuid REFERENCES public.buyers(id) ON DELETE RESTRICT,
  opportunity_id uuid REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
  closer_case_id uuid REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  outbound_intent_id uuid REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
  external_conversation_id text,
  provider text,
  opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (
    prospect_id IS NOT NULL OR entity_id IS NOT NULL OR
    buyer_id IS NOT NULL OR closer_case_id IS NOT NULL
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_empire_conversation_external
  ON public.empire_conversations(channel, provider, external_conversation_id)
  WHERE external_conversation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_empire_conversations_participants
  ON public.empire_conversations(prospect_id, buyer_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.empire_conversation_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL
    REFERENCES public.empire_conversations(id) ON DELETE RESTRICT,
  event_type text NOT NULL,
  direction text NOT NULL CHECK (
    direction IN ('inbound','outbound','internal')
  ),
  actor text,
  body_text text,
  provider_event_id text,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_empire_conversation_provider_event
  ON public.empire_conversation_events(conversation_id, provider_event_id)
  WHERE provider_event_id IS NOT NULL;
ALTER TABLE public.empire_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_conversation_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.empire_conversations,
  public.empire_conversation_events
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.empire_conversations,
  public.empire_conversation_events
TO service_role;

CREATE OR REPLACE FUNCTION public.guard_empire_conversation_events_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'conversation events are append-only';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER guard_empire_conversation_events_append_only
BEFORE UPDATE OR DELETE ON public.empire_conversation_events
FOR EACH ROW EXECUTE FUNCTION
  public.guard_empire_conversation_events_append_only();

COMMIT;
