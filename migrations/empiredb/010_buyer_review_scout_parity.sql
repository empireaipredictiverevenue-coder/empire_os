-- Empire Data Cloud — active schema parity wave 2A
-- Migration: empiredb/010_buyer_review_scout_parity
-- Source of truth: live canonical production schema, 2026-09-27.
-- Schema only. No data copy, no outbound execution, no cutover.

CREATE TABLE IF NOT EXISTS public.buyer_candidate_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL
        REFERENCES public.prospects(id) ON DELETE RESTRICT,
    entity_id UUID
        REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    contact_name TEXT NOT NULL,
    contact_title TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    offer_key TEXT NOT NULL,
    company_score NUMERIC NOT NULL,
    decision_score NUMERIC NOT NULL,
    evidence JSONB NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    review_note TEXT,
    CONSTRAINT buyer_candidate_reviews_company_score_check
        CHECK (company_score >= 0 AND company_score <= 100),
    CONSTRAINT buyer_candidate_reviews_decision_score_check
        CHECK (decision_score >= 0 AND decision_score <= 1),
    CONSTRAINT buyer_candidate_reviews_status_check
        CHECK (status = ANY (
            ARRAY['pending','approved','rejected','expired']::text[]
        ))
);

CREATE INDEX IF NOT EXISTS buyer_candidate_reviews_state_idx
    ON public.buyer_candidate_reviews (status, proposed_at DESC);

CREATE TABLE IF NOT EXISTS public.buyer_candidate_review_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id UUID NOT NULL
        REFERENCES public.buyer_candidate_reviews(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT buyer_candidate_review_events_event_type_check
        CHECK (event_type = ANY (
            ARRAY['proposed','approved','rejected','outbound_proposed']::text[]
        ))
);

CREATE INDEX IF NOT EXISTS buyer_candidate_review_events_idx
    ON public.buyer_candidate_review_events (review_id, occurred_at);

CREATE TABLE IF NOT EXISTS public.buyer_scout_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT NOT NULL UNIQUE,
    business_name TEXT,
    website TEXT NOT NULL,
    description TEXT,
    buyer_type TEXT NOT NULL DEFAULT 'unknown',
    direct_buyer_score INTEGER NOT NULL DEFAULT 0,
    explicit_direct_buyer_evidence BOOLEAN NOT NULL DEFAULT false,
    target_buyer_pools JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_product_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_corridor_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    query_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    site_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    reconciliation_state TEXT NOT NULL DEFAULT 'NEW_EXTERNAL_BUYER_CANDIDATE',
    canonical_buyer_id UUID
        REFERENCES public.buyers(id) ON DELETE SET NULL,
    canonical_prospect_id UUID
        REFERENCES public.prospects(id) ON DELETE SET NULL,
    review_state TEXT NOT NULL DEFAULT 'discovered',
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT buyer_scout_candidates_direct_buyer_score_check
        CHECK (direct_buyer_score >= 0 AND direct_buyer_score <= 100),
    CONSTRAINT buyer_scout_candidates_reconciliation_state_check
        CHECK (reconciliation_state = ANY (
            ARRAY[
                'NEW_EXTERNAL_BUYER_CANDIDATE',
                'EXISTING_CANONICAL_BUYER',
                'EXISTING_CANONICAL_PROSPECT',
                'BLOCKED_NO_DOMAIN',
                'REVIEW_READY',
                'REJECTED',
                'PROMOTED'
            ]::text[]
        )),
    CONSTRAINT buyer_scout_candidates_review_state_check
        CHECK (review_state = ANY (
            ARRAY['discovered','reconciled','review_ready','rejected','promoted']::text[]
        ))
);

CREATE INDEX IF NOT EXISTS buyer_scout_candidates_buyer_idx
    ON public.buyer_scout_candidates (canonical_buyer_id)
    WHERE canonical_buyer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS buyer_scout_candidates_prospect_idx
    ON public.buyer_scout_candidates (canonical_prospect_id)
    WHERE canonical_prospect_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS buyer_scout_candidates_state_idx
    ON public.buyer_scout_candidates (
        reconciliation_state,
        review_state,
        direct_buyer_score DESC,
        last_seen_at DESC
    );
