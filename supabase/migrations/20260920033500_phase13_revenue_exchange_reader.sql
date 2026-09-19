-- Phase 13 dedicated read-only Revenue Exchange role.
-- Staged only: no allocation, settlement or pricing authority.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_revenue_exchange_reader'
  ) THEN
    CREATE ROLE empire_revenue_exchange_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_revenue_exchange_reader;

REVOKE ALL ON public.revenue_exchange_observations
FROM empire_revenue_exchange_reader;

GRANT SELECT ON public.revenue_exchange_observations
TO empire_revenue_exchange_reader;

COMMENT ON ROLE empire_revenue_exchange_reader IS
'Phase 13 least-privilege read-only role for Revenue Exchange observations.';

COMMIT;
