-- Phase 3F dedicated runtime logins.
-- Passwords remain NULL and must be provisioned out of band.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_outcome_recorder_login'
  ) THEN
    CREATE ROLE empire_outcome_recorder_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_revenue_recognizer_login'
  ) THEN
    CREATE ROLE empire_revenue_recognizer_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_outcome_recorder_login PASSWORD NULL;
ALTER ROLE empire_revenue_recognizer_login PASSWORD NULL;

GRANT empire_outcome_recorder TO empire_outcome_recorder_login;
GRANT empire_revenue_recognizer TO empire_revenue_recognizer_login;

ALTER ROLE empire_outcome_recorder_login SET statement_timeout='15s';
ALTER ROLE empire_outcome_recorder_login SET idle_in_transaction_session_timeout='30s';
ALTER ROLE empire_revenue_recognizer_login SET statement_timeout='15s';
ALTER ROLE empire_revenue_recognizer_login SET idle_in_transaction_session_timeout='30s';

COMMENT ON ROLE empire_outcome_recorder_login IS
'Phase 3F outcome recorder login; password provisioned out of band.';
COMMENT ON ROLE empire_revenue_recognizer_login IS
'Phase 3F evidence-backed revenue recognizer login; password provisioned out of band.';

COMMIT;
