-- Empire Data Cloud — active schema parity wave 2C
-- Migration: empiredb/012_closer_commercial_evidence_parity
-- Source of truth: live canonical production schema, 2026-09-27.
-- Schema only. No data copy, no activation, no cutover.

CREATE TABLE IF NOT EXISTS public.closer_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbound_intent_id UUID NOT NULL
        REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
    reply_id UUID NOT NULL UNIQUE
        REFERENCES public.outbound_replies(id) ON DELETE RESTRICT,
    prospect_id UUID
        REFERENCES public.prospects(id) ON DELETE RESTRICT,
    entity_id UUID
        REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    buyer_id UUID
        REFERENCES public.buyers(id) ON DELETE RESTRICT,
    opportunity_id UUID
        REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
    fulfilment_order_id UUID
        REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
    state TEXT NOT NULL DEFAULT 'engaged',
    opened_from_classification TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT closer_cases_state_check
        CHECK (state = ANY (
            ARRAY[
                'engaged','qualified','proposal_ready','proposal_approved',
                'awaiting_payment','won','lost','paused'
            ]::text[]
        ))
);

CREATE INDEX IF NOT EXISTS closer_cases_state_idx
    ON public.closer_cases (state, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.commercial_evidence_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_kind TEXT NOT NULL,
    buyer_id UUID
        REFERENCES public.buyers(id) ON DELETE RESTRICT,
    closer_case_id UUID
        REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
    fulfilment_order_id UUID
        REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
    niche TEXT,
    metro TEXT,
    amount_cents BIGINT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    unit TEXT NOT NULL DEFAULT 'per_order',
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',
    observed_at TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    rejected_at TIMESTAMPTZ,
    rejected_by TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT commercial_evidence_registry_amount_cents_check
        CHECK (amount_cents >= 0),
    CONSTRAINT commercial_evidence_registry_price_positive_check
        CHECK (evidence_kind <> 'price' OR amount_cents > 0),
    CONSTRAINT commercial_evidence_registry_valid_window_check
        CHECK (valid_until IS NULL OR valid_until > observed_at),
    CONSTRAINT commercial_evidence_registry_currency_check
        CHECK (upper(currency) = 'USD'),
    CONSTRAINT commercial_evidence_registry_evidence_kind_check
        CHECK (evidence_kind = ANY (
            ARRAY['price','acquisition_cost','fulfilment_cost']::text[]
        )),
    CONSTRAINT commercial_evidence_registry_source_type_check
        CHECK (source_type = ANY (
            ARRAY[
                'buyer_stated','founder_approved','observed_contract',
                'public_price','provider_invoice','internal_actual'
            ]::text[]
        )),
    CONSTRAINT commercial_evidence_registry_status_check
        CHECK (status = ANY (ARRAY['pending','verified','rejected']::text[])),
    CONSTRAINT commercial_evidence_registry_unit_check
        CHECK (unit = ANY (
            ARRAY['per_order','per_lead','per_call','per_month','flat']::text[]
        ))
);

CREATE INDEX IF NOT EXISTS idx_commercial_evidence_market
    ON public.commercial_evidence_registry
       (evidence_kind, niche, metro, status, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_commercial_evidence_order
    ON public.commercial_evidence_registry
       (fulfilment_order_id, evidence_kind, status, observed_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_commercial_evidence_source
    ON public.commercial_evidence_registry
       (evidence_kind, source_type, source_reference);
