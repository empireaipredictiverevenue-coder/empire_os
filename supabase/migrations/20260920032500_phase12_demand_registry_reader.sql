-- Phase 12 dedicated read-only demand registry role.
-- Staged only: no publishing, outbound, ad spend or provider activation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_demand_registry_reader'
  ) THEN
    CREATE ROLE empire_demand_registry_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_demand_registry_reader;

REVOKE ALL ON public.demand_plan_registry
FROM empire_demand_registry_reader;

GRANT SELECT ON public.demand_plan_registry
TO empire_demand_registry_reader;

COMMENT ON ROLE empire_demand_registry_reader IS
'Phase 12 least-privilege read-only role for demand_plan_registry.';

COMMIT;
