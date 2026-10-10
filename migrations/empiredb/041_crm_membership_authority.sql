-- EmpireDB 041 — canonical tenant membership authority for CRM read sessions.
-- PREPARED ONLY: founder approval required before production application.
-- No live LOGIN, user/member records, HTTP activation, grants, outbound or payments.
-- Active status requires operator-supplied evidence. Default is pending.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb', 'crm_membership_fixture') THEN
    RAISE EXCEPTION 'invalid CRM membership migration database';
  END IF;
  IF pg_catalog.to_regclass('public.empire_crm_tenant_memberships') IS NOT NULL
    OR pg_catalog.to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NOT NULL
  THEN
    RAISE EXCEPTION 'existing membership authority requires reconciliation';
  END IF;
END;
$guard$;

CREATE TABLE public.empire_crm_tenant_memberships (
    tenant_id uuid NOT NULL,
    subject text NOT NULL CHECK (
      subject ~ '^[A-Za-z0-9:@._/-]{1,128}$'
    ),
    role text NOT NULL CHECK (
      role IN ('owner','admin','operator','analyst','viewer')
    ),
    status text NOT NULL DEFAULT 'pending' CHECK (
      status IN ('pending','active','disabled')
    ),
    evidence_ref text NOT NULL CHECK (
      length(btrim(evidence_ref)) BETWEEN 1 AND 512
    ),
    verified_at timestamptz NOT NULL,
    valid_until timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,subject),
    CHECK (status <> 'active' OR revoked_at IS NULL),
    CHECK (valid_until IS NULL OR valid_until > verified_at)
);

ALTER TABLE public.empire_crm_tenant_memberships ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.empire_crm_tenant_memberships FROM PUBLIC;
-- No application LOGIN or CRM reader gets direct membership-table access.
REVOKE ALL ON TABLE public.empire_crm_tenant_memberships
  FROM empiredb_app, empiredb_readonly, empiredb_tenant_reader,
       empire_revenue_crm_reader;

-- Exact-subject/tenant only; evidence is required to activate records.
-- The separate dedicated verifier LOGIN must be provisioned and receive
-- EXECUTE under a later explicit authority gate. No automatic grants.
CREATE FUNCTION public.empire_crm_read_member(
    p_subject text, p_tenant uuid
)
RETURNS TABLE (
    user_id text,
    tenant_id uuid,
    role text,
    status text
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $fn$
    SELECT m.subject, m.tenant_id, m.role, m.status
    FROM public.empire_crm_tenant_memberships m
    WHERE session_user = 'empire_crm_membership_login'
      AND m.subject = p_subject
      AND m.tenant_id = p_tenant
      AND m.status = 'active'
      AND m.revoked_at IS NULL
      AND (m.valid_until IS NULL OR m.valid_until > CURRENT_TIMESTAMP)
      AND m.verified_at <= CURRENT_TIMESTAMP
      AND m.evidence_ref IS NOT NULL
      AND length(btrim(m.evidence_ref)) > 0
    LIMIT 1
$fn$;

REVOKE ALL ON FUNCTION public.empire_crm_read_member(text,uuid) FROM PUBLIC;
COMMENT ON TABLE public.empire_crm_tenant_memberships IS
  'Canonical user/tenant membership evidence; pending by default. No direct CRM reader rights.';
COMMENT ON FUNCTION public.empire_crm_read_member(text,uuid) IS
  'Bounded active membership read for independently authenticated CRM issuer only.';
COMMIT;
