-- Empire Data Cloud — portable canonical base tables
-- Migration: 000_empiredb_canonical_base
-- Source of truth: live canonical public schema, 2026-09-27.
-- Scope: schema only. No data copy, no cutover, no Supabase roles.
-- RLS policy porting is intentionally deferred to the EmpireDB security migration;
-- enabling RLS here without equivalent portable policies would fail closed for app roles.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.prospects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now(),
    business_name TEXT,
    niche TEXT,
    metro TEXT,
    phone TEXT,
    website TEXT,
    address TEXT,
    rating NUMERIC,
    review_count INTEGER,
    buy_signal_score NUMERIC DEFAULT 0,
    runs_ads BOOLEAN,
    status TEXT DEFAULT 'new',
    notes TEXT,
    contacted_at TIMESTAMPTZ,
    contact_name TEXT,
    contact_title TEXT,
    contact_source TEXT,
    contacted_status TEXT DEFAULT 'not_contacted'
);

CREATE TABLE IF NOT EXISTS public.buyers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_name TEXT NOT NULL,
    niche TEXT NOT NULL,
    state_coverage TEXT[] DEFAULT '{}'::text[],
    timezone TEXT DEFAULT 'America/Chicago',
    hours_open INTEGER DEFAULT 8,
    hours_close INTEGER DEFAULT 20,
    base_payout NUMERIC DEFAULT 0,
    fee_rate NUMERIC DEFAULT 0.01,
    destination_phone TEXT,
    webhook_url TEXT,
    priority INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    daily_cap INTEGER DEFAULT 100,
    calls_today INTEGER DEFAULT 0,
    calls_accepted INTEGER DEFAULT 0,
    calls_offered INTEGER DEFAULT 0,
    last_reset DATE DEFAULT CURRENT_DATE,
    metro TEXT,
    payout_per_call NUMERIC DEFAULT 0.00,
    status TEXT DEFAULT 'ACTIVE',
    updated_at TIMESTAMPTZ DEFAULT now(),
    email TEXT,
    contact_name TEXT,
    notes TEXT,
    reviewed_at TIMESTAMPTZ,
    reviewed_by UUID,
    monthly_retainer NUMERIC NOT NULL DEFAULT 0,
    per_call_fee NUMERIC NOT NULL DEFAULT 0,
    sub_niche TEXT,
    org_id UUID,
    per_minute_rate NUMERIC DEFAULT NULL::numeric,
    per_lead_rate NUMERIC DEFAULT NULL::numeric,
    per_schedule_rate NUMERIC DEFAULT NULL::numeric,
    commercial_activation_state TEXT NOT NULL DEFAULT 'discovered',
    commercial_activated_at TIMESTAMPTZ,
    commercial_terms_source TEXT,
    commercial_terms_reference TEXT,
    commercial_terms_verified_at TIMESTAMPTZ,
    capacity_verified_at TIMESTAMPTZ,
    delivery_verified_at TIMESTAMPTZ,
    CONSTRAINT buyers_commercial_activation_state_check CHECK (
        commercial_activation_state = ANY (
            ARRAY['discovered','prospective','activated','suspended','revoked']::text[]
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS buyers_name_niche_unique
    ON public.buyers (buyer_name, niche)
    WHERE buyer_name IS NOT NULL AND niche IS NOT NULL;
CREATE INDEX IF NOT EXISTS buyers_org_idx
    ON public.buyers (org_id);
CREATE INDEX IF NOT EXISTS idx_buyers_commercial_activation_state
    ON public.buyers (commercial_activation_state);

CREATE TABLE IF NOT EXISTS public.strike_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tier TEXT NOT NULL DEFAULT 'standard',
    monthly_price_cents INTEGER NOT NULL DEFAULT 0,
    price_per_lead_cents INTEGER NOT NULL DEFAULT 0,
    max_leads_per_day INTEGER NOT NULL DEFAULT 10,
    max_leads_per_month INTEGER NOT NULL DEFAULT 300,
    delivery_channels TEXT[] NOT NULL DEFAULT '{email}'::text[],
    target_buyer TEXT,
    features JSONB NOT NULL DEFAULT '[]'::jsonb,
    lane_count INTEGER NOT NULL DEFAULT 0,
    niches TEXT[] NOT NULL DEFAULT '{}'::text[],
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_public BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT strike_packs_tier_check CHECK (
        tier = ANY (ARRAY['standard','combo','whale','enterprise']::text[])
    )
);

CREATE TABLE IF NOT EXISTS public.buyer_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    buyer_id UUID NOT NULL REFERENCES public.buyers(id) ON DELETE CASCADE,
    pack_id UUID NOT NULL REFERENCES public.strike_packs(id) ON DELETE RESTRICT,
    monthly_price_cents INTEGER NOT NULL,
    price_per_lead_cents INTEGER NOT NULL,
    max_leads_per_day INTEGER NOT NULL,
    max_leads_per_month INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    active BOOLEAN NOT NULL DEFAULT true,
    period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    period_end TIMESTAMPTZ,
    leads_delivered_period INTEGER NOT NULL DEFAULT 0,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT UNIQUE,
    notes TEXT,
    meta JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT buyer_subscriptions_status_check CHECK (
        status = ANY (ARRAY['active','paused','canceled','expired','trialing']::text[])
    )
);

CREATE INDEX IF NOT EXISTS buyer_subs_active_idx
    ON public.buyer_subscriptions (buyer_id) WHERE active = true;
CREATE INDEX IF NOT EXISTS buyer_subs_buyer_idx
    ON public.buyer_subscriptions (buyer_id);
CREATE INDEX IF NOT EXISTS buyer_subs_pack_idx
    ON public.buyer_subscriptions (pack_id);
CREATE INDEX IF NOT EXISTS buyer_subs_stripe_idx
    ON public.buyer_subscriptions (stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.crypto_payment_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    customer_email TEXT NOT NULL,
    customer_account_id TEXT NOT NULL,
    product_slug TEXT NOT NULL,
    tier_level TEXT NOT NULL,
    amount_usdc NUMERIC NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    transaction_signature TEXT,
    sender_address TEXT,
    paid_at TIMESTAMPTZ,
    paid_amount_usdc NUMERIC,
    memo TEXT,
    created_by TEXT DEFAULT 'self-serve',
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours'),
    notes TEXT DEFAULT '',
    CONSTRAINT crypto_payment_requests_amount_usdc_check CHECK (amount_usdc > 0),
    CONSTRAINT crypto_payment_requests_status_check CHECK (
        status = ANY (
            ARRAY[
                'pending','partial','activation_pending','completed',
                'expired','activation_failed','failed'
            ]::text[]
        )
    )
);

CREATE INDEX IF NOT EXISTS crypto_pay_req_account_idx
    ON public.crypto_payment_requests (customer_account_id);
CREATE INDEX IF NOT EXISTS crypto_pay_req_memo_idx
    ON public.crypto_payment_requests (memo) WHERE memo IS NOT NULL;
CREATE INDEX IF NOT EXISTS crypto_pay_req_sender_idx
    ON public.crypto_payment_requests (sender_address) WHERE sender_address IS NOT NULL;
CREATE INDEX IF NOT EXISTS crypto_pay_req_status_idx
    ON public.crypto_payment_requests (status, created_at DESC);

COMMENT ON TABLE public.prospects IS
    'Canonical prospect base table ported from current production truth.';
COMMENT ON TABLE public.buyers IS
    'Canonical buyer base table ported from current production truth.';
COMMENT ON TABLE public.strike_packs IS
    'Canonical strike-pack catalogue base table required by buyer subscriptions.';
COMMENT ON TABLE public.buyer_subscriptions IS
    'Canonical buyer subscription base table required by commercial evidence verification.';
COMMENT ON TABLE public.crypto_payment_requests IS
    'Legacy payment-request evidence table retained for compatibility during migration.';
