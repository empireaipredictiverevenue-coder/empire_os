-- EmpireOS founder pilot: independently inspect the ONE existing tenant.
-- Read-only evidence for internal operator registration; never proves a
-- human founder login, authorises membership, or establishes business ownership.
-- No role names, source refs, account subjects/emails, raw entity rows or secrets.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5000ms';
DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb', 'crm_membership_fixture') THEN
    RAISE EXCEPTION 'not canonical CRM database';
  END IF;
  IF to_regclass('public.empire_tenant_role_bindings') IS NULL
    OR to_regclass('public.tenant_business_entity_bindings') IS NULL
    OR to_regclass('public.empire_crm_tenant_memberships') IS NULL
    OR to_regclass('public.empire_crm_login_credentials') IS NULL
  THEN
    RAISE EXCEPTION 'founder evidence source missing';
  END IF;
END;
$guard$;
WITH target AS (
  SELECT '708efd4b-53b2-43d7-961d-1cecab67f17a'::uuid AS tenant_id
), role_scope AS (
  SELECT count(*)::int AS all_role_bindings,
    count(*) FILTER (
      WHERE b.active AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
    )::int AS active_evidenced_role_bindings,
    count(*) FILTER (
      WHERE b.role_name = 'empire_intelligence_materializer_login'
        AND b.active AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
        AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
    )::int AS operational_materializer_bindings,
    min(b.created_at) AS earliest_role_binding_created_at
  FROM public.empire_tenant_role_bindings b
  LEFT JOIN pg_catalog.pg_roles r ON r.rolname = b.role_name
  WHERE b.tenant_id=(SELECT tenant_id FROM target)
), entity_scope AS (
  SELECT count(*)::int AS all_entity_bindings,
    count(*) FILTER (
      WHERE b.active AND b.valid_from <= now()
        AND (b.valid_until IS NULL OR b.valid_until > now())
        AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
    )::int AS active_evidenced_entity_bindings,
    count(*) FILTER (
      WHERE b.active AND b.valid_from <= now()
        AND (b.valid_until IS NULL OR b.valid_until > now())
        AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
        AND b.binding_kind='observed'
    )::int AS observed_bindings,
    count(*) FILTER (
      WHERE b.active AND b.valid_from <= now()
        AND (b.valid_until IS NULL OR b.valid_until > now())
        AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
        AND b.binding_kind='owned'
    )::int AS owned_bindings,
    count(*) FILTER (
      WHERE b.active AND b.valid_from <= now()
        AND (b.valid_until IS NULL OR b.valid_until > now())
        AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
        AND b.binding_kind='managed'
    )::int AS managed_bindings,
    min(b.created_at) AS earliest_entity_binding_created_at
  FROM public.tenant_business_entity_bindings b
  WHERE b.tenant_id=(SELECT tenant_id FROM target)
), member_scope AS (
  SELECT count(*)::int AS memberships,
    count(*) FILTER (
      WHERE status='active' AND revoked_at IS NULL
        AND verified_at <= now()
        AND (valid_until IS NULL OR valid_until > now())
        AND nullif(btrim(evidence_ref),'') IS NOT NULL
    )::int AS active_memberships,
    -- Membership rows remain account-identity evidence, never proof of
    -- independently authenticated human control of an email or company.
    count(*) FILTER (
      WHERE subject='founder:phil_livesley'
        AND role='owner' AND status='pending'
        AND revoked_at IS NULL
        AND verified_at <= now()
        AND (valid_until IS NULL OR valid_until > now())
        AND evidence_ref LIKE
          'founder:chat-approved-single-owner-20261010|identity:connected-gmail-profile-reviewed-ownership-pending|tenant:operator-evidence-only-not-legal-proof'
    )::int AS exact_pending_owner_memberships
  FROM public.empire_crm_tenant_memberships
  WHERE tenant_id=(SELECT tenant_id FROM target)
), credential_scope AS (
  SELECT count(*)::int AS credential_records
  FROM public.empire_crm_login_credentials
  WHERE invitation_tenant_id=(SELECT tenant_id FROM target)
)
SELECT jsonb_pretty(jsonb_build_object(
  'schema','empire.crm.founder_existing_tenant_evidence.v1',
  'mode','OBSERVE',
  'canonical_database',current_database()='empiredb',
  'query_transaction_read_only',current_setting('transaction_read_only')='on',
  'tenant_id',(SELECT tenant_id FROM target),
  'candidate_only',true,
  'role_binding_count',r.all_role_bindings,
  'active_evidenced_role_bindings',r.active_evidenced_role_bindings,
  'operational_materializer_bindings',r.operational_materializer_bindings,
  'earliest_role_binding_created_at',r.earliest_role_binding_created_at,
  'entity_binding_count',e.all_entity_bindings,
  'active_evidenced_entity_bindings',e.active_evidenced_entity_bindings,
  'active_observed_entity_bindings',e.observed_bindings,
  'active_owned_entity_bindings',e.owned_bindings,
  'active_managed_entity_bindings',e.managed_bindings,
  'earliest_entity_binding_created_at',e.earliest_entity_binding_created_at,
  'crm_memberships',m.memberships,
  'active_crm_memberships',m.active_memberships,
  'pending_owner_membership_count',m.exact_pending_owner_memberships,
  'single_approved_pending_owner_recorded',
    (m.memberships=1 AND m.exact_pending_owner_memberships=1
     AND m.active_memberships=0 AND c.credential_records=0),
  'crm_credential_records',c.credential_records,
  'human_founder_identity_verified',false,
  'founder_to_tenant_membership_verified',false,
  'tenant_key_independently_verified',false,
  'pilot_activation_authorized',false,
  'logins_enabled_by_this_probe',false,
  'writes_performed',false,
  'next_action', CASE
     WHEN m.memberships=1 AND m.exact_pending_owner_memberships=1
       AND m.active_memberships=0 AND c.credential_records=0
       THEN 'VERIFY_HUMAN_AND_TENANT_CONTROL_BEFORE_SEPARATE_ACTIVE_MEMBERSHIP_APPROVAL'
     WHEN m.memberships=0 AND c.credential_records=0
       THEN 'REVIEW_INDEPENDENT_FOUNDER_AND_TENANT_EVIDENCE_BEFORE_FIRST_PENDING_MEMBER'
     ELSE 'RECONCILE_CRM_MEMBERSHIP_AND_CREDENTIAL_STATE_WITHOUT_ACTIVATION'
   END
))
FROM role_scope r CROSS JOIN entity_scope e
  CROSS JOIN member_scope m CROSS JOIN credential_scope c;
ROLLBACK;
