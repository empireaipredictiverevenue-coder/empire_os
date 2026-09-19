-- First bounded Supabase exposure hardening slice.
-- Staged only. Production application requires explicit approval.
BEGIN;

DO $$
DECLARE
  required_table text;
BEGIN
  FOREACH required_table IN ARRAY ARRAY[
    'public.b2b_leads',
    'public.empire_revenue_ledger',
    'public.crypto_payment_requests'
  ]
  LOOP
    IF to_regclass(required_table) IS NULL THEN
      RAISE EXCEPTION 'Security hardening dependency missing: %', required_table;
    END IF;
  END LOOP;
END $$;

-- These tables are internal/legacy surfaces. Client roles must not access them
-- directly through the Supabase Data API.
REVOKE ALL PRIVILEGES ON TABLE
  public.b2b_leads,
  public.empire_revenue_ledger,
  public.crypto_payment_requests
FROM anon, authenticated;

ALTER TABLE public.b2b_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_revenue_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_payment_requests ENABLE ROW LEVEL SECURITY;

-- No anon/authenticated policies are created intentionally.
-- service_role retains its explicit table grants and bypasses RLS.
-- postgres ownership/admin access is unchanged.

COMMENT ON TABLE public.b2b_leads IS
'Internal legacy lead-import source; direct anon/authenticated Data API access revoked.';
COMMENT ON TABLE public.empire_revenue_ledger IS
'Internal revenue ledger; direct anon/authenticated Data API access revoked.';
COMMENT ON TABLE public.crypto_payment_requests IS
'Legacy payment-request table superseded by governed BSC payment flow; direct anon/authenticated Data API access revoked.';

COMMIT;
