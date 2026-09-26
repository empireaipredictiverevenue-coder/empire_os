-- Empire OS: canonical business identity layer
-- Version: 001
-- Purpose: preserve source prospects while introducing canonical business entities.
-- Safety: append-only schema creation; does not UPDATE or DELETE prospects.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS business_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    canonical_niche TEXT,
    canonical_metro TEXT,
    canonical_phone TEXT,
    canonical_website TEXT,
    identity_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    resolution_state TEXT NOT NULL DEFAULT 'unresolved',
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_business_entities_normalized_name
    ON business_entities (normalized_name);

CREATE INDEX IF NOT EXISTS idx_business_entities_niche_metro
    ON business_entities (canonical_niche, canonical_metro);

CREATE TABLE IF NOT EXISTS prospect_entity_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE RESTRICT,
    entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE RESTRICT,
    match_method TEXT NOT NULL,
    match_score NUMERIC(5,4),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (prospect_id)
);

CREATE INDEX IF NOT EXISTS idx_prospect_entity_links_entity
    ON prospect_entity_links (entity_id);

CREATE INDEX IF NOT EXISTS idx_prospect_entity_links_active
    ON prospect_entity_links (active);

CREATE TABLE IF NOT EXISTS business_entity_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES business_entities(id) ON DELETE RESTRICT,
    prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE RESTRICT,
    field_name TEXT NOT NULL,
    observed_value JSONB,
    conflict_type TEXT NOT NULL,
    resolution_state TEXT NOT NULL DEFAULT 'unresolved',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_business_entity_conflicts_entity
    ON business_entity_conflicts (entity_id);

CREATE INDEX IF NOT EXISTS idx_business_entity_conflicts_state
    ON business_entity_conflicts (resolution_state);

COMMENT ON TABLE business_entities IS
    'Canonical business identity; never replaces source prospect records.';

COMMENT ON TABLE prospect_entity_links IS
    'Immutable lineage from a source prospect to its current canonical business entity.';

COMMENT ON TABLE business_entity_conflicts IS
    'Explicit identity/data conflicts retained for review rather than silently merged.';
