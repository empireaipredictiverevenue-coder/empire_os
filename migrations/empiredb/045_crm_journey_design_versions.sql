-- EmpireDB 045: PREPARED-ONLY, requires explicit founder approval to apply.
-- Append-only tenant-scoped journey DESIGN metadata. No execution/sender rights.
-- Strict prerequisite: separately provisioned NOLOGIN NOINHERIT writer role
-- and a dedicated per-tenant LOGIN bound by trusted session_user.
-- DO NOT add memberships, passwords, tenant bindings or public API here.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','crm_design_fixture') THEN
   RAISE EXCEPTION 'invalid CRM journey migration target';
 END IF;
 IF pg_catalog.to_regclass('public.empire_crm_journey_design_versions') IS NOT NULL THEN
   RAISE EXCEPTION 'existing journey design table: reconcile rather than overwrite';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_revenue_crm_journey_writer'
   AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
   AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN
   RAISE EXCEPTION 'dedicated NOLOGIN journey design writer role required';
 END IF;
 IF pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_proc p
      JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
      WHERE p.oid='public.empire_current_tenant_id()'::pg_catalog.regprocedure
        AND p.prosecdef AND p.provolatile='s'
        AND r.rolname='empiredb_migrator'
    ) THEN
   RAISE EXCEPTION 'trusted tenant resolver required before journey storage';
 END IF;
END;
$guard$;

CREATE TABLE public.empire_crm_journey_design_versions (
  tenant_id uuid NOT NULL,
  design_id uuid NOT NULL,
  revision integer NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
  schema_version text NOT NULL DEFAULT 'empire.revenue_crm_visual_draft.v1'
    CHECK (schema_version = 'empire.revenue_crm_visual_draft.v1'),
  design_json jsonb NOT NULL CHECK (
    jsonb_typeof(design_json) = 'object'
    AND octet_length(design_json::text) <= 65536
    AND design_json->>'schema_version' = 'empire.revenue_crm_visual_draft.v1'
    AND design_json->>'state' = 'DESIGN_ONLY'
    AND design_json->>'execution_authority' = 'none'
    AND design_json->>'tenant_data_included' = 'false'
    AND design_json->>'server_persistence' = 'false'
    AND NOT design_json ? 'tenant_id'
    AND NOT design_json ? 'prospect_id'
    AND NOT design_json ? 'contact_email'
  ),
  design_sha256 text NOT NULL CHECK (design_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id,design_id,revision)
);
ALTER TABLE public.empire_crm_journey_design_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_crm_journey_design_versions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.empire_crm_journey_design_versions FROM PUBLIC;
REVOKE ALL ON public.empire_crm_journey_design_versions FROM
  empiredb_app,empiredb_readonly,empiredb_tenant_reader,empire_revenue_crm_reader;
CREATE POLICY journey_version_select
 ON public.empire_crm_journey_design_versions FOR SELECT
 TO empire_revenue_crm_journey_writer
 USING (
    tenant_id=public.empire_current_tenant_id()
    AND public.empire_current_tenant_id() IS NOT NULL
 );
CREATE POLICY journey_version_insert
 ON public.empire_crm_journey_design_versions FOR INSERT
 TO empire_revenue_crm_journey_writer
 WITH CHECK (
    tenant_id=public.empire_current_tenant_id()
    AND public.empire_current_tenant_id() IS NOT NULL
    AND design_json->>'state'='DESIGN_ONLY'
    AND design_json->>'execution_authority'='none'
 );
GRANT USAGE ON SCHEMA public TO empire_revenue_crm_journey_writer;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
 TO empire_revenue_crm_journey_writer;
GRANT SELECT,INSERT ON public.empire_crm_journey_design_versions
 TO empire_revenue_crm_journey_writer;
COMMENT ON TABLE public.empire_crm_journey_design_versions IS
 'Append-only non-executable CRM design JSON. No consent proof, customer rows, sender, workflow execution or payment authority. Tenant bound by trusted session_user.';
COMMIT;
