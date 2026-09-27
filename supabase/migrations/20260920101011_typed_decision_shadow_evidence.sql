-- Typed-decision / Jev shadow evidence foundation.
-- STAGED ONLY. This migration is not production activation.
--
-- Goals:
-- - private schema, not exposed through public Data API by default
-- - append-oriented evidence records
-- - no anon/authenticated access
-- - no execution/commercial authority
-- - predictions/shadow outputs remain distinct from verified outcomes

CREATE SCHEMA IF NOT EXISTS empire_eval;

REVOKE ALL ON SCHEMA empire_eval FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA empire_eval TO service_role;

CREATE TABLE empire_eval.shadow_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_key text NOT NULL,
    case_id text NOT NULL,
    source_ref text NOT NULL,
    point_in_time_ref text NOT NULL,
    inputs jsonb NOT NULL CHECK (jsonb_typeof(inputs) = 'object'),
    observed_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(observed_metadata) = 'object'),
    synthetic_test_fixture boolean NOT NULL DEFAULT false,
    commercial_evidence boolean NOT NULL DEFAULT false
        CHECK (commercial_evidence = false),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (task_key, case_id, source_ref)
);

CREATE INDEX shadow_observations_task_created_idx
    ON empire_eval.shadow_observations (task_key, created_at DESC);

CREATE TABLE empire_eval.reviewed_labels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    observation_id uuid NOT NULL
        REFERENCES empire_eval.shadow_observations(id),
    proposed_label text NOT NULL,
    label_source text NOT NULL CHECK (
        label_source IN (
            'human_review',
            'verified_outcome',
            'independent_verifier',
            'deterministic_rule'
        )
    ),
    reviewer_ref text,
    review_state text NOT NULL CHECK (
        review_state IN ('pending', 'accepted', 'rejected', 'disputed')
    ),
    source_ref text NOT NULL,
    point_in_time_ref text NOT NULL,
    tenant_key text,
    notes_ref text,
    commercial_evidence boolean NOT NULL DEFAULT false
        CHECK (commercial_evidence = false),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (review_state <> 'accepted' OR reviewer_ref IS NOT NULL)
);

CREATE INDEX reviewed_labels_observation_created_idx
    ON empire_eval.reviewed_labels (observation_id, created_at DESC);

CREATE TABLE empire_eval.provider_outputs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    observation_id uuid NOT NULL
        REFERENCES empire_eval.shadow_observations(id),
    provider_key text NOT NULL,
    model_key text NOT NULL,
    decision_schema_ref text NOT NULL,
    predicted_label text NOT NULL,
    confidence numeric NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    latency_ms numeric NOT NULL CHECK (latency_ms >= 0),
    input_tokens bigint CHECK (input_tokens IS NULL OR input_tokens >= 0),
    cost_cents numeric CHECK (cost_cents IS NULL OR cost_cents >= 0),
    source_ref text NOT NULL,
    shadow_only boolean NOT NULL DEFAULT true CHECK (shadow_only = true),
    execution_authority text NOT NULL DEFAULT 'none'
        CHECK (execution_authority = 'none'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX provider_outputs_observation_provider_idx
    ON empire_eval.provider_outputs (
        observation_id,
        provider_key,
        model_key,
        created_at DESC
    );

CREATE TABLE empire_eval.dataset_manifests (
    dataset_id text NOT NULL,
    version text NOT NULL,
    sha256 text NOT NULL CHECK (length(sha256) = 64),
    case_count integer NOT NULL CHECK (case_count >= 0),
    synthetic_test_fixture_count integer NOT NULL CHECK (
        synthetic_test_fixture_count >= 0
    ),
    real_labeled_case_count integer NOT NULL CHECK (
        real_labeled_case_count >= 0
    ),
    task_keys text[] NOT NULL DEFAULT ARRAY[]::text[],
    eligible_for_production_promotion_evidence boolean NOT NULL DEFAULT false,
    commercial_evidence boolean NOT NULL DEFAULT false
        CHECK (commercial_evidence = false),
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_id, version),
    UNIQUE (sha256),
    CHECK (
        case_count =
        synthetic_test_fixture_count + real_labeled_case_count
    ),
    CHECK (
        eligible_for_production_promotion_evidence = false
        OR synthetic_test_fixture_count = 0
    )
);

CREATE TABLE empire_eval.eval_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id text NOT NULL,
    dataset_version text NOT NULL,
    task_key text NOT NULL,
    provider_key text NOT NULL,
    model_key text NOT NULL,
    sample_count integer NOT NULL CHECK (sample_count >= 0),
    metrics jsonb NOT NULL CHECK (jsonb_typeof(metrics) = 'object'),
    source_refs text[] NOT NULL DEFAULT ARRAY[]::text[],
    winner_selected boolean NOT NULL DEFAULT false CHECK (winner_selected = false),
    production_provider_selected boolean NOT NULL DEFAULT false
        CHECK (production_provider_selected = false),
    execution_authority text NOT NULL DEFAULT 'none'
        CHECK (execution_authority = 'none'),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (dataset_id, dataset_version)
        REFERENCES empire_eval.dataset_manifests(dataset_id, version)
);

CREATE INDEX eval_reports_task_provider_idx
    ON empire_eval.eval_reports (
        task_key,
        provider_key,
        model_key,
        created_at DESC
    );

CREATE TABLE empire_eval.shadow_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    observation_id uuid NOT NULL
        REFERENCES empire_eval.shadow_observations(id),
    incumbent_provider text NOT NULL,
    incumbent_decision text NOT NULL,
    candidate_provider text NOT NULL,
    candidate_model text NOT NULL,
    candidate_decision text NOT NULL,
    candidate_confidence numeric NOT NULL
        CHECK (candidate_confidence >= 0 AND candidate_confidence <= 1),
    decision_schema_ref text NOT NULL,
    agreement boolean NOT NULL,
    verified_outcome_ref text,
    candidate_controlled_live_routing boolean NOT NULL DEFAULT false
        CHECK (candidate_controlled_live_routing = false),
    execution_performed boolean NOT NULL DEFAULT false
        CHECK (execution_performed = false),
    execution_authority text NOT NULL DEFAULT 'none'
        CHECK (execution_authority = 'none'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX shadow_decisions_observation_created_idx
    ON empire_eval.shadow_decisions (observation_id, created_at DESC);

ALTER TABLE empire_eval.shadow_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE empire_eval.reviewed_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE empire_eval.provider_outputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE empire_eval.dataset_manifests ENABLE ROW LEVEL SECURITY;
ALTER TABLE empire_eval.eval_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE empire_eval.shadow_decisions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON ALL TABLES IN SCHEMA empire_eval
    FROM PUBLIC, anon, authenticated;

GRANT SELECT, INSERT ON
    empire_eval.shadow_observations,
    empire_eval.reviewed_labels,
    empire_eval.provider_outputs,
    empire_eval.dataset_manifests,
    empire_eval.eval_reports,
    empire_eval.shadow_decisions
TO service_role;

-- Explicitly preserve append-only semantics for service_role.
REVOKE UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA empire_eval
    FROM service_role;

COMMENT ON SCHEMA empire_eval IS
    'Private evaluation/shadow evidence. No commercial or execution authority.';

COMMENT ON TABLE empire_eval.shadow_observations IS
    'Point-in-time observations prepared for typed-decision evaluation only.';

COMMENT ON TABLE empire_eval.provider_outputs IS
    'Observed provider/model outputs collected in evaluation or shadow mode only.';

COMMENT ON TABLE empire_eval.dataset_manifests IS
    'Frozen typed-decision dataset manifests and provenance fingerprints.';

COMMENT ON TABLE empire_eval.eval_reports IS
    'Evaluation reports; never select or activate a production provider by themselves.';
