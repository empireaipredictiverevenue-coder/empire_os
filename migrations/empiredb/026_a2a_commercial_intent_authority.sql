-- A2A identity nonce + non-binding commercial intent authority.
-- No execution, allocation, payment, terms-acceptance or revenue-recognition authority.
BEGIN;

DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'empire_a2a_identity_nonce_writer') THEN
  CREATE ROLE empire_a2a_identity_nonce_writer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'empire_a2a_intent_writer') THEN
  CREATE ROLE empire_a2a_intent_writer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.a2a_identity_nonces (
 agent_id text NOT NULL CHECK (length(btrim(agent_id)) BETWEEN 1 AND 200),
 key_id text NOT NULL CHECK (length(btrim(key_id)) BETWEEN 1 AND 200),
 nonce text NOT NULL CHECK (length(btrim(nonce)) BETWEEN 1 AND 300),
 issued_at timestamptz NOT NULL,
 consumed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (agent_id, key_id, nonce)
);

CREATE TABLE IF NOT EXISTS public.a2a_commercial_intents (
 intent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 agent_id text NOT NULL CHECK (length(btrim(agent_id)) BETWEEN 1 AND 200),
 key_id text NOT NULL CHECK (length(btrim(key_id)) BETWEEN 1 AND 200),
 identity_nonce text NOT NULL CHECK (length(btrim(identity_nonce)) BETWEEN 1 AND 300),
 identity_issued_at timestamptz NOT NULL,
 capability text NOT NULL CHECK (capability IN (
   'commerce.quote.request',
   'commerce.negotiation.start',
   'commerce.task.create'
 )),
 idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 300),
 request jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(request) = 'object'),
 evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence) = 'object'),
 status text NOT NULL DEFAULT 'pending_approval' CHECK (status = 'pending_approval'),
 human_approval_required boolean NOT NULL DEFAULT true CHECK (human_approval_required),
 execution_authority text NOT NULL DEFAULT 'none' CHECK (execution_authority = 'none'),
 payment_authority boolean NOT NULL DEFAULT false CHECK (NOT payment_authority),
 allocation_authority boolean NOT NULL DEFAULT false CHECK (NOT allocation_authority),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

REVOKE ALL ON public.a2a_identity_nonces, public.a2a_commercial_intents
 FROM PUBLIC, empiredb_app, empire_a2a_identity_nonce_writer, empire_a2a_intent_writer;

CREATE OR REPLACE FUNCTION public.consume_a2a_identity_nonce(
 p_agent_id text,
 p_key_id text,
 p_nonce text,
 p_issued_at timestamptz
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE inserted_count integer;
BEGIN
 IF length(btrim(p_agent_id)) NOT BETWEEN 1 AND 200
    OR length(btrim(p_key_id)) NOT BETWEEN 1 AND 200
    OR length(btrim(p_nonce)) NOT BETWEEN 1 AND 300
    OR p_issued_at IS NULL THEN
  RAISE EXCEPTION 'invalid_a2a_identity_nonce';
 END IF;

 INSERT INTO public.a2a_identity_nonces(agent_id,key_id,nonce,issued_at)
 VALUES (btrim(p_agent_id),btrim(p_key_id),btrim(p_nonce),p_issued_at)
 ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS inserted_count = ROW_COUNT;
 RETURN inserted_count = 1;
END;
$$;

CREATE OR REPLACE FUNCTION public.record_a2a_commercial_intent(
 p_agent_id text,
 p_key_id text,
 p_identity_nonce text,
 p_identity_issued_at timestamptz,
 p_capability text,
 p_idempotency_key text,
 p_request jsonb,
 p_evidence jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
 existing public.a2a_commercial_intents%ROWTYPE;
 created public.a2a_commercial_intents%ROWTYPE;
BEGIN
 IF length(btrim(p_agent_id)) NOT BETWEEN 1 AND 200
    OR length(btrim(p_key_id)) NOT BETWEEN 1 AND 200
    OR length(btrim(p_identity_nonce)) NOT BETWEEN 1 AND 300
    OR length(btrim(p_idempotency_key)) NOT BETWEEN 1 AND 300
    OR p_identity_issued_at IS NULL
    OR p_capability NOT IN ('commerce.quote.request','commerce.negotiation.start','commerce.task.create')
    OR jsonb_typeof(COALESCE(p_request,'{}'::jsonb)) <> 'object'
    OR jsonb_typeof(COALESCE(p_evidence,'{}'::jsonb)) <> 'object' THEN
  RAISE EXCEPTION 'invalid_a2a_commercial_intent';
 END IF;

 SELECT * INTO existing
 FROM public.a2a_commercial_intents
 WHERE idempotency_key = btrim(p_idempotency_key);

 IF FOUND THEN
  IF existing.agent_id <> btrim(p_agent_id)
     OR existing.key_id <> btrim(p_key_id)
     OR existing.capability <> p_capability THEN
   RAISE EXCEPTION 'a2a_idempotency_conflict';
  END IF;
  RETURN jsonb_build_object(
   'status','existing',
   'intent_id',existing.intent_id,
   'agent_id',existing.agent_id,
   'capability',existing.capability
  );
 END IF;

 INSERT INTO public.a2a_commercial_intents(
  agent_id,key_id,identity_nonce,identity_issued_at,capability,
  idempotency_key,request,evidence
 ) VALUES (
  btrim(p_agent_id),btrim(p_key_id),btrim(p_identity_nonce),p_identity_issued_at,
  p_capability,btrim(p_idempotency_key),COALESCE(p_request,'{}'::jsonb),
  COALESCE(p_evidence,'{}'::jsonb)
 )
 RETURNING * INTO created;

 RETURN jsonb_build_object(
  'status','pending_approval',
  'intent_id',created.intent_id,
  'agent_id',created.agent_id,
  'capability',created.capability
 );
END;
$$;

REVOKE ALL ON FUNCTION public.consume_a2a_identity_nonce(text,text,text,timestamptz) FROM PUBLIC, empiredb_app;
REVOKE ALL ON FUNCTION public.record_a2a_commercial_intent(text,text,text,timestamptz,text,text,jsonb,jsonb) FROM PUBLIC, empiredb_app;

GRANT USAGE ON SCHEMA public TO empire_a2a_identity_nonce_writer, empire_a2a_intent_writer;
GRANT EXECUTE ON FUNCTION public.consume_a2a_identity_nonce(text,text,text,timestamptz)
 TO empire_a2a_identity_nonce_writer;
GRANT EXECUTE ON FUNCTION public.record_a2a_commercial_intent(text,text,text,timestamptz,text,text,jsonb,jsonb)
 TO empire_a2a_intent_writer;

COMMIT;
