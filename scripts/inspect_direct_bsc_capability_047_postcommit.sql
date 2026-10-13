-- READ ONLY: diagnose the nine checks which HELD AFTER COMMIT of EmpireDB 047.
-- This file NEVER creates/modifies objects, roles, policies or data.
-- Run as the OS postgres user with psql -X -v ON_ERROR_STOP=1 -d empiredb -f ...
\set ON_ERROR_STOP on
\pset pager off
\pset format aligned
BEGIN READ ONLY;
SET LOCAL statement_timeout='5000ms';

SELECT current_database() AS database,
       current_user AS catalog_reader,
       pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities') IS NOT NULL
         AS migration_047_table_exists,
       pg_catalog.to_regprocedure('public.guard_direct_bsc_buyer_capability()') IS NOT NULL
         AS guard_function_exists;

WITH checks(check_name, passed) AS (
 VALUES
 ('01_table_exists',
    pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities') IS NOT NULL),
 ('02_forced_rls',
    COALESCE((SELECT c.relrowsecurity AND c.relforcerowsecurity
    FROM pg_catalog.pg_class c
    WHERE c.oid=pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities')),FALSE)),
 ('03_app_select_denied',
    NOT pg_catalog.has_table_privilege(
      'empiredb_app','public.direct_bsc_buyer_capabilities','SELECT')),
 ('04_payment_approver_select_denied',
    NOT pg_catalog.has_table_privilege(
      'empire_payment_approver','public.direct_bsc_buyer_capabilities','SELECT')),
 ('05_bsc_verifier_select_denied',
    NOT pg_catalog.has_table_privilege(
      'empire_bsc_verifier','public.direct_bsc_buyer_capabilities','SELECT')),
 ('06_zero_rls_policies',
    NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
      WHERE p.polrelid=pg_catalog.to_regclass(
        'public.direct_bsc_buyer_capabilities'))),
 ('07_guard_security_definer_owned_by_migrator',
    EXISTS (SELECT 1 FROM pg_catalog.pg_proc f
      JOIN pg_catalog.pg_roles owner ON owner.oid=f.proowner
      WHERE f.oid=pg_catalog.to_regprocedure(
        'public.guard_direct_bsc_buyer_capability()')
        AND f.prosecdef AND owner.rolname='empiredb_migrator')),
 ('08_guard_public_execute_denied',
    NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc f
      CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))) acl
      WHERE f.oid=pg_catalog.to_regprocedure(
        'public.guard_direct_bsc_buyer_capability()')
        AND acl.grantee=0)),
 ('09_bound_trigger_enabled',
    EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t
      WHERE t.tgrelid=pg_catalog.to_regclass(
        'public.direct_bsc_buyer_capabilities')
        AND t.tgname='direct_bsc_buyer_capability_guard'
        AND t.tgenabled='O'))
)
SELECT check_name, CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END AS result
FROM checks ORDER BY check_name;

-- Object ownership, grants and policies only. No customer records.
SELECT c.relname,
       owner.rolname AS table_owner,
       c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS rls_forced,
       COALESCE((SELECT count(*) FROM pg_catalog.pg_policy p
                 WHERE p.polrelid=c.oid),0) AS policy_count
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_roles owner ON owner.oid=c.relowner
WHERE c.oid=pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities');

SELECT COALESCE(grantee.rolname,'PUBLIC') AS granted_to,
       acl.privilege_type,
       acl.is_grantable
FROM pg_catalog.pg_class c
CROSS JOIN LATERAL pg_catalog.aclexplode(
    COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) acl
LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=acl.grantee
WHERE c.oid=pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities')
ORDER BY 1,2;

SELECT COALESCE(grantee.rolname,'PUBLIC') AS function_granted_to,
       acl.privilege_type,
       acl.is_grantable
FROM pg_catalog.pg_proc f
CROSS JOIN LATERAL pg_catalog.aclexplode(
    COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))) acl
LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=acl.grantee
WHERE f.oid=pg_catalog.to_regprocedure(
  'public.guard_direct_bsc_buyer_capability()')
ORDER BY 1,2;

-- Existing default table grants can explain unexpected post-commit access.
SELECT owner.rolname AS default_grant_owner,
       COALESCE(ns.nspname,'<global>') AS schema_scope,
       COALESCE(grantee.rolname,'PUBLIC') AS grantee,
       acl.privilege_type
FROM pg_catalog.pg_default_acl d
JOIN pg_catalog.pg_roles owner ON owner.oid=d.defaclrole
LEFT JOIN pg_catalog.pg_namespace ns ON ns.oid=d.defaclnamespace
CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) acl
LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=acl.grantee
WHERE d.defaclobjtype='r' AND owner.rolname='empiredb_migrator'
ORDER BY 1,2,3,4;
ROLLBACK;
