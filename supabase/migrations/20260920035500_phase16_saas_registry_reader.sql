-- Phase 16 dedicated read-only SaaS readiness registry role.
-- Staged only: no provisioning, billing or subscription mutation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_saas_registry_reader'
  ) THEN
    CREATE ROLE empire_saas_registry_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_saas_registry_reader;

REVOKE ALL ON public.saas_readiness_registry
FROM empire_saas_registry_reader;

GRANT SELECT ON public.saas_readiness_registry
TO empire_saas_registry_reader;

COMMENT ON ROLE empire_saas_registry_reader IS
'Phase 16 least-privilege read-only role for SaaS readiness registry.';

COMMIT;
