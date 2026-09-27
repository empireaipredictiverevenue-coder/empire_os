-- Phase 6 persistent A2A identity nonce registry.
-- Staged only: no production apply and no execution authority.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_a2a_identity_nonce_writer'
  ) THEN
    CREATE ROLE empire_a2a_identity_nonce_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_a2a_identity_nonce_writer;
REVOKE empire_a2a_identity_nonce_writer FROM service_role;

CREATE TABLE IF NOT EXISTS public.a2a_identity_nonces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id text NOT NULL,
  key_id text NOT NULL,
  nonce text NOT NULL,
  issued_at timestamptz NOT NULL,
  consumed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(agent_id,key_id,nonce)
);

ALTER TABLE public.a2a_identity_nonces ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.a2a_identity_nonces
FROM PUBLIC,anon,authenticated,service_role,empire_a2a_identity_nonce_writer;

GRANT SELECT ON public.a2a_identity_nonces TO service_role;

CREATE OR REPLACE FUNCTION public.consume_a2a_identity_nonce(
  p_agent_id text,
  p_key_id text,
  p_nonce text,
  p_issued_at timestamptz
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  inserted_count integer;
BEGIN
  IF trim(COALESCE(p_agent_id,''))='' THEN
    RAISE EXCEPTION 'agent_id required';
  END IF;
  IF trim(COALESCE(p_key_id,''))='' THEN
    RAISE EXCEPTION 'key_id required';
  END IF;
  IF trim(COALESCE(p_nonce,''))='' THEN
    RAISE EXCEPTION 'nonce required';
  END IF;
  IF p_issued_at IS NULL THEN
    RAISE EXCEPTION 'issued_at required';
  END IF;

  INSERT INTO public.a2a_identity_nonces(
    agent_id,key_id,nonce,issued_at
  )
  VALUES(
    trim(p_agent_id),
    trim(p_key_id),
    trim(p_nonce),
    p_issued_at
  )
  ON CONFLICT(agent_id,key_id,nonce) DO NOTHING;

  GET DIAGNOSTICS inserted_count = ROW_COUNT;
  RETURN inserted_count = 1;
END;
$$;

REVOKE ALL ON FUNCTION public.consume_a2a_identity_nonce(
  text,text,text,timestamptz
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.consume_a2a_identity_nonce(
  text,text,text,timestamptz
) TO empire_a2a_identity_nonce_writer;

COMMIT;
