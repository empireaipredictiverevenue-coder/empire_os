-- One-time founder-approved CRM membership preparation; existing internal tenant.
-- This is NOT an independently verified human/tenant ownership claim.
-- PENDING owner, NOT ACTIVE. No login, invite, tenant-reader grant or API.
-- For use only by the guarded, backed-up operator deployment.
BEGIN;
SET LOCAL statement_timeout='10000ms';
SET LOCAL lock_timeout='2500ms';
LOCK TABLE public.empire_crm_tenant_memberships IN SHARE ROW EXCLUSIVE MODE;
DO $guard$
DECLARE
  tenant constant uuid := '708efd4b-53b2-43d7-961d-1cecab67f17a';
  principal constant text := 'founder:phil_livesley';
  proof constant text :=
    'founder:chat-approved-single-owner-20261010'
    ||'|identity:connected-gmail-profile-reviewed-ownership-pending'
    ||'|tenant:operator-evidence-only-not-legal-proof';
BEGIN
  IF current_database() NOT IN ('empiredb','crm_membership_fixture')
     OR session_user <> 'postgres'
  THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=CANONICAL_POSTGRES_OPERATOR_REQUIRED';
  END IF;
  IF to_regclass('public.empire_crm_tenant_memberships') IS NULL
     OR to_regclass('public.empire_crm_login_credentials') IS NULL
     OR to_regclass('public.empire_tenant_role_bindings') IS NULL
     OR to_regclass('public.tenant_business_entity_bindings') IS NULL
  THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=CANONICAL_SCHEMA_REQUIRED';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_authid
      WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
      AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
      AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
      AND NOT rolreplication AND rolpassword IS NULL) <> 2
  THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=CRM_IDENTITY_ROLES_NOT_DORMANT';
  END IF;
  IF (SELECT count(*) FROM public.empire_tenant_role_bindings b
      JOIN pg_catalog.pg_roles r ON r.rolname=b.role_name
      WHERE b.tenant_id=tenant
        AND b.role_name='empire_intelligence_materializer_login'
        AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
        AND b.active AND nullif(btrim(b.evidence_ref),'') IS NOT NULL) <> 1
  THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=INTERNAL_OPERATOR_TENANT_NOT_EVIDENCED';
  END IF;
  -- All four earlier bindings were OBSERVED, not owned or managed.
  -- These prove an existing internal operator scope, not a founder identity.
  IF (SELECT count(*) FROM public.tenant_business_entity_bindings b
      WHERE b.tenant_id=tenant
        AND b.active AND b.binding_kind='observed'
        AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
        AND b.valid_from <= now()
        AND (b.valid_until IS NULL OR b.valid_until > now())) <> 4
     OR EXISTS (
       SELECT 1 FROM public.tenant_business_entity_bindings b
       WHERE b.tenant_id=tenant AND b.active
         AND b.binding_kind IN ('owned','managed')
     )
  THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=EXPECTED_OPERATOR_BINDINGS_DRIFTED';
  END IF;
  IF EXISTS (SELECT 1 FROM public.empire_crm_tenant_memberships)
     OR EXISTS (SELECT 1 FROM public.empire_crm_login_credentials)
  THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=ACCOUNT_OR_MEMBERSHIP_ALREADY_EXISTS';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc
    WHERE oid=to_regprocedure('public.empire_crm_read_member(text,uuid)')
  ) THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=CANONICAL_MEMBER_READER_MISSING';
  END IF;

  -- Existing 041 schema requires verified_at even for PENDING. This is the
  -- date of the founder-approved OPERATOR REVIEW, not human authentication.
  INSERT INTO public.empire_crm_tenant_memberships
    (tenant_id,subject,role,status,evidence_ref,verified_at,valid_until,revoked_at)
  VALUES
    (tenant,principal,'owner','pending',proof,clock_timestamp(),NULL,NULL);

  IF (SELECT count(*) FROM public.empire_crm_tenant_memberships
      WHERE tenant_id=tenant AND subject=principal AND role='owner'
        AND status='pending' AND revoked_at IS NULL
        AND evidence_ref=proof) <> 1
  THEN
    RAISE EXCEPTION 'CRM_OWNER=BLOCKED reason=INSERT_READBACK_MISMATCH';
  END IF;
END;
$guard$;
SELECT jsonb_build_object(
  'schema','empire.crm.founder_single_pending_member.v1',
  'canonical_database',current_database()='empiredb',
  'operator',current_user,
  'tenant_id','708efd4b-53b2-43d7-961d-1cecab67f17a',
  'subject','founder:phil_livesley',
  'role','owner',
  'member_status','pending',
  'total_memberships',(SELECT count(*) FROM public.empire_crm_tenant_memberships),
  'active_memberships',(SELECT count(*) FROM public.empire_crm_tenant_memberships WHERE status='active'),
  'credential_rows',(SELECT count(*) FROM public.empire_crm_login_credentials),
  'human_identity_verified',false,
  'crm_login_authorized',false,
  'email_sent',false,
  'public_api_activated',false
);
COMMIT;
