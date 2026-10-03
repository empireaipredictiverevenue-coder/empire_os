-- EmpireDB migration 036: outbound policy governance
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Append-only policy/version and shadow-evaluation evidence.
-- No runtime grants or authority expansion in this migration.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbound_policy_manifests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    policy_name TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    source_commit TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    policy_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    activation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, policy_name, policy_version, fingerprint),
    CHECK (activation_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_policy_manifests_name
    ON public.outbound_policy_manifests(
        scope_key, policy_name, created_at DESC
    );

CREATE TABLE IF NOT EXISTS public.outbound_policy_shadow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    run_key TEXT NOT NULL,
    current_policy_fingerprint TEXT NOT NULL,
    candidate_policy_fingerprint TEXT NOT NULL,
    samples INTEGER NOT NULL DEFAULT 0 CHECK (samples >= 0),
    disagreements INTEGER NOT NULL DEFAULT 0 CHECK (disagreements >= 0),
    disagreement_rate NUMERIC NOT NULL DEFAULT 0 CHECK (
        disagreement_rate >= 0 AND disagreement_rate <= 1
    ),
    candidate_stricter INTEGER NOT NULL DEFAULT 0 CHECK (candidate_stricter >= 0),
    candidate_looser INTEGER NOT NULL DEFAULT 0 CHECK (candidate_looser >= 0),
    promotion_status TEXT NOT NULL CHECK (
        promotion_status IN (
            'NOT_READY',
            'REVIEW_REQUIRED',
            'READY_FOR_REVIEW'
        )
    ),
    blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
    review_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    activation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, run_key),
    CHECK (activation_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_policy_shadow_runs_time
    ON public.outbound_policy_shadow_runs(
        scope_key, observed_at DESC
    );

COMMENT ON TABLE public.outbound_policy_manifests IS
    'Append-only Ringleader policy manifests; migration 034 cannot authorize activation.';

COMMENT ON TABLE public.outbound_policy_shadow_runs IS
    'Append-only shadow/counterfactual policy evaluation evidence; promotion remains release-gated.';

COMMIT;
