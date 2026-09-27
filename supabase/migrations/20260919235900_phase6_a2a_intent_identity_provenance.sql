-- Phase 6 A2A commercial-intent identity provenance.
-- Staged only: no production apply, approval execution, payment or allocation.
BEGIN;

ALTER TABLE public.a2a_commercial_intents
  ADD COLUMN IF NOT EXISTS identity_nonce text,
  ADD COLUMN IF NOT EXISTS identity_issued_at timestamptz;

DROP FUNCTION IF EXISTS public.record_a2a_commercial_intent(
  text,text,text,text,jsonb,jsonb
);

CREATE OR REPLACE FUNCTION public.record_a2a_commercial_intent(
  p_agent_id text,
  p_key_id text,
  p_identity_nonce text,
  p_identity_issued_at timestamptz,
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
  IF trim(COALESCE(p_identity_nonce,''))='' THEN
    RAISE EXCEPTION 'identity_nonce required';
  END IF;
  IF p_identity_issued_at IS NULL THEN
    RAISE EXCEPTION 'identity_issued_at required';
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
    agent_id,
    key_id,
    identity_nonce,
    identity_issued_at,
    capability,
    idempotency_key,
    request,
    evidence
  )
  VALUES(
    trim(p_agent_id),
    trim(p_key_id),
    trim(p_identity_nonce),
    p_identity_issued_at,
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
  text,text,text,timestamptz,text,text,jsonb,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_a2a_commercial_intent(
  text,text,text,timestamptz,text,text,jsonb,jsonb
) TO empire_a2a_intent_writer;

COMMIT;
