-- Phase 6 authenticated A2A commercial-intent foundation.
-- Staged only: no production apply, approval execution, payment or allocation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_a2a_intent_writer'
  ) THEN
    CREATE ROLE empire_a2a_intent_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_a2a_intent_writer;
REVOKE empire_a2a_intent_writer FROM service_role;

CREATE TABLE IF NOT EXISTS public.a2a_commercial_intents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id text NOT NULL,
  key_id text NOT NULL,
  capability text NOT NULL CHECK (
    capability IN (
      'commerce.quote.request',
      'commerce.negotiation.start',
      'commerce.task.create'
    )
  ),
  idempotency_key text NOT NULL UNIQUE,
  request jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending_approval'
    CHECK (status='pending_approval'),
  human_approval_required boolean NOT NULL DEFAULT true
    CHECK (human_approval_required),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  payment_authority boolean NOT NULL DEFAULT false
    CHECK (NOT payment_authority),
  allocation_authority boolean NOT NULL DEFAULT false
    CHECK (NOT allocation_authority),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_a2a_intents_agent_created
  ON public.a2a_commercial_intents(agent_id, created_at DESC);

ALTER TABLE public.a2a_commercial_intents ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.a2a_commercial_intents
FROM PUBLIC,anon,authenticated,service_role,empire_a2a_intent_writer;

GRANT SELECT ON public.a2a_commercial_intents TO service_role;

CREATE OR REPLACE FUNCTION public.guard_a2a_commercial_intents_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'a2a commercial intents are append-only';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_a2a_commercial_intents_append_only
ON public.a2a_commercial_intents;

CREATE TRIGGER guard_a2a_commercial_intents_append_only
BEFORE UPDATE OR DELETE ON public.a2a_commercial_intents
FOR EACH ROW EXECUTE FUNCTION
  public.guard_a2a_commercial_intents_append_only();

CREATE OR REPLACE FUNCTION public.record_a2a_commercial_intent(
  p_agent_id text,
  p_key_id text,
  p_capability text,
  p_idempotency_key text,
  p_request jsonb DEFAULT '{}'::jsonb,
  p_evidence jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.a2a_commercial_intents%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_agent_id,''))='' THEN
    RAISE EXCEPTION 'agent_id required';
  END IF;
  IF trim(COALESCE(p_key_id,''))='' THEN
    RAISE EXCEPTION 'key_id required';
  END IF;
  IF trim(COALESCE(p_idempotency_key,''))='' THEN
    RAISE EXCEPTION 'idempotency_key required';
  END IF;
  IF p_capability NOT IN (
    'commerce.quote.request',
    'commerce.negotiation.start',
    'commerce.task.create'
  ) THEN
    RAISE EXCEPTION 'unsupported commerce capability';
  END IF;

  SELECT * INTO r
  FROM public.a2a_commercial_intents
  WHERE idempotency_key=trim(p_idempotency_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'intent_id',r.id,
      'agent_id',r.agent_id,
      'capability',r.capability,
      'human_approval_required',true,
      'execution_authority','none',
      'payment_authority',false,
      'allocation_authority',false
    );
  END IF;

  INSERT INTO public.a2a_commercial_intents(
    agent_id,key_id,capability,idempotency_key,request,evidence
  )
  VALUES(
    trim(p_agent_id),
    trim(p_key_id),
    p_capability,
    trim(p_idempotency_key),
    COALESCE(p_request,'{}'::jsonb),
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','pending_approval',
    'intent_id',r.id,
    'agent_id',r.agent_id,
    'capability',r.capability,
    'human_approval_required',true,
    'execution_authority','none',
    'payment_authority',false,
    'allocation_authority',false
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_a2a_commercial_intent(
  text,text,text,text,jsonb,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_a2a_commercial_intent(
  text,text,text,text,jsonb,jsonb
) TO empire_a2a_intent_writer;

COMMIT;
