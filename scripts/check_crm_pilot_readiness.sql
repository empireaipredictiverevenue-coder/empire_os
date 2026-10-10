-- EmpireOS Revenue CRM pilot readiness. CATALOG ONLY / NO CUSTOMER ROWS.
-- Run: sudo -n -u postgres psql -X -w -v ON_ERROR_STOP=1 -d empiredb \
--        -f /srv/empire_os/scripts/check_crm_pilot_readiness.sql
-- This checks existing migrations and missing dedicated login roles.
-- Never grants roles, creates users, reads contacts, or authorises HTTP CRM.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
WITH observed AS (
  SELECT
    current_database() = 'empiredb' AS canonical_database,
    pg_catalog.to_regclass('public.revenue_crm_prospects') IS NOT NULL
      AND pg_catalog.to_regclass('public.revenue_crm_buyers') IS NOT NULL
      AS crm_040_views_present,
    pg_catalog.to_regclass('public.empire_crm_tenant_memberships') IS NOT NULL
      AND pg_catalog.to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NOT NULL
      AS crm_041_membership_schema_present,
    pg_catalog.to_regclass('public.empire_crm_login_credentials') IS NOT NULL
      AS crm_042_login_schema_present,
    EXISTS (
      SELECT 1 FROM pg_catalog.pg_authid r
      WHERE r.rolname='empire_crm_auth_login'
        AND NOT r.rolcanlogin AND NOT r.rolinherit
        AND r.rolpassword IS NULL
        AND NOT (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole
                 OR r.rolcreatedb OR r.rolreplication)
        AND NOT EXISTS (
          SELECT 1 FROM pg_catalog.pg_auth_members m
          WHERE m.member=r.oid
        )
    ) AS auth_identity_role_staged_nologin,
    EXISTS (
      SELECT 1 FROM pg_catalog.pg_authid r
      WHERE r.rolname='empire_crm_membership_login'
        AND NOT r.rolcanlogin AND NOT r.rolinherit
        AND r.rolpassword IS NULL
        AND NOT (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole
                 OR r.rolcreatedb OR r.rolreplication)
        AND NOT EXISTS (
          SELECT 1 FROM pg_catalog.pg_auth_members m
          WHERE m.member=r.oid
        )
    ) AS membership_identity_role_staged_nologin,
    EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles r
      WHERE r.rolname='empire_crm_auth_login'
        AND coalesce(pg_catalog.has_table_privilege(
          r.oid, pg_catalog.to_regclass('public.empire_crm_login_credentials'), 'SELECT'
        ),false)
        AND coalesce(pg_catalog.has_column_privilege(
          r.oid, pg_catalog.to_regclass('public.empire_crm_login_credentials'),
          'failed_attempts', 'UPDATE'
        ),false)
        AND NOT coalesce(pg_catalog.has_column_privilege(
          r.oid, pg_catalog.to_regclass('public.empire_crm_login_credentials'),
          'evidence_ref','UPDATE'
        ),false)
        AND NOT coalesce(pg_catalog.has_table_privilege(
          r.oid, pg_catalog.to_regclass('public.empire_crm_tenant_memberships'),'SELECT'
        ),false)
        AND NOT coalesce(pg_catalog.has_function_privilege(
          r.oid, pg_catalog.to_regprocedure('public.empire_crm_read_member(text,uuid)'),
          'EXECUTE'
        ),false)
    ) AS auth_role_restricted_grants_verified,
    EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles r
      WHERE r.rolname='empire_crm_membership_login'
        AND coalesce(pg_catalog.has_function_privilege(
          r.oid, pg_catalog.to_regprocedure('public.empire_crm_read_member(text,uuid)'),
          'EXECUTE'
        ),false)
        AND NOT coalesce(pg_catalog.has_table_privilege(
          r.oid, pg_catalog.to_regclass('public.empire_crm_login_credentials'),'SELECT'
        ),false)
        AND NOT coalesce(pg_catalog.has_table_privilege(
          r.oid, pg_catalog.to_regclass('public.empire_crm_tenant_memberships'),'SELECT'
        ),false)
    ) AS membership_role_restricted_grants_verified,
    EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname='empire_crm_auth_login'
        AND rolcanlogin AND NOT rolinherit
        AND NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication)
    ) AS dedicated_auth_login_role_present,
    EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname='empire_crm_membership_login'
        AND rolcanlogin AND NOT rolinherit
        AND NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication)
    ) AS dedicated_membership_login_role_present,
    (
      SELECT count(*) FROM pg_catalog.pg_roles r
      WHERE r.rolname ~ '^empire_crm_tenant_[0-9a-f]{12,32}$'
        AND r.rolcanlogin AND NOT r.rolinherit
        AND NOT (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole
                 OR r.rolcreatedb OR r.rolreplication)
        AND pg_catalog.pg_has_role(
          r.oid, 'empire_revenue_crm_reader'::pg_catalog.regrole, 'MEMBER'
        )
        AND NOT pg_catalog.pg_has_role(
          r.oid, 'empire_revenue_crm_reader'::pg_catalog.regrole, 'USAGE'
        )
        AND NOT EXISTS (
          SELECT 1 FROM pg_catalog.pg_roles other
          WHERE other.oid <> r.oid
            AND other.rolname <> 'empire_revenue_crm_reader'
            AND pg_catalog.pg_has_role(r.oid, other.oid, 'MEMBER')
        )
    ) AS dedicated_reader_login_role_count
),
summary AS (
 SELECT *,
   CASE
     WHEN NOT canonical_database THEN 'WRONG_DATABASE_STOP'
     WHEN NOT crm_040_views_present OR NOT crm_041_membership_schema_present
       THEN 'RECONCILE_CRM040_CRM041_STOP'
     WHEN NOT crm_042_login_schema_present
       THEN 'FOUNDER_APPROVAL_REQUIRED_FOR_CRM042_SCHEMA'
     WHEN auth_identity_role_staged_nologin
       AND membership_identity_role_staged_nologin
       AND auth_role_restricted_grants_verified
       AND membership_role_restricted_grants_verified
       THEN 'FOUNDER_GATE_DEDICATED_LOGIN_CREDENTIALS_AND_TENANT_PROOF'
     WHEN auth_identity_role_staged_nologin
       OR membership_identity_role_staged_nologin
       THEN 'RECONCILE_INCOMPLETE_IDENTITY_ROLE_PRIVILEGES'
     WHEN NOT dedicated_auth_login_role_present
       OR NOT dedicated_membership_login_role_present
       THEN 'RECONCILE_OR_PREPARE_DEDICATED_IDENTITY_ROLES'
     WHEN dedicated_reader_login_role_count=0
       THEN 'PROVISION_FIRST_EVIDENCED_TENANT_READER_LOGIN'
     ELSE 'VERIFY_TENANT_BINDINGS_AND_REAL_USER_MEMBERSHIP'
   END AS next_action
 FROM observed
)
SELECT pg_catalog.jsonb_pretty(pg_catalog.jsonb_build_object(
    'schema', 'empire.crm.pilot_catalog_readiness.v1',
    'mode', 'OBSERVE',
    'catalog_read_only', true,
    'customer_rows_read', false,
    'role_changes_performed', false,
    'crm_http_activated', false,
    'credentials_logged', false,
    'canonical_database', canonical_database,
    'crm_040_views_present', crm_040_views_present,
    'crm_041_membership_schema_present', crm_041_membership_schema_present,
    'crm_042_login_schema_present', crm_042_login_schema_present,
    'auth_identity_role_staged_nologin', auth_identity_role_staged_nologin,
    'membership_identity_role_staged_nologin', membership_identity_role_staged_nologin,
    'auth_role_restricted_grants_verified', auth_role_restricted_grants_verified,
    'membership_role_restricted_grants_verified', membership_role_restricted_grants_verified,
    'dedicated_auth_login_role_present', dedicated_auth_login_role_present,
    'dedicated_membership_login_role_present',
       dedicated_membership_login_role_present,
    'dedicated_reader_login_role_count', dedicated_reader_login_role_count,
    'tenant_binding_evidence_verified', false,
    'independent_http_identity_verified', false,
    'live_cross_tenant_proof', false,
    'next_action', next_action
)) AS crm_pilot_readiness
FROM summary;
ROLLBACK;
