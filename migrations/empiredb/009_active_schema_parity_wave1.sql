-- Empire Data Cloud — active production schema parity wave 1
-- Migration: empiredb/009_active_schema_parity_wave1
-- Source of truth: live canonical production schema, 2026-09-27.
-- Tables only. No data copy, no outbound execution, no cutover.
-- Tenant/RLS hardening is handled separately before canonical activation.

CREATE TABLE IF NOT EXISTS public.prospect_qualifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL
        REFERENCES public.prospects(id) ON DELETE RESTRICT,
    entity_id UUID
        REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    score NUMERIC DEFAULT 0,
    tier TEXT NOT NULL DEFAULT 'dead',
    data_completeness_score NUMERIC NOT NULL DEFAULT 0,
    business_presence_score NUMERIC DEFAULT 0,
    market_fit_score NUMERIC DEFAULT 0,
    engagement_potential_score NUMERIC DEFAULT 0,
    enrichment_quality_score NUMERIC DEFAULT 0,
    recommended_action TEXT,
    scoring_engine TEXT NOT NULL DEFAULT 'empire_os.lead_scoring',
    scoring_version TEXT NOT NULL DEFAULT 'v1',
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'scored',
    scored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    evidence_confidence NUMERIC,
    observed_dimensions JSONB NOT NULL DEFAULT '[]'::jsonb,
    unknown_dimensions JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT prospect_qualifications_prospect_engine_version_key
        UNIQUE (prospect_id, scoring_engine, scoring_version),
    CONSTRAINT prospect_qualifications_evidence_confidence_check
        CHECK (
            evidence_confidence IS NULL
            OR (evidence_confidence >= 0 AND evidence_confidence <= 1)
        ),
    CONSTRAINT prospect_qualifications_observed_dimensions_array_check
        CHECK (jsonb_typeof(observed_dimensions) = 'array'),
    CONSTRAINT prospect_qualifications_unknown_dimensions_array_check
        CHECK (jsonb_typeof(unknown_dimensions) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_prospect_qualifications_prospect
    ON public.prospect_qualifications (prospect_id);
CREATE INDEX IF NOT EXISTS idx_prospect_qualifications_score
    ON public.prospect_qualifications (score DESC);
CREATE INDEX IF NOT EXISTS idx_prospect_qualifications_scored
    ON public.prospect_qualifications (scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_prospect_qualifications_status
    ON public.prospect_qualifications (status);
CREATE INDEX IF NOT EXISTS idx_prospect_qualifications_tier
    ON public.prospect_qualifications (tier);

CREATE TABLE IF NOT EXISTS public.commercial_product_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL
        REFERENCES public.commercial_products(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    version_state TEXT NOT NULL DEFAULT 'UNKNOWN',
    billing_model TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    price_basis JSONB NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
    acquisition_cost_basis JSONB NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
    fulfilment_cost_basis JSONB NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
    margin_policy JSONB NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    rejected_at TIMESTAMPTZ,
    rejected_by TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT commercial_product_versions_product_id_version_key
        UNIQUE (product_id, version),
    CONSTRAINT commercial_product_versions_version_state_check
        CHECK (version_state = ANY (
            ARRAY['UNKNOWN','DRAFT','PENDING','VERIFIED','RETIRED','REJECTED']::text[]
        )),
    CONSTRAINT commercial_product_versions_effective_window_check
        CHECK (
            effective_until IS NULL
            OR effective_from IS NULL
            OR effective_until > effective_from
        )
);

CREATE INDEX IF NOT EXISTS commercial_product_versions_product_idx
    ON public.commercial_product_versions (product_id, version DESC);
CREATE INDEX IF NOT EXISTS commercial_product_versions_state_idx
    ON public.commercial_product_versions
       (version_state, effective_from, effective_until);

CREATE TABLE IF NOT EXISTS public.commercial_product_catalog_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL
        REFERENCES public.commercial_products(id) ON DELETE CASCADE,
    product_version_id UUID
        REFERENCES public.commercial_product_versions(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS commercial_product_catalog_events_product_idx
    ON public.commercial_product_catalog_events (product_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS public.outbound_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID REFERENCES public.prospects(id) ON DELETE RESTRICT,
    entity_id UUID REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    buyer_id UUID REFERENCES public.buyers(id) ON DELETE RESTRICT,
    opportunity_id UUID REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    normalized_recipient TEXT NOT NULL,
    subject TEXT,
    body_text TEXT NOT NULL,
    body_html TEXT,
    offer_key TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    idempotency_key TEXT NOT NULL UNIQUE,
    proposed_by TEXT NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT outbound_intents_channel_check
        CHECK (channel = ANY (ARRAY['email','sms','voice','a2a']::text[])),
    CONSTRAINT outbound_intents_status_check
        CHECK (status = ANY (
            ARRAY[
                'draft','pending_approval','approved','rejected','sent',
                'delivered','replied','suppressed','failed','cancelled'
            ]::text[]
        )),
    CONSTRAINT outbound_intents_subject_check
        CHECK (
            prospect_id IS NOT NULL
            OR entity_id IS NOT NULL
            OR buyer_id IS NOT NULL
        )
);

CREATE INDEX IF NOT EXISTS outbound_intents_entity_idx
    ON public.outbound_intents (entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS outbound_intents_state_idx
    ON public.outbound_intents (status, created_at);

CREATE TABLE IF NOT EXISTS public.outbound_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id UUID NOT NULL
        REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    provider_message_id TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT outbound_events_event_type_check
        CHECK (event_type = ANY (
            ARRAY[
                'proposed','approved','rejected','send_attempt','sent',
                'delivered','failed','reply_received','reply_classified',
                'suppressed','cancelled','delivery_delayed','bounced',
                'complained','opened','clicked','call_ringing',
                'call_answered','call_completed','call_busy',
                'call_unanswered','call_rejected','call_failed'
            ]::text[]
        ))
);

CREATE INDEX IF NOT EXISTS outbound_events_intent_idx
    ON public.outbound_events (intent_id, occurred_at);

CREATE TABLE IF NOT EXISTS public.outbound_replies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id UUID NOT NULL
        REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
    provider_message_id TEXT,
    from_contact TEXT NOT NULL,
    normalized_from_contact TEXT NOT NULL,
    subject TEXT,
    body_text TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'unclassified',
    confidence NUMERIC,
    received_at TIMESTAMPTZ NOT NULL,
    classified_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT outbound_replies_intent_provider_key
        UNIQUE (intent_id, provider_message_id),
    CONSTRAINT outbound_replies_classification_check
        CHECK (classification = ANY (
            ARRAY[
                'unclassified','positive','negative','question','objection',
                'later','unsubscribe','bounce','other'
            ]::text[]
        )),
    CONSTRAINT outbound_replies_confidence_check
        CHECK (
            confidence IS NULL
            OR (confidence >= 0 AND confidence <= 1)
        )
);

CREATE INDEX IF NOT EXISTS outbound_replies_state_idx
    ON public.outbound_replies (classification, received_at DESC);

CREATE TABLE IF NOT EXISTS public.outbound_suppressions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_contact TEXT NOT NULL UNIQUE,
    contact_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT outbound_suppressions_contact_type_check
        CHECK (contact_type = ANY (ARRAY['email','phone','domain']::text[]))
);
