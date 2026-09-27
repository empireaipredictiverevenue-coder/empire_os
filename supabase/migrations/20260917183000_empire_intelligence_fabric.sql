-- Empire Intelligence Fabric: temporal, provenance-aware commercial graph.
-- Forward-only. Creates intelligence storage only; no CRM leads, outreach, or execution.
BEGIN;

CREATE TABLE public.intelligence_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key text NOT NULL UNIQUE CHECK (source_key ~ '^[a-z0-9_.:-]{3,120}$'),
    source_type text NOT NULL CHECK (source_type IN (
        'public_registry','company_web','news','jobs','search','licensed_data',
        'first_party','social_public','technology','market','weather','other'
    )),
    display_name text NOT NULL,
    authority_score numeric(5,4) NOT NULL DEFAULT 0.5000 CHECK (authority_score BETWEEN 0 AND 1),
    enabled boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE public.intelligence_people (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name text NOT NULL,
    normalized_name text NOT NULL,
    primary_country_code text,
    identity_confidence numeric(5,4) NOT NULL DEFAULT 0 CHECK (identity_confidence BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX intelligence_people_name_idx ON public.intelligence_people(normalized_name);

CREATE TABLE public.intelligence_employment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id uuid NOT NULL REFERENCES public.intelligence_people(id) ON DELETE RESTRICT,
    entity_id uuid NOT NULL REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    title text NOT NULL,
    normalized_title text NOT NULL,
    seniority text,
    department text,
    buying_role text CHECK (buying_role IS NULL OR buying_role IN (
        'economic_buyer','functional_buyer','champion','technical_approver',
        'commercial_approver','influencer','user','unknown'
    )),
    is_current boolean NOT NULL DEFAULT true,
    valid_from timestamptz,
    valid_to timestamptz,
    confidence numeric(5,4) NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX intelligence_employment_entity_idx
    ON public.intelligence_employment(entity_id, is_current);
CREATE INDEX intelligence_employment_person_idx
    ON public.intelligence_employment(person_id, is_current);

CREATE TABLE public.intelligence_contact_points (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id uuid REFERENCES public.intelligence_people(id) ON DELETE RESTRICT,
    entity_id uuid REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    contact_type text NOT NULL CHECK (contact_type IN ('work_email','business_phone','mobile','professional_url','other')),
    value text NOT NULL,
    normalized_value text NOT NULL,
    verification_state text NOT NULL DEFAULT 'observed' CHECK (verification_state IN ('observed','verified','invalid','suppressed')),
    source_id uuid REFERENCES public.intelligence_sources(id) ON DELETE RESTRICT,
    first_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    verified_at timestamptz,
    confidence numeric(5,4) NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 1),
    CHECK (person_id IS NOT NULL OR entity_id IS NOT NULL)
);
CREATE INDEX intelligence_contact_person_idx ON public.intelligence_contact_points(person_id);
CREATE INDEX intelligence_contact_entity_idx ON public.intelligence_contact_points(entity_id);

CREATE TABLE public.intelligence_facts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL CHECK (entity_type IN ('company','person','employment','market','opportunity','offer')),
    entity_id uuid NOT NULL,
    fact_key text NOT NULL,
    fact_value jsonb NOT NULL,
    source_id uuid NOT NULL REFERENCES public.intelligence_sources(id) ON DELETE RESTRICT,
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    valid_from timestamptz,
    valid_to timestamptz,
    evidence_uri text,
    evidence_hash text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (last_seen_at >= first_seen_at)
);
CREATE INDEX intelligence_facts_lookup_idx ON public.intelligence_facts(entity_type, entity_id, fact_key, last_seen_at DESC);
CREATE TABLE public.intelligence_signals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id uuid NOT NULL REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    signal_type text NOT NULL,
    signal_domain text NOT NULL,
    observed_at timestamptz NOT NULL,
    source_id uuid NOT NULL REFERENCES public.intelligence_sources(id) ON DELETE RESTRICT,
    strength numeric(5,4) NOT NULL CHECK (strength BETWEEN 0 AND 1),
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    expires_at timestamptz,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX intelligence_signals_entity_idx ON public.intelligence_signals(entity_id, observed_at DESC);
CREATE INDEX intelligence_signals_domain_idx ON public.intelligence_signals(signal_domain, observed_at DESC);

CREATE TABLE public.intelligence_segments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_key text NOT NULL UNIQUE,
    display_name text NOT NULL,
    intelligence_domain text NOT NULL,
    definition jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE public.intelligence_segment_membership (
    entity_id uuid NOT NULL REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    segment_id uuid NOT NULL REFERENCES public.intelligence_segments(id) ON DELETE RESTRICT,
    score numeric(7,4) NOT NULL CHECK (score BETWEEN 0 AND 100),
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    scored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(entity_id, segment_id)
);
CREATE TABLE public.intelligence_scores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL CHECK (entity_type IN ('company','person','opportunity','offer')),
    entity_id uuid NOT NULL,
    score_type text NOT NULL,
    score numeric(9,4) NOT NULL,
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    model_key text NOT NULL,
    features jsonb NOT NULL DEFAULT '{}'::jsonb,
    explanation jsonb NOT NULL DEFAULT '{}'::jsonb,
    scored_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX intelligence_scores_lookup_idx ON public.intelligence_scores(entity_type, entity_id, score_type, scored_at DESC);

CREATE TABLE public.intelligence_offer_fit (
    entity_id uuid NOT NULL REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    offer_key text NOT NULL,
    fit_score numeric(7,4) NOT NULL CHECK (fit_score BETWEEN 0 AND 100),
    expected_value numeric,
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    scored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(entity_id, offer_key)
);

CREATE TABLE public.intelligence_outcomes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id uuid REFERENCES public.business_entities(id) ON DELETE RESTRICT,
    person_id uuid REFERENCES public.intelligence_people(id) ON DELETE RESTRICT,
    opportunity_id uuid,
    outcome_type text NOT NULL,
    outcome_value jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL,
    source_system text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX intelligence_outcomes_entity_idx ON public.intelligence_outcomes(entity_id, occurred_at DESC);
ALTER TABLE public.intelligence_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_people ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_employment ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_contact_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_segment_membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_offer_fit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_outcomes ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.intelligence_sources, public.intelligence_people,
    public.intelligence_employment, public.intelligence_contact_points,
    public.intelligence_facts, public.intelligence_signals,
    public.intelligence_segments, public.intelligence_segment_membership,
    public.intelligence_scores, public.intelligence_offer_fit,
    public.intelligence_outcomes
FROM PUBLIC, anon, authenticated;

GRANT SELECT, INSERT, UPDATE ON public.intelligence_sources, public.intelligence_people,
    public.intelligence_employment, public.intelligence_contact_points,
    public.intelligence_facts, public.intelligence_signals,
    public.intelligence_segments, public.intelligence_segment_membership,
    public.intelligence_scores, public.intelligence_offer_fit,
    public.intelligence_outcomes TO service_role;
INSERT INTO public.intelligence_segments(segment_key,display_name,intelligence_domain,definition) VALUES
('tam_software','Software / MRR TAM','market','{"offer_family":"software"}'::jsonb),
('tam_high_ticket','High-Ticket TAM','opportunity','{"offer_family":"high_ticket"}'::jsonb),
('tam_managed_services','Managed Services TAM','opportunity','{"offer_family":"managed_services"}'::jsonb),
('tam_white_label','White-Label TAM','buyer','{"offer_family":"white_label"}'::jsonb),
('tam_enterprise','Enterprise TAM','buyer','{"offer_family":"enterprise"}'::jsonb),
('tam_escrow_payments','Escrow / Payments TAM','revenue','{"offer_family":"escrow_payments"}'::jsonb)
ON CONFLICT (segment_key) DO NOTHING;

COMMENT ON TABLE public.intelligence_facts IS 'Temporal source-backed facts; conflicting observations remain visible rather than silently overwritten.';
COMMENT ON TABLE public.intelligence_signals IS 'Time-bound commercial signals spanning all Empire intelligence domains.';
COMMENT ON TABLE public.intelligence_scores IS 'Versioned model scores with confidence, features and explanation for calibration and outcome learning.';
COMMENT ON TABLE public.intelligence_outcomes IS 'Observed commercial outcomes used to calibrate Omega, causal models and Astra decisions.';

COMMIT;
