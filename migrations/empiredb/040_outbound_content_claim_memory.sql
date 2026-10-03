-- EmpireDB migration 040: outbound content and claim evidence memory
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Append-only message-family outcomes and claim-verification evidence.
-- No runtime grants, DNS mutation, transport mutation, or send authority.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbound_content_family_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    event_key TEXT NOT NULL,
    family_key TEXT NOT NULL,
    event_kind TEXT NOT NULL CHECK (
        event_kind IN (
            'sent',
            'seed_test',
            'spam_placement',
            'complaint',
            'opt_out',
            'positive_reply',
            'meeting_booked',
            'revenue'
        )
    ),
    event_count INTEGER NOT NULL DEFAULT 1 CHECK (event_count >= 0),
    amount NUMERIC NOT NULL DEFAULT 0 CHECK (amount >= 0),
    campaign_key TEXT,
    recipient_mx_family TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, event_key)
);

CREATE INDEX IF NOT EXISTS idx_outbound_content_family_events_family_time
    ON public.outbound_content_family_events(
        scope_key, family_key, occurred_at DESC
    );

CREATE TABLE IF NOT EXISTS public.outbound_content_family_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    family_key TEXT NOT NULL,
    posture TEXT NOT NULL CHECK (
        posture IN ('LEARNING','HEALTHY','DEGRADED','QUARANTINE')
    ),
    sent INTEGER NOT NULL DEFAULT 0 CHECK (sent >= 0),
    seed_tests INTEGER NOT NULL DEFAULT 0 CHECK (seed_tests >= 0),
    complaint_rate NUMERIC NOT NULL DEFAULT 0 CHECK (
        complaint_rate >= 0 AND complaint_rate <= 1
    ),
    opt_out_rate NUMERIC NOT NULL DEFAULT 0 CHECK (
        opt_out_rate >= 0 AND opt_out_rate <= 1
    ),
    spam_placement_rate NUMERIC NOT NULL DEFAULT 0 CHECK (
        spam_placement_rate >= 0 AND spam_placement_rate <= 1
    ),
    commercial_score NUMERIC NOT NULL DEFAULT 0,
    revenue NUMERIC NOT NULL DEFAULT 0 CHECK (revenue >= 0),
    blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (mutation_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_content_family_snapshots_latest
    ON public.outbound_content_family_snapshots(
        scope_key, family_key, observed_at DESC
    );

CREATE TABLE IF NOT EXISTS public.outbound_claim_verification_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    verification_key TEXT NOT NULL,
    message_key TEXT NOT NULL,
    claim_index INTEGER NOT NULL CHECK (claim_index >= 0),
    claim_hash TEXT NOT NULL,
    claim_kind TEXT NOT NULL,
    evidence_ref TEXT,
    decision TEXT NOT NULL CHECK (
        decision IN ('VERIFIED','ESCALATE','HOLD')
    ),
    source_kind TEXT,
    hard_holds JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_holds JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, verification_key),
    CHECK (mutation_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_claim_verification_message
    ON public.outbound_claim_verification_events(
        scope_key, message_key, observed_at DESC
    );

COMMENT ON TABLE public.outbound_content_family_events IS
    'Append-only placement, complaint, opt-out and commercial outcomes attributed to stable message families.';
COMMENT ON TABLE public.outbound_content_family_snapshots IS
    'Derived content-family reputation history used by Ringleader canary/quarantine decisions.';
COMMENT ON TABLE public.outbound_claim_verification_events IS
    'Append-only hash-based audit of claim-to-evidence send-gate decisions without storing recipient copy as canonical identity.';

COMMIT;
