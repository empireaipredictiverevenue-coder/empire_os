-- Phase 11 Experiment + Causal Engine foundation.
-- Staged only: no traffic mutation, rollout or pricing changes.
BEGIN;

CREATE TABLE IF NOT EXISTS public.experiment_assignment_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id uuid NOT NULL
    REFERENCES public.gtm_experiments(id) ON DELETE RESTRICT,
  subject_key text NOT NULL,
  arm text NOT NULL,
  assignment_kind text NOT NULL CHECK (
    assignment_kind IN ('holdout_control','treatment')
  ),
  deterministic_bucket integer NOT NULL CHECK (
    deterministic_bucket BETWEEN 0 AND 9999
  ),
  planned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(experiment_id, subject_key)
);
CREATE TABLE IF NOT EXISTS public.experiment_outcome_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id uuid NOT NULL
    REFERENCES public.gtm_experiments(id) ON DELETE RESTRICT,
  subject_key text NOT NULL,
  arm text NOT NULL,
  metric text NOT NULL,
  observed_value numeric NOT NULL CHECK (observed_value >= 0),
  observed_at timestamptz NOT NULL,
  source text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_experiment_outcome_metric
  ON public.experiment_outcome_observations(
    experiment_id,metric,arm,observed_at DESC
  );
ALTER TABLE public.experiment_assignment_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experiment_outcome_observations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.experiment_assignment_plans,
  public.experiment_outcome_observations
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.experiment_assignment_plans,
  public.experiment_outcome_observations
TO service_role;

COMMIT;
