-- Phase 10 Predictive Cloud V3 evidence-backed forecast records.
-- Staged only: no automated commercial execution or production apply.
BEGIN;

CREATE TABLE IF NOT EXISTS public.predictive_signal_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  metric text NOT NULL,
  dimension_key text NOT NULL DEFAULT 'global',
  observed_date date NOT NULL,
  value numeric NOT NULL CHECK (value >= 0),
  source text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(metric, dimension_key, observed_date, source)
);

CREATE TABLE IF NOT EXISTS public.predictive_forecasts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  metric text NOT NULL,
  dimension_key text NOT NULL DEFAULT 'global',
  horizon_days integer NOT NULL CHECK (horizon_days BETWEEN 1 AND 365),
  sample_count integer NOT NULL CHECK (sample_count >= 0),
  latest_observed_value numeric,
  predicted_value numeric,
  daily_slope numeric,
  r_squared numeric CHECK (r_squared IS NULL OR r_squared BETWEEN 0 AND 1),
  evidence_confidence numeric CHECK (
    evidence_confidence IS NULL OR evidence_confidence BETWEEN 0 AND 1
  ),
  direction text NOT NULL CHECK (
    direction IN ('up','down','flat','insufficient_history')
  ),
  reason text,
  source text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  generated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.predictive_signal_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.predictive_forecasts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.predictive_signal_observations,
  public.predictive_forecasts
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.predictive_signal_observations,
  public.predictive_forecasts
TO service_role;

COMMIT;
