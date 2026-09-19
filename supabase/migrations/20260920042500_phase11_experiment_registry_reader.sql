-- Phase 11 dedicated read-only experiment registry role.
-- Staged only: no traffic mutation, rollout or pricing authority.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_experiment_registry_reader'
  ) THEN
    CREATE ROLE empire_experiment_registry_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_experiment_registry_reader;

REVOKE ALL ON public.experiment_registry
FROM empire_experiment_registry_reader;

GRANT SELECT ON public.experiment_registry
TO empire_experiment_registry_reader;

COMMENT ON ROLE empire_experiment_registry_reader IS
'Phase 11 least-privilege read-only role for experiment registry history.';

COMMIT;
