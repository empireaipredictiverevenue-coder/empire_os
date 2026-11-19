-- Synthetic, offline-only PostgreSQL fixture for Mautic -> Smart CRM integration.
-- Must only be applied to an ephemeral PostgreSQL cluster created by the test
-- runner. This script provisions dummy roles and synthetic rows, NEVER live.
\set ON_ERROR_STOP on

DO $$
BEGIN
 IF current_database() <> 'mautic_crm_inbox_fixture' THEN
   RAISE EXCEPTION 'REFUSE: not isolated Mautic fixture database';
 END IF;
END $$;

CREATE ROLE empiredb_migrator NOLOGIN NOINHERIT;
CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT;
CREATE ROLE empire_revenue_crm_journey_writer NOLOGIN NOINHERIT;
CREATE ROLE empiredb_app NOLOGIN;
CREATE ROLE empiredb_readonly NOLOGIN;
CREATE ROLE empiredb_tenant_reader NOLOGIN;
CREATE ROLE mautic_fixture_writer_a LOGIN NOINHERIT;
CREATE ROLE mautic_fixture_writer_b LOGIN NOINHERIT;
CREATE ROLE mautic_fixture_reader_a LOGIN NOINHERIT;
-- Distinct real-login-shaped roles for the full private pilot wiring canary.
CREATE ROLE empire_mautic_tenant_aabbccddeeff LOGIN NOINHERIT;
CREATE ROLE empire_crm_tenant_0123456789ab LOGIN NOINHERIT;

GRANT empiredb_migrator TO fixture_owner;
GRANT empire_revenue_crm_reader TO mautic_fixture_reader_a;
GRANT empire_revenue_crm_reader TO empire_crm_tenant_0123456789ab;
GRANT CREATE ON SCHEMA public TO empiredb_migrator;

SET ROLE empiredb_migrator;
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog
AS $tenant$
  SELECT CASE session_user
    WHEN 'mautic_fixture_writer_a'
      THEN '00000000-0000-0000-0000-000000000101'::uuid
    WHEN 'mautic_fixture_writer_b'
      THEN '00000000-0000-0000-0000-000000000102'::uuid
    WHEN 'mautic_fixture_reader_a'
      THEN '00000000-0000-0000-0000-000000000101'::uuid
    WHEN 'empire_crm_tenant_0123456789ab'
      THEN '00000000-0000-0000-0000-000000000101'::uuid
    WHEN 'empire_mautic_tenant_aabbccddeeff'
      THEN '00000000-0000-0000-0000-000000000101'::uuid
    ELSE NULL::uuid
  END
$tenant$;
RESET ROLE;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id() TO empire_revenue_crm_reader;

-- Synthetic CRM row and explicit read-only projection for the canonical
-- reader. This is NOT a production CRM schema or a deployment migration.
CREATE TABLE public.mautic_fixture_prospects (
  tenant_id uuid NOT NULL,
  prospect_id uuid PRIMARY KEY,
  business_name text NOT NULL,
  niche text,
  metro text,
  prospect_status text,
  conversation_id uuid,
  conversation_channel text,
  conversation_state text,
  conversation_updated_at timestamptz,
  closer_case_id uuid,
  closer_state text,
  closer_updated_at timestamptz,
  fulfilment_order_id uuid,
  fulfilment_state text,
  fulfilment_updated_at timestamptz,
  price_cents bigint,
  buyer_id uuid,
  buyer_activation_state text,
  buyer_available_capacity integer,
  buyer_capacity_verified_at timestamptz,
  deal_probability numeric
);
REVOKE ALL ON public.mautic_fixture_prospects FROM PUBLIC;
INSERT INTO public.mautic_fixture_prospects (
  tenant_id,prospect_id,business_name,niche,prospect_status,
  conversation_id,conversation_state,conversation_updated_at
) VALUES (
  '00000000-0000-0000-0000-000000000101',
  '00000000-0000-0000-0000-000000000201',
  'Synthetic Example Ltd', 'solar', 'suppressed',
  '00000000-0000-0000-0000-000000000301',
  'engaged', '2026-11-18T12:00:00Z'
), (
  '00000000-0000-0000-0000-000000000102',
  '00000000-0000-0000-0000-000000000202',
  'Second Tenant Synthetic Example', 'solar', 'engaged',
  '00000000-0000-0000-0000-000000000302',
  'engaged', '2026-11-18T12:00:00Z'
);
CREATE VIEW public.revenue_crm_prospects WITH (security_barrier=true) AS
  SELECT * FROM public.mautic_fixture_prospects;
REVOKE ALL ON public.revenue_crm_prospects FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO empire_revenue_crm_reader;
GRANT SELECT ON public.revenue_crm_prospects TO empire_revenue_crm_reader;
