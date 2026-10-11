-- EmpireOS CRM 3 exact existing login roles: CONNECT-only repair.
-- Founder approved these three logins. NO login/secret/tenant/table/HTTP changes.
-- Run as postgres against canonical empiredb with ON_ERROR_STOP=1.
BEGIN;
SET LOCAL statement_timeout='8s';
SET LOCAL lock_timeout='3s';
DO $before$
DECLARE
  role_count integer;
  bound_count integer;
BEGIN
  IF current_database() <> 'empiredb' OR pg_catalog.pg_is_in_recovery()
     OR session_user <> 'postgres' THEN
    RAISE EXCEPTION 'CRM_CONNECT_BLOCKED_WRONG_DATABASE_OR_OPERATOR';
  END IF;
  SELECT count(*) INTO role_count
  FROM pg_catalog.pg_authid
  WHERE rolname IN (
      'empire_crm_auth_login','empire_crm_membership_login',
      'empire_crm_tenant_708efd4b53b2'
  )
    AND rolcanlogin AND NOT rolinherit AND NOT rolsuper
    AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
    AND NOT rolbypassrls
    AND rolpassword LIKE 'SCRAM-SHA-256$%';
  IF role_count <> 3 THEN
    RAISE EXCEPTION 'CRM_CONNECT_BLOCKED_ROLE_IDENTITY_UNSAFE';
  END IF;
  IF NOT pg_catalog.pg_has_role(
      'empire_crm_tenant_708efd4b53b2',
      'empire_revenue_crm_reader', 'MEMBER')
    OR pg_catalog.pg_has_role(
      'empire_crm_tenant_708efd4b53b2',
      'empire_revenue_crm_reader', 'USAGE')
    OR EXISTS (
       SELECT 1 FROM pg_catalog.pg_auth_members am
       JOIN pg_catalog.pg_roles member ON member.oid=am.member
       WHERE member.rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
    )
    OR EXISTS (
       SELECT 1 FROM pg_catalog.pg_auth_members am
       JOIN pg_catalog.pg_roles member ON member.oid=am.member
       JOIN pg_catalog.pg_roles grp ON grp.oid=am.roleid
       WHERE member.rolname='empire_crm_tenant_708efd4b53b2'
         AND grp.rolname<>'empire_revenue_crm_reader'
    )
  THEN
    RAISE EXCEPTION 'CRM_CONNECT_BLOCKED_UNEXPECTED_ROLE_MEMBERSHIPS';
  END IF;
  SELECT count(*) INTO bound_count
  FROM public.empire_tenant_role_bindings
  WHERE role_name='empire_crm_tenant_708efd4b53b2'
    AND tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'::uuid
    AND active
    AND NULLIF(BTRIM(evidence_ref),'') IS NOT NULL;
  IF bound_count <> 1 OR
     (SELECT count(*) FROM public.empire_tenant_role_bindings
      WHERE role_name='empire_crm_tenant_708efd4b53b2') <> 1
  THEN
    RAISE EXCEPTION 'CRM_CONNECT_BLOCKED_FOUNDER_TENANT_BINDING';
  END IF;
  IF (SELECT count(*) FROM public.empire_crm_tenant_memberships
      WHERE subject='founder:phil_livesley'
        AND tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'::uuid
        AND role='owner' AND status='active'
        AND revoked_at IS NULL
        AND verified_at<=clock_timestamp()
        AND (valid_until IS NULL OR valid_until>clock_timestamp())
        AND NULLIF(BTRIM(evidence_ref),'') IS NOT NULL) <> 1
  THEN
    RAISE EXCEPTION 'CRM_CONNECT_BLOCKED_FOUNDER_MEMBERSHIP';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.rolname IN (
       'empire_crm_auth_login','empire_crm_membership_login',
       'empire_crm_tenant_708efd4b53b2')
      AND pg_catalog.has_database_privilege(r.oid,'empiredb','CONNECT')
  ) THEN
    RAISE EXCEPTION 'CRM_CONNECT_BLOCKED_ALREADY_OR_PARTIALLY_GRANTED';
  END IF;
END
$before$;
GRANT CONNECT ON DATABASE empiredb
  TO empire_crm_auth_login,
     empire_crm_membership_login,
     empire_crm_tenant_708efd4b53b2;
DO $after$
BEGIN
  IF (SELECT count(*)
      FROM pg_catalog.pg_roles r
      WHERE r.rolname IN (
         'empire_crm_auth_login','empire_crm_membership_login',
         'empire_crm_tenant_708efd4b53b2')
        AND pg_catalog.has_database_privilege(r.oid,'empiredb','CONNECT')) <> 3
  THEN
    RAISE EXCEPTION 'CRM_CONNECT_POSTGRANT_READBACK_FAILED';
  END IF;
END
$after$;
COMMIT;
-- Receipt is a constant; caller should independently verify real role logins.
SELECT 'CRM_CONNECT_RESULT=EXACT_THREE_ROLE_CONNECT_GRANT_COMMITTED' AS receipt;
