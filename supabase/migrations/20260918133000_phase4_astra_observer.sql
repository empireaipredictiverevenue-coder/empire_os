-- Phase 4 Astra read-only outcome observer identity.
-- Password remains NULL and must be provisioned out of band.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_astra_observer'
  ) THEN
    CREATE ROLE empire_astra_observer
      NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_astra_observer_login'
  ) THEN
    CREATE ROLE empire_astra_observer_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_astra_observer_login PASSWORD NULL;
GRANT USAGE ON SCHEMA public TO empire_astra_observer;
REVOKE empire_astra_observer FROM service_role;
GRANT empire_astra_observer TO empire_astra_observer_login;

ALTER ROLE empire_astra_observer_login SET statement_timeout='15s';
ALTER ROLE empire_astra_observer_login
  SET idle_in_transaction_session_timeout='30s';

REVOKE ALL ON FUNCTION public.get_commercial_outcome_feedback(integer)
  FROM PUBLIC,anon,authenticated,empire_outcome_recorder,empire_revenue_recognizer;
GRANT EXECUTE ON FUNCTION public.get_commercial_outcome_feedback(integer)
  TO empire_astra_observer,service_role;

COMMENT ON ROLE empire_astra_observer IS
'Phase 4 read-only Astra outcome observer; no direct commercial table writes.';
COMMENT ON ROLE empire_astra_observer_login IS
'Phase 4 Astra observer login; password provisioned out of band.';

COMMIT;
