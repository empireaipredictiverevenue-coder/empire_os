-- EmpireDB migration 039: outbound fleet readiness certificates
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Append-only fleet capacity/resilience evidence for audited scaling decisions.
-- No runtime grants, provisioning authority, DNS mutation, or send authority.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbound_fleet_readiness_certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    certificate_key TEXT NOT NULL,
    certificate_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('READY','LIMITED','HOLD')
    ),
    approved_daily_volume INTEGER NOT NULL DEFAULT 0 CHECK (
        approved_daily_volume >= 0
    ),
    allocated_capacity INTEGER NOT NULL DEFAULT 0 CHECK (
        allocated_capacity >= 0
    ),
    capacity_gap INTEGER NOT NULL DEFAULT 0 CHECK (
        capacity_gap >= 0
    ),
    required_domains INTEGER NOT NULL DEFAULT 0 CHECK (
        required_domains >= 0
    ),
    required_mailboxes INTEGER NOT NULL DEFAULT 0 CHECK (
        required_mailboxes >= 0
    ),
    eligible_domains INTEGER NOT NULL DEFAULT 0 CHECK (
        eligible_domains >= 0
    ),
    resilience_score NUMERIC NOT NULL DEFAULT 0 CHECK (
        resilience_score >= 0 AND resilience_score <= 100
    ),
    transport_n_minus_one_survival NUMERIC NOT NULL DEFAULT 0 CHECK (
        transport_n_minus_one_survival >= 0
        AND transport_n_minus_one_survival <= 1
    ),
    domain_n_minus_one_survival NUMERIC NOT NULL DEFAULT 0 CHECK (
        domain_n_minus_one_survival >= 0
        AND domain_n_minus_one_survival <= 1
    ),
    ip_pool_n_minus_one_survival NUMERIC NOT NULL DEFAULT 0 CHECK (
        ip_pool_n_minus_one_survival >= 0
        AND ip_pool_n_minus_one_survival <= 1
    ),
    estate_status TEXT,
    failover_evidence TEXT,
    blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    certificate JSONB NOT NULL DEFAULT '{}'::jsonb,
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    provisioning_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    send_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, certificate_key),
    UNIQUE(scope_key, certificate_fingerprint, observed_at),
    CHECK (mutation_authorized = FALSE),
    CHECK (provisioning_authorized = FALSE),
    CHECK (send_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_fleet_readiness_latest
    ON public.outbound_fleet_readiness_certificates(
        scope_key, observed_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_outbound_fleet_readiness_status
    ON public.outbound_fleet_readiness_certificates(
        scope_key, status, observed_at DESC
    );

COMMENT ON TABLE public.outbound_fleet_readiness_certificates IS
    'Append-only capacity and N-1 resilience certificates used to audit scaling readiness; never grants provisioning or send authority.';

COMMIT;
