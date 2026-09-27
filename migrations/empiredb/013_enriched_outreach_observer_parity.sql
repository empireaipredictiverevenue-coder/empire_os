-- Empire Data Cloud — active schema parity wave 2D
-- Migration: empiredb/013_enriched_outreach_observer_parity
-- Source of truth: live canonical production schema, 2026-09-27.
-- Schema only. No outbound sends, no data copy, no cutover.

CREATE TABLE IF NOT EXISTS public.enriched_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    radar_target_id UUID UNIQUE,
    address TEXT,
    city TEXT,
    state TEXT,
    phone TEXT,
    email TEXT,
    warehouse_name TEXT,
    asset_value NUMERIC,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    score NUMERIC,
    status TEXT NOT NULL DEFAULT 'pending_enrichment',
    last_enriched_at TIMESTAMPTZ,
    meta JSONB DEFAULT '{}'::jsonb,
    converted_at TIMESTAMPTZ,
    niche TEXT,
    vertical TEXT,
    CONSTRAINT enriched_leads_status_check
        CHECK (status = ANY (
            ARRAY[
                'pending_enrichment','pending_outreach','blocked',
                'converted','opted_out','rejected'
            ]::text[]
        ))
);

CREATE INDEX IF NOT EXISTS enriched_leads_created_idx
    ON public.enriched_leads (created_at DESC);

CREATE INDEX IF NOT EXISTS enriched_leads_phone_idx
    ON public.enriched_leads (phone)
    WHERE phone IS NOT NULL;

CREATE INDEX IF NOT EXISTS enriched_leads_status_idx
    ON public.enriched_leads (status, score DESC);

CREATE INDEX IF NOT EXISTS idx_enriched_leads_converted_at
    ON public.enriched_leads (converted_at DESC)
    WHERE status = 'converted' AND converted_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.outreach_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enriched_lead_id UUID
        REFERENCES public.enriched_leads(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    run_id UUID NOT NULL,
    channel TEXT NOT NULL,
    sequence TEXT,
    step INTEGER,
    body_preview TEXT,
    would_send_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    compliance_passed BOOLEAN NOT NULL,
    compliance_block_reason TEXT,
    mode TEXT NOT NULL,
    sent_at TIMESTAMPTZ,
    sent_status TEXT,
    response_received_at TIMESTAMPTZ,
    response_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT outreach_log_channel_check
        CHECK (channel = ANY (ARRAY['sms','voice','email']::text[])),
    CONSTRAINT outreach_log_mode_check
        CHECK (mode = ANY (ARRAY['dry_run','live']::text[]))
);

CREATE INDEX IF NOT EXISTS outreach_log_lead_idx
    ON public.outreach_log (enriched_lead_id, would_send_at DESC);

CREATE INDEX IF NOT EXISTS outreach_log_mode_idx
    ON public.outreach_log (mode, would_send_at DESC);

CREATE INDEX IF NOT EXISTS outreach_log_run_idx
    ON public.outreach_log (run_id);

CREATE TABLE IF NOT EXISTS public.astra_observer_tokens (
    token_sha256 TEXT PRIMARY KEY,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT astra_observer_tokens_token_sha256_check
        CHECK (token_sha256 ~ '^[0-9a-f]{64}$')
);

REVOKE ALL ON TABLE public.astra_observer_tokens FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.astra_observer_tokens FROM empiredb_app;
GRANT SELECT ON TABLE public.astra_observer_tokens TO empiredb_app;
GRANT SELECT ON TABLE public.astra_observer_tokens TO empiredb_readonly;
