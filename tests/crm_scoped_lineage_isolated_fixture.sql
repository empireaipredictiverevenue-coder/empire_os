-- Disposable PostgreSQL 18 fixture only. NEVER use against empiredb.
CREATE ROLE empiredb_migrator NOLOGIN NOINHERIT;
CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT;
CREATE ROLE crm_fixture_a LOGIN NOINHERIT;
CREATE ROLE crm_fixture_b LOGIN NOINHERIT;
CREATE ROLE crm_fixture_unbound LOGIN NOINHERIT;
GRANT empire_revenue_crm_reader TO crm_fixture_a,crm_fixture_b,crm_fixture_unbound;
GRANT USAGE ON SCHEMA public TO empire_revenue_crm_reader;
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
SET ROLE empiredb_migrator;
CREATE TABLE public.prospects (id uuid PRIMARY KEY);
CREATE TABLE public.business_entities (id uuid PRIMARY KEY);
CREATE TABLE public.prospect_entity_links (
 prospect_id uuid NOT NULL, entity_id uuid NOT NULL, active bool NOT NULL,
 match_method text NOT NULL, evidence jsonb NOT NULL
);
CREATE TABLE public.tenant_business_entity_bindings (
 tenant_id uuid NOT NULL,entity_id uuid NOT NULL,binding_kind text NOT NULL,
 evidence_ref text NOT NULL,active bool NOT NULL,
 valid_from timestamptz NOT NULL,valid_until timestamptz
);
CREATE TABLE public.business_entity_conflicts (
 prospect_id uuid NOT NULL,entity_id uuid NOT NULL,resolution_state text NOT NULL
);
CREATE TABLE public.gtm_opportunities (id uuid PRIMARY KEY);
CREATE TABLE public.buyers (id uuid PRIMARY KEY,org_id uuid NOT NULL);
CREATE TABLE public.commercial_events (
 id uuid PRIMARY KEY,opportunity_id uuid,prospect_id uuid,
 entity_id uuid,buyer_id uuid
);
CREATE TABLE public.fulfilment_orders (
 id uuid PRIMARY KEY,opportunity_id uuid,prospect_id uuid,
 entity_id uuid,buyer_id uuid
);
CREATE TABLE public.empire_tenant_role_bindings (
 role_name name PRIMARY KEY, tenant_id uuid NOT NULL,active bool NOT NULL
);
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT b.tenant_id FROM public.empire_tenant_role_bindings b
 WHERE b.role_name=session_user AND b.active IS TRUE LIMIT 1
$$;
CREATE FUNCTION public.empire_crm_prospect_authorized(p_prospect_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT public.empire_current_tenant_id() IS NOT NULL AND (
  SELECT count(*)=1 FROM public.prospect_entity_links l
  JOIN public.tenant_business_entity_bindings b ON b.entity_id=l.entity_id
  WHERE l.prospect_id=p_prospect_id AND l.active IS TRUE
  AND b.tenant_id=public.empire_current_tenant_id()
  AND b.active IS TRUE AND b.valid_from<=CURRENT_TIMESTAMP
  AND (b.valid_until IS NULL OR b.valid_until>CURRENT_TIMESTAMP)
 )
$$;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_crm_prospect_authorized(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
 TO empire_revenue_crm_reader;
GRANT EXECUTE ON FUNCTION public.empire_crm_prospect_authorized(uuid)
 TO empire_revenue_crm_reader;
INSERT INTO public.empire_tenant_role_bindings VALUES
 ('crm_fixture_a','00000000-0000-0000-0000-0000000000a1',true),
 ('crm_fixture_b','00000000-0000-0000-0000-0000000000b1',true);
INSERT INTO public.prospects VALUES
 ('00000000-0000-0000-0000-000000000001');
INSERT INTO public.business_entities VALUES
 ('00000000-0000-0000-0000-000000000002');
INSERT INTO public.prospect_entity_links VALUES
 ('00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',true,
  'verified_source_identity','{"source_ref":"fixture:first_party"}'::jsonb);
-- Same canonical entity intentionally belongs to two tenants. A receipt
-- must remain scoped to its own actual buyer, not just the shared entity.
INSERT INTO public.tenant_business_entity_bindings VALUES
 ('00000000-0000-0000-0000-0000000000a1',
  '00000000-0000-0000-0000-000000000002','prospect','fixture:tenant_a',true,
  CURRENT_TIMESTAMP-INTERVAL '1 day',NULL),
 ('00000000-0000-0000-0000-0000000000b1',
  '00000000-0000-0000-0000-000000000002','prospect','fixture:tenant_b',true,
  CURRENT_TIMESTAMP-INTERVAL '1 day',NULL);
INSERT INTO public.gtm_opportunities VALUES
 ('00000000-0000-0000-0000-000000000003');
INSERT INTO public.buyers VALUES
 ('00000000-0000-0000-0000-0000000000a2',
  '00000000-0000-0000-0000-0000000000a1'),
 ('00000000-0000-0000-0000-0000000000b2',
  '00000000-0000-0000-0000-0000000000b1');
INSERT INTO public.commercial_events VALUES
 ('00000000-0000-0000-0000-0000000000a3',
  '00000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000000b3',
  '00000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-0000000000b2'),
 ('00000000-0000-0000-0000-0000000000c3',
  '00000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',NULL);
INSERT INTO public.fulfilment_orders VALUES
 ('00000000-0000-0000-0000-0000000000a4',
  '00000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-0000000000a2'),
 ('00000000-0000-0000-0000-0000000000b4',
  '00000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-0000000000b2'),
 ('00000000-0000-0000-0000-0000000000c4',
  '00000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002',NULL);
RESET ROLE;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
