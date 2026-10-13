-- Independent read-only postcommit 050 issuer role/policy/function proof.
\set ON_ERROR_STOP on
\pset format unaligned
\pset fieldsep '|'
\pset pager off
BEGIN READ ONLY;
SET LOCAL statement_timeout='4500ms';
WITH
roles AS (
 SELECT rolname,oid,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,
        rolreplication,rolbypassrls FROM pg_catalog.pg_roles
 WHERE rolname IN ('empire_direct_checkout_status_issuer_owner',
                   'empire_direct_checkout_status_issuer')
),
o AS (SELECT oid FROM roles WHERE rolname='empire_direct_checkout_status_issuer_owner'),
caller AS (SELECT oid FROM roles WHERE rolname='empire_direct_checkout_status_issuer'),
p AS (
 SELECT proowner,prosecdef,provolatile,proconfig,proacl FROM pg_catalog.pg_proc
 WHERE oid=pg_catalog.to_regprocedure(
   'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)')
),
checks(label,passed) AS (
 VALUES
 ('01_two_new_roles_nologin',
  (SELECT count(*)=2 AND bool_and(NOT rolcanlogin AND NOT rolinherit
    AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
    AND NOT rolreplication AND NOT rolbypassrls) FROM roles)),
 ('02_no_new_role_membership',
  (SELECT count(*)=0 FROM pg_catalog.pg_auth_members m
   WHERE m.member IN (SELECT oid FROM roles)
      OR m.roleid IN (SELECT oid FROM roles))),
 ('03_issuer_isolated_security_definer',
  (SELECT count(*)=1 FROM p
   WHERE proowner=(SELECT oid FROM o) AND prosecdef AND provolatile='v'
     AND EXISTS (SELECT 1 FROM pg_catalog.unnest(proconfig) setting
                 WHERE setting IN ('search_path=','search_path=""')))),
 ('04_function_execute_acl_sealed',
  (SELECT count(*)=1 FROM p
   CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
   WHERE a.grantee=(SELECT oid FROM caller)
     AND a.privilege_type='EXECUTE' AND NOT a.is_grantable)
   AND (SELECT count(*)=0 FROM p
   CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
   WHERE a.grantee NOT IN ((SELECT oid FROM o),(SELECT oid FROM caller)))),
 ('05_only_isolated_owner_insert_policy',
  (SELECT count(*)=1 FROM pg_catalog.pg_policy pol
   WHERE pol.polrelid='public.direct_bsc_buyer_capabilities'::regclass
     AND pol.polname='direct_bsc_status_issuer_capability_insert'
     AND pol.polcmd='a' AND pol.polpermissive
     AND pol.polroles=ARRAY[(SELECT oid FROM o)])),
 ('06_only_isolated_owner_payment_request_select_policy',
  (SELECT count(*)=1 FROM pg_catalog.pg_policy pol
   WHERE pol.polrelid='public.bsc_payment_requests'::regclass
     AND pol.polname='direct_bsc_status_issuer_request_select'
     AND pol.polcmd='r' AND pol.polpermissive
     AND pol.polroles=ARRAY[(SELECT oid FROM o)])),
 ('07_exact_post_050_policy_counts',
  (SELECT count(*)=2 FROM pg_catalog.pg_policy
   WHERE polrelid='public.direct_bsc_buyer_capabilities'::regclass)
   AND (SELECT count(*)=12 FROM pg_catalog.pg_policy
   WHERE polrelid='public.bsc_payment_requests'::regclass)),
 ('08_old_reader_cannot_issue',
  NOT pg_catalog.has_function_privilege(
    'empire_direct_checkout_status_reader',
    'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)',
    'EXECUTE')),
 ('09_app_and_migrator_cannot_issue',
  NOT pg_catalog.has_function_privilege(
    'empiredb_app',
    'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)',
    'EXECUTE') AND NOT pg_catalog.has_function_privilege(
    'empiredb_migrator_login',
    'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)',
    'EXECUTE')),
 ('10_column_scoped_owner_and_no_caller_table_insert',
  pg_catalog.has_column_privilege(
    'empire_direct_checkout_status_issuer_owner',
    'public.direct_bsc_buyer_capabilities','token_fingerprint','INSERT')
   AND NOT pg_catalog.has_table_privilege(
    'empire_direct_checkout_status_issuer_owner',
    'public.direct_bsc_buyer_capabilities','INSERT')
   AND NOT pg_catalog.has_table_privilege(
    'empire_direct_checkout_status_issuer',
    'public.direct_bsc_buyer_capabilities','INSERT'))
)
SELECT label,CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END
FROM checks ORDER BY label;
ROLLBACK;
