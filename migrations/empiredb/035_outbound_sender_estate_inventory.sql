-- EmpireDB migration 035: outbound sender estate inventory
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Creates canonical assets supervised by Ringleader.
-- No credentials/secrets belong in these tables.
-- No runtime grants or authority expansion in this migration.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbound_transports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    transport_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    traffic_class TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'VERIFYING' CHECK (
        state IN (
            'VERIFYING','ACTIVE','THROTTLED','HOLD','RETIRED'
        )
    ),
    policy_compatible BOOLEAN NOT NULL DEFAULT FALSE,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, transport_key)
);

CREATE TABLE IF NOT EXISTS public.outbound_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    domain TEXT NOT NULL,
    purpose TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'PARKED' CHECK (
        lifecycle_state IN (
            'PARKED','VERIFYING','RAMPING','ACTIVE',
            'THROTTLED','HOLD','RETIRED'
        )
    ),
    primary_brand BOOLEAN NOT NULL DEFAULT FALSE,
    registrar_controlled BOOLEAN NOT NULL DEFAULT FALSE,
    dns_controlled BOOLEAN NOT NULL DEFAULT FALSE,
    registrar_provider TEXT,
    dns_provider TEXT,
    expires_on DATE,
    desired_dns_fingerprint TEXT,
    observed_dns_fingerprint TEXT,
    sovereignty_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, domain)
);

CREATE INDEX IF NOT EXISTS idx_outbound_domains_scope_state
    ON public.outbound_domains(scope_key, lifecycle_state);

CREATE TABLE IF NOT EXISTS public.outbound_mailboxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    mailbox_key TEXT NOT NULL,
    email_address TEXT NOT NULL,
    domain_id UUID NOT NULL
        REFERENCES public.outbound_domains(id)
        ON DELETE RESTRICT,
    transport_id UUID
        REFERENCES public.outbound_transports(id)
        ON DELETE RESTRICT,
    state TEXT NOT NULL DEFAULT 'VERIFYING' CHECK (
        state IN (
            'NEW','VERIFYING','RAMPING','ACTIVE',
            'THROTTLED','QUARANTINED','RECOVERY','RETIRED'
        )
    ),
    daily_cap INTEGER NOT NULL DEFAULT 0 CHECK (daily_cap >= 0),
    reputation_credit INTEGER NOT NULL DEFAULT 0 CHECK (
        reputation_credit BETWEEN 0 AND 100
    ),
    identity_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, mailbox_key),
    UNIQUE(scope_key, email_address)
);

CREATE INDEX IF NOT EXISTS idx_outbound_mailboxes_domain
    ON public.outbound_mailboxes(scope_key, domain_id, state);

CREATE INDEX IF NOT EXISTS idx_outbound_mailboxes_transport
    ON public.outbound_mailboxes(scope_key, transport_id, state);

CREATE TABLE IF NOT EXISTS public.outbound_sender_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    pool_key TEXT NOT NULL,
    pool_kind TEXT NOT NULL CHECK (
        pool_kind IN (
            'DOMAIN','MAILBOX','TRANSPORT',
            'RECIPIENT_MX','SEED_PLACEMENT'
        )
    ),
    purpose TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'VERIFYING' CHECK (
        state IN (
            'NEW','VERIFYING','RAMPING','ACTIVE',
            'THROTTLED','QUARANTINED','RECOVERY','RETIRED'
        )
    ),
    policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, pool_key)
);

CREATE INDEX IF NOT EXISTS idx_outbound_sender_pools_scope_kind
    ON public.outbound_sender_pools(scope_key, pool_kind, state);

CREATE TABLE IF NOT EXISTS public.outbound_pool_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    pool_id UUID NOT NULL
        REFERENCES public.outbound_sender_pools(id)
        ON DELETE RESTRICT,
    member_type TEXT NOT NULL CHECK (
        member_type IN (
            'DOMAIN','MAILBOX','TRANSPORT','RECIPIENT_MX','SEED'
        )
    ),
    member_key TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, pool_id, member_type, member_key)
);

CREATE INDEX IF NOT EXISTS idx_outbound_pool_members_active
    ON public.outbound_pool_members(scope_key, pool_id, active);

CREATE TABLE IF NOT EXISTS public.outbound_capacity_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    capacity_date DATE NOT NULL,
    mailbox_key TEXT NOT NULL,
    domain TEXT NOT NULL,
    transport_key TEXT,
    recipient_mx TEXT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'SET_LIMIT','RESERVE','CONSUME','RELEASE','RESET'
        )
    ),
    units INTEGER NOT NULL DEFAULT 0 CHECK (units >= 0),
    capacity_limit INTEGER CHECK (
        capacity_limit IS NULL OR capacity_limit >= 0
    ),
    reason TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        (event_type = 'SET_LIMIT' AND capacity_limit IS NOT NULL)
        OR
        (event_type <> 'SET_LIMIT' AND capacity_limit IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_outbound_capacity_mailbox_day
    ON public.outbound_capacity_ledger(
        scope_key, mailbox_key, capacity_date, recorded_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_outbound_capacity_mx_day
    ON public.outbound_capacity_ledger(
        scope_key, recipient_mx, capacity_date, recorded_at DESC
    );

CREATE TABLE IF NOT EXISTS public.outbound_seed_mailboxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    seed_key TEXT NOT NULL,
    mailbox_provider TEXT NOT NULL,
    recipient_mx_family TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    ownership_verified BOOLEAN NOT NULL DEFAULT FALSE,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, seed_key)
);

COMMENT ON TABLE public.outbound_transports IS
    'Canonical non-secret transport registry. Provider credentials remain outside EmpireDB.';
COMMENT ON TABLE public.outbound_domains IS
    'Canonical Empire-owned domain inventory and sovereignty evidence.';
COMMENT ON TABLE public.outbound_mailboxes IS
    'Canonical sender identity inventory with bounded capacity and reputation state.';
COMMENT ON TABLE public.outbound_sender_pools IS
    'Stable Ringleader pools used for isolation, capacity and measurement.';
COMMENT ON TABLE public.outbound_pool_members IS
    'Explicit membership of domains, mailboxes, transports, MX families or seeds in stable pools.';
COMMENT ON TABLE public.outbound_capacity_ledger IS
    'Append-only SET_LIMIT/RESERVE/CONSUME/RELEASE/RESET capacity events; replayable and non-authorizing.';
COMMENT ON TABLE public.outbound_seed_mailboxes IS
    'Empire-controlled placement-test mailbox identities; never synthetic engagement actors.';

COMMIT;
