-- Phase 3 commercial-evidence verification identity.
-- The LOGIN remains passwordless/inert until a founder-controlled credential
-- is explicitly provisioned out of band.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_commercial_evidence_verifier'
  ) THEN
    CREATE ROLE empire_commercial_evidence_verifier
      NOLOGIN NOINHERIT;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_commercial_evidence_verifier_login'
  ) THEN
    CREATE ROLE empire_commercial_evidence_verifier_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_commercial_evidence_verifier_login PASSWORD NULL;
GRANT empire_commercial_evidence_verifier
TO empire_commercial_evidence_verifier_login;

GRANT USAGE ON SCHEMA public
TO empire_commercial_evidence_verifier;

GRANT EXECUTE ON FUNCTION
  public.verify_commercial_evidence(uuid,text)
TO empire_commercial_evidence_verifier;

GRANT EXECUTE ON FUNCTION
  public.reject_commercial_evidence(uuid,text,text)
TO empire_commercial_evidence_verifier;

REVOKE ALL ON FUNCTION
  public.propose_commercial_evidence(
    text,uuid,uuid,uuid,text,text,bigint,text,text,text,jsonb,timestamptz,timestamptz
  )
FROM empire_commercial_evidence_verifier;

REVOKE ALL ON FUNCTION
  public.decide_commercial_terms(uuid,text,text,text)
FROM empire_commercial_evidence_verifier;

ALTER ROLE empire_commercial_evidence_verifier_login
  SET statement_timeout='15s';
ALTER ROLE empire_commercial_evidence_verifier_login
  SET idle_in_transaction_session_timeout='30s';

COMMIT;
