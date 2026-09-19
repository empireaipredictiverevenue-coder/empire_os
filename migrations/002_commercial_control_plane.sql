-- ============================================================
-- Empire OS — Commercial Control Plane
-- Migration: 002_commercial_control_plane
--
-- Purpose:
--   Shared backbone for GTM, products, fulfilment and outcomes.
--
-- Safety:
--   Creates new tables/indexes only.
--   Does NOT UPDATE or DELETE prospects, buyers or identities.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- 1. GTM opportunities
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.gtm_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    niche TEXT NOT NULL,
    metro TEXT,

    opportunity_type TEXT NOT NULL,
    source_channel TEXT NOT NULL,

    demand_score NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    supply_score NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    buyer_demand_score NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    economic_score NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    fulfilment_score NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    visibility_score NUMERIC(5,4) NOT NULL DEFAULT 0.0000,

    expected_revenue_cents BIGINT NOT NULL DEFAULT 0,
    expected_margin_cents BIGINT NOT NULL DEFAULT 0,

    priority_score NUMERIC(7,4) NOT NULL DEFAULT 0.0000,

    hypothesis TEXT,
    rationale JSONB NOT NULL DEFAULT '{}'::jsonb,
    signal_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    status TEXT NOT NULL DEFAULT 'discovered',
    -- discovered / testing / approved / active / paused / won / rejected

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gtm_opportunities_priority
    ON public.gtm_opportunities (priority_score DESC);

CREATE INDEX IF NOT EXISTS idx_gtm_opportunities_market
    ON public.gtm_opportunities (niche, metro);

CREATE INDEX IF NOT EXISTS idx_gtm_opportunities_status
    ON public.gtm_opportunities (status);

-- ------------------------------------------------------------
-- 2. GTM execution jobs
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.gtm_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    opportunity_id UUID
        REFERENCES public.gtm_opportunities(id)
        ON DELETE RESTRICT,

    job_type TEXT NOT NULL,
    worker_adapter TEXT NOT NULL,

    priority NUMERIC(7,4) NOT NULL DEFAULT 0.0000,

    status TEXT NOT NULL DEFAULT 'planned',
    -- planned / queued / running / blocked / completed / failed / cancelled

    requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
    approved_at TIMESTAMPTZ,

    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,

    attempts INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_gtm_jobs_priority
    ON public.gtm_jobs (priority DESC);

CREATE INDEX IF NOT EXISTS idx_gtm_jobs_status
    ON public.gtm_jobs (status);

CREATE INDEX IF NOT EXISTS idx_gtm_jobs_opportunity
    ON public.gtm_jobs (opportunity_id);

-- ------------------------------------------------------------
-- 3. Product catalogue / MRR
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.commercial_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    product_code TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,

    product_family TEXT NOT NULL,
    -- ppl / subscription / intelligence / appointment /
    -- managed_service / enterprise / hybrid

    billing_model TEXT NOT NULL,
    -- one_time / recurring / usage / hybrid

    monthly_price_cents BIGINT NOT NULL DEFAULT 0,
    setup_price_cents BIGINT NOT NULL DEFAULT 0,

    per_lead_price_cents BIGINT NOT NULL DEFAULT 0,
    per_call_price_cents BIGINT NOT NULL DEFAULT 0,
    per_schedule_price_cents BIGINT NOT NULL DEFAULT 0,

    active BOOLEAN NOT NULL DEFAULT FALSE,

    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_commercial_products_family
    ON public.commercial_products (product_family);

CREATE INDEX IF NOT EXISTS idx_commercial_products_active
    ON public.commercial_products (active);

-- ------------------------------------------------------------
-- 4. Fulfilment orders
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fulfilment_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    opportunity_id UUID
        REFERENCES public.gtm_opportunities(id)
        ON DELETE RESTRICT,

    product_id UUID
        REFERENCES public.commercial_products(id)
        ON DELETE RESTRICT,

    prospect_id UUID
        REFERENCES public.prospects(id)
        ON DELETE RESTRICT,

    entity_id UUID
        REFERENCES public.business_entities(id)
        ON DELETE RESTRICT,

    buyer_id UUID
        REFERENCES public.buyers(id)
        ON DELETE RESTRICT,

    state TEXT NOT NULL DEFAULT 'raw',
    -- raw
    -- qualified
    -- matched
    -- offered
    -- accepted
    -- delivered
    -- confirmed
    -- invoiced
    -- paid
    -- settled
    -- outcome_captured
    -- rejected
    -- cancelled

    quantity INTEGER NOT NULL DEFAULT 1,

    price_cents BIGINT NOT NULL DEFAULT 0,
    acquisition_cost_cents BIGINT NOT NULL DEFAULT 0,
    fulfilment_cost_cents BIGINT NOT NULL DEFAULT 0,

    expected_margin_cents BIGINT NOT NULL DEFAULT 0,
    actual_margin_cents BIGINT,

    delivery_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    commercial_payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    delivered_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    settled_at TIMESTAMPTZ,
    outcome_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_fulfilment_orders_state
    ON public.fulfilment_orders (state);

CREATE INDEX IF NOT EXISTS idx_fulfilment_orders_buyer
    ON public.fulfilment_orders (buyer_id);

CREATE INDEX IF NOT EXISTS idx_fulfilment_orders_prospect
    ON public.fulfilment_orders (prospect_id);

CREATE INDEX IF NOT EXISTS idx_fulfilment_orders_entity
    ON public.fulfilment_orders (entity_id);

-- ------------------------------------------------------------
-- 5. Immutable commercial event ledger
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.commercial_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    event_type TEXT NOT NULL,

    opportunity_id UUID
        REFERENCES public.gtm_opportunities(id)
        ON DELETE RESTRICT,

    job_id UUID
        REFERENCES public.gtm_jobs(id)
        ON DELETE RESTRICT,

    fulfilment_order_id UUID
        REFERENCES public.fulfilment_orders(id)
        ON DELETE RESTRICT,

    prospect_id UUID
        REFERENCES public.prospects(id)
        ON DELETE RESTRICT,

    entity_id UUID
        REFERENCES public.business_entities(id)
        ON DELETE RESTRICT,

    buyer_id UUID
        REFERENCES public.buyers(id)
        ON DELETE RESTRICT,

    product_id UUID
        REFERENCES public.commercial_products(id)
        ON DELETE RESTRICT,

    channel TEXT,
    actor TEXT,

    amount_cents BIGINT,
    cost_cents BIGINT,
    margin_cents BIGINT,

    payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_commercial_events_type
    ON public.commercial_events (event_type);

CREATE INDEX IF NOT EXISTS idx_commercial_events_occurred
    ON public.commercial_events (occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_commercial_events_opportunity
    ON public.commercial_events (opportunity_id);

CREATE INDEX IF NOT EXISTS idx_commercial_events_order
    ON public.commercial_events (fulfilment_order_id);

CREATE INDEX IF NOT EXISTS idx_commercial_events_buyer
    ON public.commercial_events (buyer_id);

-- ------------------------------------------------------------
-- 6. GTM experiments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.gtm_experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    opportunity_id UUID
        REFERENCES public.gtm_opportunities(id)
        ON DELETE RESTRICT,

    experiment_type TEXT NOT NULL,
    hypothesis TEXT NOT NULL,

    variants JSONB NOT NULL DEFAULT '[]'::jsonb,
    allocation JSONB NOT NULL DEFAULT '{}'::jsonb,

    status TEXT NOT NULL DEFAULT 'draft',
    -- draft / running / paused / completed / rejected

    minimum_sample_size INTEGER NOT NULL DEFAULT 0,

    winner_variant TEXT,

    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_gtm_experiments_status
    ON public.gtm_experiments (status);

CREATE INDEX IF NOT EXISTS idx_gtm_experiments_opportunity
    ON public.gtm_experiments (opportunity_id);

-- ------------------------------------------------------------
-- Documentation
-- ------------------------------------------------------------
COMMENT ON TABLE public.gtm_opportunities IS
    'Commercial opportunities discovered by GTM and Predictive Cloud.';

COMMENT ON TABLE public.gtm_jobs IS
    'Governed execution jobs delegated to GTM worker adapters.';

COMMENT ON TABLE public.commercial_products IS
    'Empire commercial product and recurring-revenue catalogue.';

COMMENT ON TABLE public.fulfilment_orders IS
    'Commercial fulfilment state machine from qualification through settlement and outcome.';

COMMENT ON TABLE public.commercial_events IS
    'Append-only commercial event ledger used by Predictive Cloud and the Empire Brain.';

COMMENT ON TABLE public.gtm_experiments IS
    'Controlled GTM experiments for offers, channels, messaging and acquisition strategies.';
