-- Post-049 independent catalogue-only verification, no customer rows.
-- Execution as postgres on canonical EmpireDB after SEPARATE approval.
\set ON_ERROR_STOP on
\pset pager off
\pset format unaligned
\pset fieldsep '|'
BEGIN READ ONLY;
SET LOCAL statement_timeout='4500ms';
WITH
 roles AS (
   SELECT rolname,oid,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
          rolcreaterole,rolreplication,rolbypassrls
   FROM pg_catalog.pg_roles
   WHERE rolname IN (
     'empire_direct_checkout_status_owner',
     'empire_direct_checkout_status_reader')
 ),
 owner AS (SELECT oid FROM roles WHERE rolname='empire_direct_checkout_status_owner'),
 reader AS (SELECT oid FROM roles WHERE rolname='empire_direct_checkout_status_reader'),
 p AS (
   SELECT f.oid,f.proowner,f.prosecdef,f.provolatile,f.proconfig,f.proacl
   FROM pg_catalog.pg_proc f
   WHERE f.oid=pg_catalog.to_regprocedure(
     'public.read_direct_bsc_buyer_status(text)')
 ),
 c AS (
   SELECT relrowsecurity,relforcerowsecurity,oid
   FROM pg_catalog.pg_class
   WHERE oid=pg_catalog.to_regclass(
     'public.direct_bsc_buyer_capabilities')
 ),
 checks(label,passed) AS (
 VALUES
 ('01_two_nologin_restricted_roles',
   (SELECT count(*)=2 AND bool_and(
      NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
      AND NOT rolcreatedb AND NOT rolcreaterole
      AND NOT rolreplication AND NOT rolbypassrls) FROM roles)),
 ('02_zero_isolated_role_memberships',
   (SELECT count(*)=0
    FROM pg_catalog.pg_auth_members m
    WHERE m.member IN (SELECT oid FROM roles)
       OR m.roleid IN (SELECT oid FROM roles))),
 ('03_capability_forced_rls',
   (SELECT relrowsecurity AND relforcerowsecurity FROM c)),
 ('04_capability_exact_owner_policy',
   (SELECT count(*)=1 FROM pg_catalog.pg_policy pol
    WHERE pol.polrelid=(SELECT oid FROM c)
      AND pol.polname='direct_bsc_status_owner_capability_select'
      AND pol.polroles=ARRAY[(SELECT oid FROM owner)]
      AND pol.polcmd='r' AND pol.polpermissive)
   AND (SELECT count(*)=1 FROM pg_catalog.pg_policy pol
     WHERE pol.polrelid=(SELECT oid FROM c))),
 ('05_three_parent_policies_exact',
   (SELECT count(*)=3 FROM pg_catalog.pg_policy pol
    JOIN pg_catalog.pg_class cl ON cl.oid=pol.polrelid
    WHERE (cl.relname,pol.polname) IN (
      ('fulfilment_orders','direct_bsc_status_owner_orders_select'),
      ('bsc_payment_requests','direct_bsc_status_owner_requests_select'),
      ('bsc_payment_evidence','direct_bsc_status_owner_evidence_select'))
      AND pol.polroles=ARRAY[(SELECT oid FROM owner)]
      AND pol.polcmd='r' AND pol.polpermissive)),
 ('06_parent_policy_counts_preserved_plus_one',
   (SELECT count(*)=3 FROM (
      SELECT c.relname,count(pol.oid)::integer AS n
      FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_policy pol ON pol.polrelid=c.oid
      WHERE c.relnamespace='public'::regnamespace
        AND c.relname IN ('fulfilment_orders','bsc_payment_requests',
                          'bsc_payment_evidence')
      GROUP BY c.relname
    ) totals
    WHERE (relname,n) IN (
       ('fulfilment_orders',24),
       ('bsc_payment_requests',11),
       ('bsc_payment_evidence',10)))),
 ('07_function_isolated_security_definer',
   (SELECT count(*)=1 FROM p
    WHERE proowner=(SELECT oid FROM owner)
      AND prosecdef AND provolatile='s'
      AND proconfig IN (
        ARRAY['search_path=']::text[],
        ARRAY['search_path=""']::text[]))),
 ('08_function_execute_only_reader',
   (SELECT count(*)=1
     FROM p CROSS JOIN LATERAL pg_catalog.aclexplode(
       COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
     WHERE a.grantee=(SELECT oid FROM reader)
       AND a.privilege_type='EXECUTE' AND NOT a.is_grantable)
   AND (SELECT count(*)=0
     FROM p CROSS JOIN LATERAL pg_catalog.aclexplode(
       COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
     WHERE a.grantee NOT IN (
       (SELECT oid FROM owner),(SELECT oid FROM reader)))),
 ('09_existing_app_and_migrator_cannot_execute',
   NOT pg_catalog.has_function_privilege(
     'empiredb_app','public.read_direct_bsc_buyer_status(text)','EXECUTE')
   AND NOT pg_catalog.has_function_privilege(
     'empiredb_migrator_login',
     'public.read_direct_bsc_buyer_status(text)','EXECUTE')),
 ('10_app_and_reader_cannot_select_capability',
   NOT pg_catalog.has_table_privilege(
     'empiredb_app','public.direct_bsc_buyer_capabilities','SELECT')
   AND NOT pg_catalog.has_table_privilege(
     'empire_direct_checkout_status_reader',
     'public.direct_bsc_buyer_capabilities','SELECT')),
 ('11_owner_has_column_select_only',
   pg_catalog.has_column_privilege(
     'empire_direct_checkout_status_owner',
     'public.direct_bsc_buyer_capabilities','token_fingerprint','SELECT')
   AND pg_catalog.has_column_privilege(
     'empire_direct_checkout_status_owner',
     'public.bsc_payment_requests','amount_usdt','SELECT')
   AND NOT pg_catalog.has_table_privilege(
     'empire_direct_checkout_status_owner',
     'public.direct_bsc_buyer_capabilities','SELECT')),
 ('12_existing_migrator_login_still_member',
   (SELECT count(*)=1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles member ON member.oid=m.member
    JOIN pg_catalog.pg_roles target ON target.oid=m.roleid
    WHERE member.rolname='empiredb_migrator_login'
      AND target.rolname='empiredb_migrator'
      AND member.rolcanlogin AND member.rolinherit
      AND m.set_option AND m.inherit_option AND NOT m.admin_option))
 )
 SELECT label,CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END
 FROM checks ORDER BY label;
ROLLBACK;
