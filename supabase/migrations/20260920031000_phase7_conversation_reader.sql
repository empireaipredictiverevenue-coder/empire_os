-- Phase 7 Conversation OS dedicated read role.
-- Staged only: read-only canonical conversation timeline access.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_conversation_reader'
  ) THEN
    CREATE ROLE empire_conversation_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_conversation_reader;

REVOKE ALL ON public.empire_conversations,
  public.empire_conversation_events
FROM empire_conversation_reader;

GRANT SELECT ON public.empire_conversations,
  public.empire_conversation_events
TO empire_conversation_reader;

ALTER TABLE public.empire_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_conversation_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS conversation_reader_conversations
ON public.empire_conversations;

CREATE POLICY conversation_reader_conversations
ON public.empire_conversations
FOR SELECT
TO empire_conversation_reader
USING (true);

DROP POLICY IF EXISTS conversation_reader_events
ON public.empire_conversation_events;

CREATE POLICY conversation_reader_events
ON public.empire_conversation_events
FOR SELECT
TO empire_conversation_reader
USING (true);

REVOKE empire_conversation_ingest FROM empire_conversation_reader;
REVOKE empire_conversation_reader FROM empire_conversation_ingest;

COMMIT;
