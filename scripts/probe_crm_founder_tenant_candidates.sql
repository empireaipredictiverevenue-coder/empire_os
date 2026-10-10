-- EmpireOS CRM founder pilot: tenant candidate inventory, OBSERVE ONLY.
-- Never establishes founder ownership. Tenant role & entity bindings are
-- candidate signals, not a human's verified identity or an access grant.
-- Operator read-only invocation after file review:
-- sudo -n -u postgres psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb \
--   -f /srv/empire_os/scripts/probe_crm_founder_tenant_candidates.sql
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5000ms';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','crm_membership_fixture') THEN
   RAISE EXCEPTION 'not canonical CRM database';
 END IF;
 IF to_regclass('public.empire_tenant_role_bindings') IS NULL
    OR to_regclass('public.tenant_business_entity_bindings') IS NULL
    OR to_regclass('public.empire_crm_tenant_memberships') IS NULL
    OR to_regclass('public.empire_crm_login_credentials') IS NULL
 THEN
   RAISE EXCEPTION 'founder pilot candidate data dependencies missing';
 END IF;
END;
$guard$;
WITH role_scope AS (
  SELECT tenant_id,
    count(*)::integer AS role_binding_count,
    count(*) FILTER (
      WHERE active AND evidence_ref IS NOT NULL
      AND length(btrim(evidence_ref)) > 0
    )::integer AS active_evidenced_role_bindings
  FROM public.empire_tenant_role_bindings
  GROUP BY tenant_id
),
entity_scope AS (
  SELECT tenant_id,
    count(*) FILTER (
      WHERE active AND binding_kind='owned'
        AND evidence_ref IS NOT NULL AND length(btrim(evidence_ref)) > 0
        AND valid_from<=now()
        AND (valid_until IS NULL OR valid_until>now())
    )::integer AS owned_entity_evidence_count,
    count(*) FILTER (
      WHERE active
        AND evidence_ref IS NOT NULL AND length(btrim(evidence_ref)) > 0
        AND valid_from<=now()
        AND (valid_until IS NULL OR valid_until>now())
    )::integer AS total_entity_evidence_count
  FROM public.tenant_business_entity_bindings
  GROUP BY tenant_id
),
membership_scope AS (
  SELECT tenant_id,
    count(*)::integer AS crm_membership_records,
    count(*) FILTER (
      WHERE status='active' AND revoked_at IS NULL AND verified_at<=now()
        AND evidence_ref IS NOT NULL AND length(btrim(evidence_ref))>0
        AND (valid_until IS NULL OR valid_until>now())
    )::integer AS active_crm_memberships
  FROM public.empire_crm_tenant_memberships
  GROUP BY tenant_id
),
candidates AS (
  SELECT tenant_id FROM role_scope
  UNION SELECT tenant_id FROM entity_scope
  UNION SELECT tenant_id FROM membership_scope
),
annotated AS (
  SELECT c.tenant_id, COALESCE(r.role_binding_count,0) AS role_binding_count,
         COALESCE(r.active_evidenced_role_bindings,0) AS active_evidenced_role_bindings,
         COALESCE(e.owned_entity_evidence_count,0) AS owned_entity_evidence_count,
         COALESCE(e.total_entity_evidence_count,0) AS total_entity_evidence_count,
         COALESCE(m.crm_membership_records,0) AS crm_membership_records,
         COALESCE(m.active_crm_memberships,0) AS active_crm_memberships
  FROM candidates c
  LEFT JOIN role_scope r USING (tenant_id)
  LEFT JOIN entity_scope e USING (tenant_id)
  LEFT JOIN membership_scope m USING (tenant_id)
),
bounded AS (
  SELECT * FROM annotated
  ORDER BY owned_entity_evidence_count DESC,
           active_evidenced_role_bindings DESC, tenant_id
  LIMIT 20
)
SELECT jsonb_pretty(jsonb_build_object(
  'schema','empire.crm.founder_candidate_inventory.v1',
  'mode','OBSERVE',
  'canonical_db',current_database()='empiredb'
      OR current_database()='crm_membership_fixture',
  'query_transaction_read_only',current_setting('transaction_read_only')='on',
  'writes_performed',false,'logins_enabled',false,
  'customer_credentials_read',false,'private_email_read',false,
  'crm_membership_total',(SELECT COUNT(*) FROM public.empire_crm_tenant_memberships),
  'credential_record_count',(SELECT COUNT(*) FROM public.empire_crm_login_credentials),
  'tenant_candidates_total',(SELECT COUNT(*) FROM annotated),
  'tenant_candidates_truncated',(SELECT COUNT(*) FROM annotated)>20,
  'candidate_tenants',COALESCE((SELECT jsonb_agg(jsonb_build_object(
    'tenant_id',tenant_id,
    'active_evidenced_role_bindings',active_evidenced_role_bindings,
    'owned_entity_evidence_count',owned_entity_evidence_count,
    'total_entity_evidence_count',total_entity_evidence_count,
    'active_crm_memberships',active_crm_memberships
  ) ORDER BY owned_entity_evidence_count DESC,
             active_evidenced_role_bindings DESC,tenant_id)
  FROM bounded),'[]'::jsonb),
  'human_founder_identity_verified',false,
  'founder_to_tenant_membership_verified',false,
  'pilot_activation_authorized',false,
  'next_action','REVIEW_INDEPENDENT_FOUNDER_AND_TENANT_OWNERSHIP_EVIDENCE'
));
ROLLBACK;
