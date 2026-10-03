-- EmpireDB migration 035: outbound deliverability control plane
-- STAGED ONLY. Do not apply to production without explicit founder approval.
-- Canonical target: EmpireDB/PostgreSQL, not legacy Supabase.
-- Append-only evidence structures; no UPDATE/DELETE of existing business data.
-- Role grants are intentionally deferred until live EmpireDB role inventory is reconciled.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbound_deliverability_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    observed_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    domain TEXT,
    mailbox_key TEXT,
    transport_key TEXT,
    recipient_mx TEXT,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC,
    unit TEXT NOT NULL DEFAULT 'count',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_hash TEXT,
    previous_evidence_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        domain IS NOT NULL
        OR mailbox_key IS NOT NULL
        OR transport_key IS NOT NULL
        OR recipient_mx IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_outbound_deliv_obs_domain_time
    ON public.outbound_deliverability_observations(scope_key, domain, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_outbound_deliv_obs_mailbox_time
    ON public.outbound_deliverability_observations(scope_key, mailbox_key, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_outbound_deliv_obs_transport_time
    ON public.outbound_deliverability_observations(scope_key, transport_key, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_outbound_deliv_obs_mx_time
    ON public.outbound_deliverability_observations(scope_key, recipient_mx, observed_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_outbound_deliv_obs_evidence_hash
    ON public.outbound_deliverability_observations(scope_key, evidence_hash)
    WHERE evidence_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.outbound_ringleader_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    decision_key TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    posture TEXT NOT NULL CHECK (
        posture IN ('READY','LIMITED','REMEDIATE','HOLD','OBSERVE')
    ),
    domain TEXT,
    mailbox_key TEXT,
    transport_key TEXT,
    recipient_mx TEXT,
    hard_holds JSONB NOT NULL DEFAULT '[]'::jsonb,
    tasks JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_hash TEXT,
    previous_evidence_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, decision_key),
    CHECK (mutation_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_ringleader_decisions_time
    ON public.outbound_ringleader_decisions(scope_key, observed_at DESC);

CREATE TABLE IF NOT EXISTS public.outbound_sender_pool_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    pool_key TEXT NOT NULL,
    pool_kind TEXT NOT NULL CHECK (
        pool_kind IN ('DOMAIN','MAILBOX','TRANSPORT','RECIPIENT_MX','SEED_PLACEMENT')
    ),
    state TEXT NOT NULL CHECK (
        state IN (
            'NEW','VERIFYING','RAMPING','ACTIVE','THROTTLED',
            'QUARANTINED','RECOVERY','RETIRED'
        )
    ),
    daily_cap INTEGER NOT NULL DEFAULT 0 CHECK (daily_cap >= 0),
    reputation_credit INTEGER CHECK (
        reputation_credit IS NULL OR reputation_credit BETWEEN 0 AND 100
    ),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_outbound_sender_pool_obs_latest
    ON public.outbound_sender_pool_observations(
        scope_key, pool_key, observed_at DESC
    );

CREATE TABLE IF NOT EXISTS public.outbound_provider_policy_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    provider TEXT NOT NULL,
    effective_date DATE NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL,
    allowed_traffic_classes TEXT[] NOT NULL DEFAULT '{}',
    source_url TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, provider, effective_date, source_hash)
);

CREATE TABLE IF NOT EXISTS public.outbound_reputation_economic_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    cohort_key TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    domain TEXT,
    mailbox_key TEXT,
    transport_key TEXT,
    sent INTEGER NOT NULL DEFAULT 0 CHECK (sent >= 0),
    commercial_signal NUMERIC NOT NULL DEFAULT 0,
    reputation_cost NUMERIC NOT NULL DEFAULT 0 CHECK (reputation_cost >= 0),
    actual_revenue NUMERIC NOT NULL DEFAULT 0 CHECK (actual_revenue >= 0),
    predicted_pipeline NUMERIC NOT NULL DEFAULT 0 CHECK (predicted_pipeline >= 0),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, cohort_key)
);

CREATE INDEX IF NOT EXISTS idx_outbound_reputation_econ_time
    ON public.outbound_reputation_economic_events(scope_key, observed_at DESC);

CREATE TABLE IF NOT EXISTS public.outbound_contact_pressure_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    person_key TEXT NOT NULL,
    company_key TEXT NOT NULL,
    campaign_key TEXT,
    agent_key TEXT,
    channel TEXT NOT NULL DEFAULT 'email',
    occurred_at TIMESTAMPTZ NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_outbound_contact_pressure_person
    ON public.outbound_contact_pressure_events(scope_key, person_key, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_outbound_contact_pressure_company
    ON public.outbound_contact_pressure_events(scope_key, company_key, occurred_at DESC);

COMMENT ON TABLE public.outbound_deliverability_observations IS
    'Append-only EmpireDB evidence ledger for domain, mailbox, transport and recipient-MX deliverability observations.';

COMMENT ON TABLE public.outbound_ringleader_decisions IS
    'Append-only Ringleader decision history; migration 033 cannot authorize outbound mutation.';

COMMENT ON TABLE public.outbound_sender_pool_observations IS
    'Append-only state observations for Ringleader sender and destination pools.';

COMMENT ON TABLE public.outbound_provider_policy_snapshots IS
    'Dated provider policy evidence used for transport compatibility checks.';

COMMENT ON TABLE public.outbound_reputation_economic_events IS
    'Commercial yield versus reputation-cost history for approved outbound cohorts.';

COMMENT ON TABLE public.outbound_contact_pressure_events IS
    'Cross-agent contact-pressure evidence used to prevent duplicate or excessive outreach.';

COMMIT;
