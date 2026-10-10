-- One-time, founder-approved production change: exactly one existing
-- owner CRM membership pending -> active. NO LOGIN, credential, grant, email,
-- invitation, API activation, payment, outbound or company-ownership assertion.
-- Operator must independently verify current authoritative DNS challenge and
-- Gmail challenge completion before invoking this single transaction.
BEGIN;
SET LOCAL statement_timeout='10000ms';
SET LOCAL lock_timeout='2500ms';
LOCK TABLE public.empire_crm_tenant_memberships IN SHARE ROW EXCLUSIVE MODE;
DO $activate$
DECLARE
  tenant constant uuid := '708efd4b-53b2-43d7-961d-1cecab67f17a';
  person constant text := 'founder:phil_livesley';
  original_evidence constant text :=
    'founder:chat-approved-single-owner-20261010'
    ||'|identity:connected-gmail-profile-reviewed-ownership-pending'
    ||'|tenant:operator-evidence-only-not-legal-proof';
  activation_evidence constant text :=
    '|founder:chat-approved-pending-to-active-20261010'
    ||'|mailbox:challenge-confirmed-20261010'
    ||'|dns:two-authoritative-nameservers-confirmed-20261010';
  affected integer;
BEGIN
  IF current_database() NOT IN ('empiredb','crm_membership_fixture')
    OR session_user <> 'postgres'
  THEN
    RAISE EXCEPTION 'CRM_FOUNDER_ACTIVE=BLOCKED reason=CANONICAL_POSTGRES_OPERATOR_REQUIRED';
  END IF;
  IF to_regclass('public.empire_crm_tenant_memberships') IS NULL
    OR to_regclass('public.empire_crm_login_credentials') IS NULL
    OR to_regclass('public.empire_tenant_role_bindings') IS NULL
    OR to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NULL
  THEN
    RAISE EXCEPTION 'CRM_FOUNDER_ACTIVE=BLOCKED reason=CANONICAL_SCHEMA_MISSING';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_authid
    WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
      AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolbypassrls
      AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
      AND rolpassword IS NULL) <> 2
  THEN
    RAISE EXCEPTION 'CRM_FOUNDER_ACTIVE=BLOCKED reason=CRM_IDENTITY_ROLES_NOT_DORMANT';
  END IF;
  IF (SELECT count(*) FROM public.empire_tenant_role_bindings b
      JOIN pg_catalog.pg_roles r ON r.rolname=b.role_name
      WHERE b.tenant_id=tenant
        AND b.role_name='empire_intelligence_materializer_login'
        AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
        AND b.active AND nullif(btrim(b.evidence_ref),'') IS NOT NULL) <> 1
     OR (SELECT count(*) FROM public.empire_tenant_role_bindings
         WHERE tenant_id=tenant) <> 1
  THEN
    RAISE EXCEPTION 'CRM_FOUNDER_ACTIVE=BLOCKED reason=INDEPENDENT_TENANT_OPERATOR_BINDING_DRIFT';
  END IF;
  IF EXISTS (SELECT 1 FROM public.empire_crm_login_credentials)
    OR (SELECT count(*) FROM public.empire_crm_tenant_memberships) <> 1
  THEN
    RAISE EXCEPTION 'CRM_FOUNDER_ACTIVE=BLOCKED reason=CRM_MEMBERSHIP_OR_CREDENTIAL_DRIFT';
  END IF;
  IF (SELECT count(*) FROM public.empire_crm_tenant_memberships
     WHERE tenant_id=tenant AND subject=person
       AND role='owner' AND status='pending'
       AND evidence_ref=original_evidence
       AND verified_at <= now() AND revoked_at IS NULL
       AND valid_until IS NULL) <> 1
  THEN
    RAISE EXCEPTION 'CRM_FOUNDER_ACTIVE=BLOCKED reason=EXACT_PENDING_FOUNDER_EVIDENCE_REQUIRED';
  END IF;
  -- SQL records the founder's separately approved transition and two
  -- verified proof signals, not legal ownership or a completed login.
  UPDATE public.empire_crm_tenant_memberships
  SET status='active',
      evidence_ref=original_evidence||activation_evidence,
      verified_at=clock_timestamp(),
      updated_at=clock_timestamp()
  WHERE tenant_id=tenant AND subject=person
    AND role='owner' AND status='pending'
    AND evidence_ref=original_evidence AND revoked_at IS NULL
    AND valid_until IS NULL;
  GET DIAGNOSTICS affected = ROW_COUNT;
  IF affected <> 1
    OR (SELECT count(*) FROM public.empire_crm_tenant_memberships
        WHERE tenant_id=tenant AND subject=person AND role='owner'
          AND status='active' AND revoked_at IS NULL AND valid_until IS NULL
          AND evidence_ref=original_evidence||activation_evidence) <> 1
    OR (SELECT count(*) FROM public.empire_crm_login_credentials) <> 0
  THEN
    RAISE EXCEPTION 'CRM_FOUNDER_ACTIVE=BLOCKED reason=EXACT_UPDATE_READBACK_FAILED';
  END IF;
END;
$activate$;
SELECT jsonb_build_object(
  'schema','empire.crm.founder_membership_only_activation.v1',
  'mode','GOVERNED_SINGLE_RECORD',
  'canonical_database',current_database()='empiredb',
  'tenant_id','708efd4b-53b2-43d7-961d-1cecab67f17a',
  'subject','founder:phil_livesley',
  'membership_status','active',
  'active_membership_rows',(SELECT count(*) FROM public.empire_crm_tenant_memberships WHERE status='active'),
  'total_membership_rows',(SELECT count(*) FROM public.empire_crm_tenant_memberships),
  'credential_rows',(SELECT count(*) FROM public.empire_crm_login_credentials),
  'dedicated_crm_logins_enabled',false,
  'crm_http_activated',false,
  'email_or_invitation_sent',false,
  'commercial_execution_authority','none',
  'independent_legal_ownership_proven',false
);
COMMIT;
