-- Phase 11 read-only experiment analysis records.
-- Staged only: no traffic mutation, rollout, pricing change or execution authority.
BEGIN;

CREATE TABLE IF NOT EXISTS public.experiment_analysis_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_key text NOT NULL,
  metric text NOT NULL,
  control_count integer NOT NULL CHECK (control_count >= 0),
  treatment_count integer NOT NULL CHECK (treatment_count >= 0),
  control_mean numeric,
  treatment_mean numeric,
  absolute_lift numeric,
  relative_lift numeric,
  assignment_integrity_verified boolean NOT NULL DEFAULT false,
  exposure_integrity_verified boolean NOT NULL DEFAULT false,
  outcome_window_closed boolean NOT NULL DEFAULT false,
  causal_claim_eligible boolean NOT NULL DEFAULT false,
  interpretation text NOT NULL,
  evidence_refs text[] NOT NULL,
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  analyzed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.experiment_analysis_records ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.experiment_analysis_records
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.experiment_analysis_records
TO service_role;

COMMIT;
