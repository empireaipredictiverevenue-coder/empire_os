-- EmpireDB migration 037: outbound acquisition-source reputation memory
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Append-only downstream outcome evidence for scrapers/scouts/datasets/enrichment sources.
-- No runtime grants or send authority are introduced here.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbound_source_reputation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    event_key TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_type TEXT,
    event_kind TEXT NOT NULL CHECK (
        event_kind IN (
            'sent',
            'hard_bounce',
            'soft_bounce',
            'invalid_recipient',
            'complaint',
            'opt_out',
            'negative_reply',
            'positive_reply',
            'meeting_booked',
            'proposal_requested',
            'commercial_terms',
            'revenue'
        )
    ),
    event_count INTEGER NOT NULL DEFAULT 1 CHECK (event_count >= 0),
    amount NUMERIC NOT NULL DEFAULT 0 CHECK (amount >= 0),
    person_key TEXT,
    company_key TEXT,
    campaign_key TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, event_key)
);

CREATE INDEX IF NOT EXISTS idx_outbound_source_reputation_events_source_time
    ON public.outbound_source_reputation_events(
        scope_key, source_key, occurred_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_outbound_source_reputation_events_kind_time
    ON public.outbound_source_reputation_events(
        scope_key, event_kind, occurred_at DESC
    );

CREATE TABLE IF NOT EXISTS public.outbound_source_reputation_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    source_key TEXT NOT NULL,
    posture TEXT NOT NULL CHECK (
        posture IN ('LEARNING','HEALTHY','DEGRADED','QUARANTINE')
    ),
    score NUMERIC NOT NULL DEFAULT 0,
    sent INTEGER NOT NULL DEFAULT 0 CHECK (sent >= 0),
    hard_bounce_rate NUMERIC NOT NULL DEFAULT 0 CHECK (
        hard_bounce_rate >= 0 AND hard_bounce_rate <= 1
    ),
    complaint_rate NUMERIC NOT NULL DEFAULT 0 CHECK (
        complaint_rate >= 0 AND complaint_rate <= 1
    ),
    opt_out_rate NUMERIC NOT NULL DEFAULT 0 CHECK (
        opt_out_rate >= 0 AND opt_out_rate <= 1
    ),
    revenue NUMERIC NOT NULL DEFAULT 0 CHECK (revenue >= 0),
    blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (mutation_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_source_reputation_snapshots_latest
    ON public.outbound_source_reputation_snapshots(
        scope_key, source_key, observed_at DESC
    );

COMMENT ON TABLE public.outbound_source_reputation_events IS
    'Append-only downstream quality and commercial outcomes attributed to canonical acquisition sources.';
COMMENT ON TABLE public.outbound_source_reputation_snapshots IS
    'Derived source-reputation history for verification/quarantine decisions; never grants send authority.';

COMMIT;
