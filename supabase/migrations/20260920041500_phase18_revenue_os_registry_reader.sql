-- Phase 18 dedicated read-only Revenue OS decision-packet reader.
-- Staged only: no spend, outreach, payment, allocation or deployment execution.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_revenue_os_registry_reader'
  ) THEN
    CREATE ROLE empire_revenue_os_registry_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_revenue_os_registry_reader;

REVOKE ALL ON public.revenue_os_decision_packets
FROM empire_revenue_os_registry_reader;

GRANT SELECT ON public.revenue_os_decision_packets
TO empire_revenue_os_registry_reader;

COMMENT ON ROLE empire_revenue_os_registry_reader IS
'Phase 18 least-privilege read-only role for Revenue OS decision packets.';

COMMIT;
