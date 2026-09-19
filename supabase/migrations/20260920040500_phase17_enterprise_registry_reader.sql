-- Phase 17 dedicated read-only enterprise readiness registry role.
-- Staged only: no control, infrastructure, identity or SLO mutation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_enterprise_registry_reader'
  ) THEN
    CREATE ROLE empire_enterprise_registry_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_enterprise_registry_reader;

REVOKE ALL ON public.enterprise_readiness_registry
FROM empire_enterprise_registry_reader;

GRANT SELECT ON public.enterprise_readiness_registry
TO empire_enterprise_registry_reader;

COMMENT ON ROLE empire_enterprise_registry_reader IS
'Phase 17 least-privilege read-only role for enterprise readiness history.';

COMMIT;
