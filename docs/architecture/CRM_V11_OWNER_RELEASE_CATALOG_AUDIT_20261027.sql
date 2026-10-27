-- EmpireOS V11 ORIGINAL CRM OWNER ONLY: read-only release inventory.
-- This script CANNOT approve, install or change the held exact-order RPC.
-- Run ONLY through the original DBA-authorised session, never as an untrusted
-- public CRM endpoint. No customer records or credential values are read.
-- Requires owner review of returned boolean flags and separate restricted-
-- login, signed-tenant, privilege/revocation and rollback test evidence.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '4000ms';

WITH rpc AS (
  SELECT p.oid, p.proowner, p.proacl, p.prosecdef, p.provolatile, p.proconfig
  FROM pg_catalog.pg_proc p
  WHERE p.oid = pg_catalog.to_regprocedure(
    'public.empire_crm_exact_lineage(uuid,uuid,uuid,text)')
),
flags AS (
  SELECT
    EXISTS(SELECT 1 FROM rpc) AS exact_rpc_present,
    EXISTS(SELECT 1 FROM rpc WHERE prosecdef IS TRUE) AS security_definer,
    EXISTS(SELECT 1 FROM rpc WHERE provolatile='s') AS stable_function,
    EXISTS(SELECT 1 FROM rpc WHERE
      pg_catalog.pg_get_userbyid(proowner)='empiredb_migrator') AS owner_is_original_migrator,
    EXISTS(SELECT 1 FROM rpc WHERE
      COALESCE(proconfig, ARRAY[]::text[])
       && ARRAY['search_path=', 'search_path=""']::text[]) AS locked_empty_search_path,
    EXISTS(
      SELECT 1 FROM rpc r,
      LATERAL pg_catalog.aclexplode(COALESCE(
        r.proacl,pg_catalog.acldefault('f',r.proowner))) AS a
      WHERE a.grantee=0 AND a.privilege_type='EXECUTE'
    ) AS public_execute_present,
    EXISTS(
      SELECT 1 FROM rpc r,
        LATERAL pg_catalog.aclexplode(COALESCE(
          r.proacl,pg_catalog.acldefault('f',r.proowner))) AS a
      JOIN pg_catalog.pg_roles role ON role.oid=a.grantee
      WHERE role.rolname='empire_revenue_crm_reader'
        AND a.privilege_type='EXECUTE'
    ) AS original_reader_explicit_execute_granted,
    EXISTS(
      SELECT 1 FROM pg_catalog.pg_roles role
      WHERE role.rolname='empire_revenue_crm_reader'
        AND role.rolcanlogin IS FALSE AND role.rolinherit IS FALSE
        AND role.rolsuper IS FALSE AND role.rolcreatedb IS FALSE
        AND role.rolcreaterole IS FALSE AND role.rolbypassrls IS FALSE
        AND role.rolreplication IS FALSE
    ) AS restricted_original_reader_role,
    pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
      IS NOT NULL AS original_tenant_resolver_present,
    NOT EXISTS(
      SELECT 1 FROM (VALUES
        ('public.prospect_entity_links'),
        ('public.tenant_business_entity_bindings'),
        ('public.commercial_events'),
        ('public.fulfilment_orders')
      ) AS source(object_name)
      WHERE pg_catalog.to_regclass(source.object_name) IS NULL
        OR pg_catalog.has_table_privilege(
          'empire_revenue_crm_reader', source.object_name, 'SELECT')
    ) AS restricted_reader_has_no_raw_table_select
)
SELECT pg_catalog.jsonb_build_object(
  'schema_version','empire.crm.v11.catalog_release_audit.v1',
  'review_only',true,
  'exact_rpc_present',exact_rpc_present,
  'security_definer',security_definer,
  'stable_function',stable_function,
  'owner_is_original_migrator',owner_is_original_migrator,
  'locked_empty_search_path',locked_empty_search_path,
  'public_execute_present',public_execute_present,
  'original_reader_explicit_execute_granted',original_reader_explicit_execute_granted,
  'restricted_original_reader_role',restricted_original_reader_role,
  'original_tenant_resolver_present',original_tenant_resolver_present,
  'restricted_reader_has_no_raw_table_select',
    restricted_reader_has_no_raw_table_select,
  'catalog_preflight_passed',
    (exact_rpc_present AND security_definer AND stable_function
     AND owner_is_original_migrator AND locked_empty_search_path
     AND NOT public_execute_present
     AND original_reader_explicit_execute_granted
     AND restricted_original_reader_role
     AND original_tenant_resolver_present
     AND restricted_reader_has_no_raw_table_select),
  'owner_authorized',false,
  'real_order_verified',false,
  'financial_settlement_verified',false,
  'production_release_authorized',false
) AS crm_owner_catalog_audit
FROM flags;
ROLLBACK;
