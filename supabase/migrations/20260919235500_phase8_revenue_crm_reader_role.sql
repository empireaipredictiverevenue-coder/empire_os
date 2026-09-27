-- Phase 8 dedicated read-only Revenue CRM role.
-- Staged only: no production apply, credentials, follow-up or payment authority.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_revenue_crm_reader'
  ) THEN
    CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_revenue_crm_reader;

REVOKE ALL ON public.revenue_crm_prospects,
  public.revenue_crm_buyers
FROM empire_revenue_crm_reader;

GRANT SELECT ON public.revenue_crm_prospects,
  public.revenue_crm_buyers
TO empire_revenue_crm_reader;

COMMENT ON ROLE empire_revenue_crm_reader IS
'Phase 8 least-privilege read-only role for canonical Revenue CRM views.';

COMMIT;
