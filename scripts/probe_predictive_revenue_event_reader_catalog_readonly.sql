-- Read-only catalog-only preflight of the *existing planned* EmpireDB
-- single recognized-event reader.  No source records, secrets, writes,
-- role changes, migrations or financial claims.
-- Run with an authorised existing administrator/session, e.g.
-- sudo -u postgres psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb -f scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql
-- Read-only BEGIN ensures this cannot be repurposed into activation.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5000ms';
WITH
  capability AS (
    SELECT oid,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,
           rolcreatedb,rolreplication
      FROM pg_catalog.pg_roles
     WHERE rolname='empire_predictive_revenue_evidence_reader'
  ),
  source_func AS (
    SELECT oid,prosecdef,provolatile,proconfig,
           proowner,proacl
      FROM pg_catalog.pg_proc
     WHERE oid=pg_catalog.to_regprocedure(
       'public.read_predictive_revenue_event_v1(uuid,text)')
  ),
  migrator AS (
    SELECT oid
      FROM pg_catalog.pg_roles
     WHERE rolname='empiredb_migrator'
  ),
  input_tables AS (
    SELECT source_name,
           pg_catalog.to_regclass(source_name) AS source_oid
    FROM (VALUES
      ('public.commercial_events'),
      ('public.fulfilment_orders'),
      ('public.buyers')
    ) AS s(source_name)
  ),
  direct_privileges AS (
    SELECT pg_catalog.has_table_privilege(
                 (SELECT oid FROM capability),
                 input_tables.source_oid,privilege) AS granted
      FROM input_tables CROSS JOIN
           (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE'),
                   ('TRUNCATE'),('REFERENCES'),('TRIGGER')) AS g(privilege)
     WHERE input_tables.source_oid IS NOT NULL
  ),
  function_acl AS (
    SELECT entry.grantee,entry.privilege_type
      FROM source_func f
      CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))
      ) AS entry
  ),
  role_users AS (
    SELECT member.oid,member.rolname,member.rolcanlogin,member.rolsuper,
           member.rolbypassrls,member.rolcreaterole,member.rolcreatedb,
           grants.set_option AS can_set_role
      FROM pg_catalog.pg_auth_members grants
      JOIN pg_catalog.pg_roles member ON member.oid=grants.member
     WHERE grants.roleid=(SELECT oid FROM capability)
  ),
  facts AS (
    SELECT
      current_database()='empiredb' AS correct_database,
      EXISTS (SELECT 1 FROM capability) AS capability_exists,
      COALESCE((SELECT NOT rolcanlogin AND NOT rolsuper
                       AND NOT rolbypassrls AND NOT rolcreaterole
                       AND NOT rolcreatedb AND NOT rolreplication
                  FROM capability),false) AS capability_no_login_no_admin,
      EXISTS (SELECT 1 FROM source_func) AS function_exists,
      COALESCE((SELECT prosecdef AND provolatile='s'
                       AND 'search_path='=ANY(proconfig)
                  FROM source_func),false) AS function_security_definer_stable_locked_path,
      COALESCE((SELECT proowner=(SELECT oid FROM migrator)
                  FROM source_func),false) AS function_owned_by_migrator,
      COALESCE((SELECT pg_catalog.has_function_privilege(
                     (SELECT oid FROM capability),f.oid,'EXECUTE')
                  FROM source_func f),false) AS capability_can_execute,
      NOT EXISTS (SELECT 1 FROM function_acl
                   WHERE grantee=0 AND privilege_type='EXECUTE')
          AND EXISTS (SELECT 1 FROM source_func) AS public_execute_denied,
      (SELECT COUNT(*)=3
         FROM input_tables
        WHERE source_oid IS NOT NULL) AS all_three_source_tables_exist,
      NOT EXISTS(SELECT 1 FROM direct_privileges WHERE granted IS TRUE)
          AND EXISTS (SELECT 1 FROM capability) AS role_has_no_direct_source_table_grants,
      pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NOT NULL
          AS canonical_session_tenant_resolver_exists,
      EXISTS(SELECT 1 FROM role_users)
          AS dedicated_login_member_exists,
      NOT EXISTS (
        SELECT 1 FROM role_users
         WHERE NOT rolcanlogin OR rolsuper OR rolbypassrls
            OR rolcreatedb OR rolcreaterole
      ) AND EXISTS(SELECT 1 FROM role_users)
          AS login_members_are_nonadmin,
      NOT EXISTS(SELECT 1 FROM role_users WHERE can_set_role IS NOT TRUE)
          AND EXISTS(SELECT 1 FROM role_users)
          AS login_members_can_set_capability_role,
      NOT EXISTS (
        SELECT 1 FROM role_users
         WHERE rolname='empiredb_app' OR rolname='empiredb_migrator'
      ) AND EXISTS(SELECT 1 FROM role_users)
          AS privileged_existing_logins_not_reused
  )
SELECT pg_catalog.jsonb_build_object(
  'schema_version','empire.predictive_revenue.reader_catalog_preflight.v1',
  'status',
    CASE WHEN
      correct_database AND capability_exists
      AND capability_no_login_no_admin AND function_exists
      AND function_security_definer_stable_locked_path
      AND function_owned_by_migrator AND capability_can_execute
      AND public_execute_denied AND all_three_source_tables_exist
      AND role_has_no_direct_source_table_grants
      AND canonical_session_tenant_resolver_exists
      AND dedicated_login_member_exists AND login_members_are_nonadmin
      AND login_members_can_set_capability_role
      AND privileged_existing_logins_not_reused
      THEN 'CATALOG_PREREQUISITES_PRESENT_NOT_EVENT_PROVEN'
      ELSE 'HOLD_EVENT_READER_CATALOG_NOT_PROVEN'
    END,
  'correct_database',correct_database,
  'capability_exists',capability_exists,
  'capability_no_login_no_admin',capability_no_login_no_admin,
  'function_exists',function_exists,
  'function_security_definer_stable_locked_path',
    function_security_definer_stable_locked_path,
  'function_owned_by_migrator',function_owned_by_migrator,
  'capability_can_execute',capability_can_execute,
  'public_execute_denied',public_execute_denied,
  'all_three_source_tables_exist',all_three_source_tables_exist,
  'role_has_no_direct_source_table_grants',
    role_has_no_direct_source_table_grants,
  'canonical_session_tenant_resolver_exists',
    canonical_session_tenant_resolver_exists,
  'dedicated_login_member_exists',dedicated_login_member_exists,
  'login_members_are_nonadmin',login_members_are_nonadmin,
  'login_members_can_set_capability_role',login_members_can_set_capability_role,
  'privileged_existing_logins_not_reused',
    privileged_existing_logins_not_reused,
  'function_body_independently_security_reviewed',false,
  'dedicated_login_exercised_with_authenticated_tenant',false,
  'canonical_event_fetched',false,
  'payment_settlement_verified',false,
  'daily_revenue_census_verified',false,
  'customer_report_release_authorized',false,
  'rows_read_from_financial_source_tables',0,
  'execution_authority','none',
  'mode','OBSERVE'
)::text
FROM facts;
ROLLBACK;
