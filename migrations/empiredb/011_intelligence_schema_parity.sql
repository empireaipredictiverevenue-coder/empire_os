-- Empire Data Cloud — active schema parity wave 2B
-- Migration: empiredb/011_intelligence_schema_parity
-- Source of truth: live canonical production schema, 2026-09-27.
-- Schema only. No data copy, no canonical cutover.

CREATE TABLE IF NOT EXISTS public.intelligence_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    authority_score NUMERIC NOT NULL DEFAULT 0.5000,
    enabled BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT intelligence_sources_authority_score_check
        CHECK (authority_score >= 0 AND authority_score <= 1),
    CONSTRAINT intelligence_sources_source_key_check
        CHECK (source_key ~ '^[a-z0-9_.:-]{3,120}$'),
    CONSTRAINT intelligence_sources_source_type_check
        CHECK (source_type = ANY (
            ARRAY[
                'public_registry','company_web','news','jobs','search',
                'licensed_data','first_party','social_public','technology',
                'market','weather','other'
            ]::text[]
        ))
);

CREATE TABLE IF NOT EXISTS public.intelligence_people (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    primary_country_code TEXT,
    identity_confidence NUMERIC NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT intelligence_people_identity_confidence_check
        CHECK (identity_confidence >= 0 AND identity_confidence <= 1)
);

CREATE INDEX IF NOT EXISTS intelligence_people_name_idx
    ON public.intelligence_people (normalized_name);

CREATE TABLE IF NOT EXISTS public.intelligence_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    intelligence_domain TEXT NOT NULL,
    definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.intelligence_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL
        REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    signal_type TEXT NOT NULL,
    signal_domain TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    source_id UUID NOT NULL
        REFERENCES public.intelligence_sources(id) ON DELETE RESTRICT,
    strength NUMERIC NOT NULL,
    confidence NUMERIC NOT NULL,
    expires_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT intelligence_signals_strength_check
        CHECK (strength >= 0 AND strength <= 1),
    CONSTRAINT intelligence_signals_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE INDEX IF NOT EXISTS intelligence_signals_domain_idx
    ON public.intelligence_signals (signal_domain, observed_at DESC);

CREATE INDEX IF NOT EXISTS intelligence_signals_entity_idx
    ON public.intelligence_signals (entity_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS public.intelligence_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    fact_key TEXT NOT NULL,
    fact_value JSONB NOT NULL,
    source_id UUID NOT NULL
        REFERENCES public.intelligence_sources(id) ON DELETE RESTRICT,
    confidence NUMERIC NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    evidence_uri TEXT,
    evidence_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT intelligence_facts_time_check
        CHECK (last_seen_at >= first_seen_at),
    CONSTRAINT intelligence_facts_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT intelligence_facts_entity_type_check
        CHECK (entity_type = ANY (
            ARRAY[
                'company','person','employment','market',
                'opportunity','offer'
            ]::text[]
        ))
);

CREATE INDEX IF NOT EXISTS intelligence_facts_lookup_idx
    ON public.intelligence_facts
       (entity_type, entity_id, fact_key, last_seen_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_intelligence_facts_evidence_hash
    ON public.intelligence_facts (evidence_hash)
    WHERE evidence_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.intelligence_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    score_type TEXT NOT NULL,
    score NUMERIC NOT NULL,
    confidence NUMERIC NOT NULL,
    model_key TEXT NOT NULL,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT intelligence_scores_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT intelligence_scores_entity_type_check
        CHECK (entity_type = ANY (
            ARRAY['company','person','opportunity','offer']::text[]
        ))
);

CREATE INDEX IF NOT EXISTS intelligence_scores_lookup_idx
    ON public.intelligence_scores
       (entity_type, entity_id, score_type, scored_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_intelligence_scores_materialized
    ON public.intelligence_scores
       (entity_type, entity_id, score_type, model_key, scored_at);

CREATE TABLE IF NOT EXISTS public.intelligence_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID
        REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    person_id UUID
        REFERENCES public.intelligence_people(id) ON DELETE RESTRICT,
    opportunity_id UUID,
    outcome_type TEXT NOT NULL,
    outcome_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    source_system TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS intelligence_outcomes_entity_idx
    ON public.intelligence_outcomes (entity_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS public.intelligence_contact_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id UUID
        REFERENCES public.intelligence_people(id) ON DELETE RESTRICT,
    entity_id UUID
        REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    contact_type TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    verification_state TEXT NOT NULL DEFAULT 'observed',
    source_id UUID
        REFERENCES public.intelligence_sources(id) ON DELETE RESTRICT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    verified_at TIMESTAMPTZ,
    confidence NUMERIC NOT NULL DEFAULT 0,
    CONSTRAINT intelligence_contact_points_subject_check
        CHECK (person_id IS NOT NULL OR entity_id IS NOT NULL),
    CONSTRAINT intelligence_contact_points_confidence_check
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT intelligence_contact_points_contact_type_check
        CHECK (contact_type = ANY (
            ARRAY[
                'work_email','business_phone','mobile',
                'professional_url','other'
            ]::text[]
        )),
    CONSTRAINT intelligence_contact_points_verification_state_check
        CHECK (verification_state = ANY (
            ARRAY['observed','verified','invalid','suppressed']::text[]
        ))
);

CREATE INDEX IF NOT EXISTS intelligence_contact_entity_idx
    ON public.intelligence_contact_points (entity_id);

CREATE INDEX IF NOT EXISTS intelligence_contact_person_idx
    ON public.intelligence_contact_points (person_id);
