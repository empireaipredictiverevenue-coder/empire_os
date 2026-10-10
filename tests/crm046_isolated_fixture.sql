-- Throw-away PostgreSQL 18-only fixture. Never run against empiredb.
CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE crm046_fixture_tenant LOGIN NOINHERIT;
CREATE ROLE crm046_fixture_other LOGIN NOINHERIT;
GRANT empire_revenue_crm_reader TO crm046_fixture_tenant;
GRANT empire_revenue_crm_reader TO crm046_fixture_other;
GRANT CREATE ON SCHEMA public TO empiredb_migrator;
GRANT USAGE ON SCHEMA public TO empire_revenue_crm_reader;
SET ROLE empiredb_migrator;
CREATE TABLE public.prospects (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, phone text);
ALTER TABLE public.prospects ENABLE ROW LEVEL SECURITY;
CREATE TABLE public.outbound_suppressions (
 normalized_contact text UNIQUE NOT NULL,contact_type text NOT NULL,reason text,source text
);
CREATE TABLE public.empire_tenant_role_bindings (
 role_name name PRIMARY KEY, tenant_id uuid NOT NULL, active boolean NOT NULL
);
INSERT INTO public.empire_tenant_role_bindings VALUES
 ('crm046_fixture_tenant','00000000-0000-0000-0000-000000000101',true),
 ('crm046_fixture_other','00000000-0000-0000-0000-000000000102',true);
INSERT INTO public.prospects VALUES
 ('00000000-0000-0000-0000-000000000201','00000000-0000-0000-0000-000000000101','+441234567890'),
 ('00000000-0000-0000-0000-000000000202','00000000-0000-0000-0000-000000000101','+441234567891'),
 ('00000000-0000-0000-0000-000000000203','00000000-0000-0000-0000-000000000102','+441234567892'),
 ('00000000-0000-0000-0000-000000000204','00000000-0000-0000-0000-000000000101','invalid');
INSERT INTO public.outbound_suppressions VALUES
 ('+441234567890','phone','fixture','unit_test'),
 ('+441234567892','phone','fixture','unit_test');
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path=''
AS $fn$
 SELECT t.tenant_id FROM public.empire_tenant_role_bindings t
 WHERE t.role_name=session_user AND t.active LIMIT 1
$fn$;
CREATE FUNCTION public.empire_crm_prospect_authorized(p_prospect_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=''
AS $fn$
 SELECT public.empire_current_tenant_id() IS NOT NULL AND EXISTS (
 SELECT 1 FROM public.prospects p WHERE p.id=p_prospect_id
 AND p.tenant_id=public.empire_current_tenant_id())
$fn$;
RESET ROLE;
REVOKE ALL ON TABLE public.prospects,public.outbound_suppressions,public.empire_tenant_role_bindings FROM PUBLIC;
