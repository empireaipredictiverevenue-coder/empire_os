-- EmpireDB 048: corrective ACL removal on 047's SEALED table ONLY.
-- PREPARED ONLY — needs separate explicit founder approval.
-- Preserve all existing ALTER DEFAULT PRIVILEGES, applications, and all roles.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
DECLARE
  v_acl text[];
  v_expected text[] := ARRAY[
    'empiredb_app:DELETE','empiredb_app:INSERT',
    'empiredb_app:SELECT','empiredb_app:UPDATE',
    'empiredb_readonly:SELECT'
  ];
BEGIN
  IF current_database() NOT IN ('empiredb','direct_bsc_capability_fixture')
    OR current_user <> 'empiredb_migrator'
  THEN
    RAISE EXCEPTION 'DIRECT048_WRONG_DATABASE_OR_MIGRATOR';
  END IF;
  IF pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities') IS NULL
     OR pg_catalog.to_regprocedure(
         'public.guard_direct_bsc_buyer_capability()') IS NULL
  THEN
    RAISE EXCEPTION 'DIRECT048_ORIGINAL_047_OBJECTS_MISSING';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::regclass
      AND o.rolname='empiredb_migrator'
      AND c.relrowsecurity AND c.relforcerowsecurity
      AND (SELECT count(*) FROM pg_catalog.pg_policy p
           WHERE p.polrelid=c.oid)=0
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc f
    JOIN pg_catalog.pg_roles o ON o.oid=f.proowner
    WHERE f.oid=pg_catalog.to_regprocedure(
       'public.guard_direct_bsc_buyer_capability()')
      AND f.prosecdef AND o.rolname='empiredb_migrator'
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_trigger t
    WHERE t.tgrelid='public.direct_bsc_buyer_capabilities'::regclass
      AND t.tgname='direct_bsc_buyer_capability_guard'
      AND t.tgenabled='O'
  ) THEN
    RAISE EXCEPTION 'DIRECT048_SEAL_OR_FUNCTION_TRIGGER_DRIFT';
  END IF;

  -- In particular, reject unexpected grantees/GRANT OPTION/PUBLIC.
  -- Owner's own privileges are not part of the repair.
  SELECT pg_catalog.array_agg(
    COALESCE(grantee.rolname,'PUBLIC') || ':' || a.privilege_type
    ORDER BY COALESCE(grantee.rolname,'PUBLIC'),a.privilege_type
  ) INTO v_acl
  FROM pg_catalog.pg_class c
  CROSS JOIN LATERAL pg_catalog.aclexplode(
    COALESCE(c.relacl, pg_catalog.acldefault('r',c.relowner))
  ) a
  LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=a.grantee
  WHERE c.oid='public.direct_bsc_buyer_capabilities'::regclass
    AND a.grantee<>c.relowner
    AND NOT a.is_grantable;

  -- A separate check catches any granted grant-option privilege, which the
  -- above deliberately excludes from the no-GRANT-OPTION snapshot.
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(c.relacl, pg_catalog.acldefault('r',c.relowner))) a
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::regclass
      AND a.grantee<>c.relowner AND a.is_grantable
  ) OR v_acl IS DISTINCT FROM v_expected
  THEN
    RAISE EXCEPTION 'DIRECT048_EXACT_EXISTING_GRANTS_DRIFT';
  END IF;
END
$guard$;

-- Only this 047 table. Default privileges on other EmpireDB objects are
-- deliberately preserved; no other object, role or privilege is touched.
REVOKE ALL PRIVILEGES ON TABLE public.direct_bsc_buyer_capabilities
  FROM empiredb_app, empiredb_readonly;

DO $verify$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::regclass
      AND a.grantee<>c.relowner
  ) OR pg_catalog.has_table_privilege(
      'empiredb_app','public.direct_bsc_buyer_capabilities','SELECT,INSERT,UPDATE,DELETE'
  ) OR pg_catalog.has_table_privilege(
      'empiredb_readonly','public.direct_bsc_buyer_capabilities','SELECT'
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::regclass
      AND c.relrowsecurity AND c.relforcerowsecurity
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_policy p
    WHERE p.polrelid='public.direct_bsc_buyer_capabilities'::regclass
  ) THEN
    RAISE EXCEPTION 'DIRECT048_SEALED_ACL_POSTCHECK_FAIL';
  END IF;
END
$verify$;
COMMIT;
