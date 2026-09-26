-- Phase 14 dedicated read-only Digital Twin registry role.
-- Staged only: simulations cannot execute capital, campaigns or pricing.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_digital_twin_registry_reader'
  ) THEN
    CREATE ROLE empire_digital_twin_registry_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_digital_twin_registry_reader;

REVOKE ALL ON public.digital_twin_scenarios,
  public.digital_twin_results
FROM empire_digital_twin_registry_reader;

GRANT SELECT ON public.digital_twin_scenarios,
  public.digital_twin_results
TO empire_digital_twin_registry_reader;

COMMENT ON ROLE empire_digital_twin_registry_reader IS
'Phase 14 least-privilege read-only role for Digital Twin scenarios/results.';

COMMIT;
