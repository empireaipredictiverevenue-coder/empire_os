-- PREPARED ONLY - DO NOT APPLY WITHOUT REVIEW.
-- Requires 20261020124500_inbound_revenue_recovery_prepared.sql first.
-- Tenant membership is the authorization source; never trust user_metadata.
-- No customer-accessible event/receipt mutation, and no privileged public RPC.
BEGIN;

CREATE TABLE IF NOT EXISTS public.inbound_recovery_memberships (
    tenant_id text NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    membership_role text NOT NULL DEFAULT 'viewer'
        CHECK (membership_role IN ('viewer', 'analyst', 'admin')),
    membership_status text NOT NULL DEFAULT 'pending'
        CHECK (membership_status IN ('pending', 'active', 'revoked')),
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id),
    CHECK (membership_status <> 'active' OR approved_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS inbound_recovery_memberships_user_idx
    ON public.inbound_recovery_memberships (user_id, tenant_id)
    WHERE membership_status = 'active';

ALTER TABLE public.inbound_recovery_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_memberships FORCE ROW LEVEL SECURITY;

REVOKE ALL ON public.inbound_recovery_memberships FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.inbound_recovery_memberships TO authenticated;

DROP POLICY IF EXISTS inbound_recovery_membership_self_read
    ON public.inbound_recovery_memberships;
CREATE POLICY inbound_recovery_membership_self_read
    ON public.inbound_recovery_memberships
    FOR SELECT TO authenticated
    USING (
        user_id = (select auth.uid())
        AND membership_status = 'active'
        AND approved_at IS NOT NULL
    );

-- Only approved tenant profiles can be read by actively admitted members.
-- Users cannot select arbitrary tenant profiles by passing a tenant_id.
DROP POLICY IF EXISTS inbound_recovery_tenant_member_read
    ON public.inbound_recovery_tenants;
CREATE POLICY inbound_recovery_tenant_member_read
    ON public.inbound_recovery_tenants
    FOR SELECT TO authenticated
    USING (
        lifecycle_state = 'approved'
        AND EXISTS (
            SELECT 1
            FROM public.inbound_recovery_memberships m
            WHERE m.tenant_id = inbound_recovery_tenants.tenant_id
              AND m.user_id = (select auth.uid())
              AND m.membership_status = 'active'
              AND m.approved_at IS NOT NULL
        )
    );

REVOKE ALL ON public.inbound_recovery_tenants FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.inbound_recovery_tenants TO authenticated;

-- Event and provider receipt tables stay server-only; customer-facing
-- aggregates are mediated by an authenticated, independently audited API.
REVOKE ALL ON public.inbound_recovery_events
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.inbound_recovery_signed_callbacks
    FROM PUBLIC, anon, authenticated;

-- Append-only server-owned audit storage. No automatic trigger/worker/service
-- is installed, and no policies or grants permit customer access.
CREATE TABLE IF NOT EXISTS public.inbound_recovery_management_access_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    actor_fingerprint char(64) NOT NULL
        CHECK (actor_fingerprint ~ '^[a-f0-9]{64}$'),
    operation text NOT NULL CHECK (operation IN (
        'profile_read', 'scorecard_read', 'queue_read', 'patterns_read',
        'knowledge_read', 'workflow_read', 'calendar_read'
    )),
    previous_hash text NOT NULL,
    record_hash char(64) NOT NULL CHECK (record_hash ~ '^[a-f0-9]{64}$'),
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inbound_recovery_management_audit_tenant_time_idx
    ON public.inbound_recovery_management_access_audit(tenant_id, occurred_at DESC);

ALTER TABLE public.inbound_recovery_management_access_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_management_access_audit FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.inbound_recovery_management_access_audit
    FROM PUBLIC, anon, authenticated;

-- Granting public/anon tenant or event reads would be a release regression.
-- Provision/revoke memberships only through a separate, audited operator
-- workflow with a server-side credential that is never exposed to browsers.
COMMIT;
