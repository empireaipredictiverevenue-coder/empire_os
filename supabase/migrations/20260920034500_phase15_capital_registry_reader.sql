-- Phase 15 dedicated read-only capital review registry role.
-- Staged only: no funds movement or budget mutation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_capital_registry_reader'
  ) THEN
    CREATE ROLE empire_capital_registry_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_capital_registry_reader;

REVOKE ALL ON public.capital_review_registry
FROM empire_capital_registry_reader;

GRANT SELECT ON public.capital_review_registry
TO empire_capital_registry_reader;

COMMENT ON ROLE empire_capital_registry_reader IS
'Phase 15 least-privilege read-only role for capital review registry.';

COMMIT;
