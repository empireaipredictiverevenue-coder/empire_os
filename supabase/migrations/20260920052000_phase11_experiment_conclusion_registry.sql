-- Phase 11 append-only causal-review conclusion registry.
-- Staged only: no rollout, traffic or pricing mutation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_experiment_conclusion_writer'
  ) THEN
    CREATE ROLE empire_experiment_conclusion_writer NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_experiment_conclusion_reader'
  ) THEN
    CREATE ROLE empire_experiment_conclusion_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public
TO empire_experiment_conclusion_writer,
   empire_experiment_conclusion_reader;

REVOKE empire_experiment_conclusion_writer,
       empire_experiment_conclusion_reader
FROM service_role;

CREATE TABLE IF NOT EXISTS public.experiment_causal_conclusions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conclusion_key text NOT NULL UNIQUE,
  experiment_key text NOT NULL,
  metric text NOT NULL,
  control_count integer NOT NULL CHECK (control_count > 0),
  treatment_count integer NOT NULL CHECK (treatment_count > 0),
  control_mean numeric NOT NULL CHECK (control_mean >= 0),
  treatment_mean numeric NOT NULL CHECK (treatment_mean >= 0),
  absolute_lift numeric NOT NULL,
  relative_lift numeric,
  effect_direction text NOT NULL CHECK (
    effect_direction IN (
      'positive_observed_lift',
      'negative_observed_lift',
      'no_observed_lift'
    )
  ),
  assignment_integrity_verified boolean NOT NULL DEFAULT true
    CHECK (assignment_integrity_verified),
  exposure_integrity_verified boolean NOT NULL DEFAULT true
    CHECK (exposure_integrity_verified),
  outcome_window_closed boolean NOT NULL DEFAULT true
    CHECK (outcome_window_closed),
  causal_review_eligible boolean NOT NULL DEFAULT true
    CHECK (causal_review_eligible),
  statistical_significance_available boolean NOT NULL DEFAULT false
    CHECK (NOT statistical_significance_available),
  evidence_refs text[] NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  traffic_mutation boolean NOT NULL DEFAULT false
    CHECK (NOT traffic_mutation),
  rollout_enabled boolean NOT NULL DEFAULT false
    CHECK (NOT rollout_enabled),
  pricing_mutation boolean NOT NULL DEFAULT false
    CHECK (NOT pricing_mutation),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.experiment_causal_conclusions ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS guard_experiment_conclusions_append_only
ON public.experiment_causal_conclusions;
CREATE TRIGGER guard_experiment_conclusions_append_only
BEFORE UPDATE OR DELETE ON public.experiment_causal_conclusions
FOR EACH ROW EXECUTE FUNCTION
  public.guard_experiment_registry_append_only();

REVOKE ALL ON public.experiment_causal_conclusions
FROM PUBLIC,anon,authenticated,service_role,
     empire_experiment_conclusion_writer,
     empire_experiment_conclusion_reader;

GRANT SELECT ON public.experiment_causal_conclusions
TO empire_experiment_conclusion_reader;

CREATE OR REPLACE FUNCTION public.record_experiment_causal_conclusion(
  p_conclusion_key text,
  p_experiment_key text,
  p_metric text,
  p_control_count integer,
  p_treatment_count integer,
  p_control_mean numeric,
  p_treatment_mean numeric,
  p_assignment_integrity_verified boolean,
  p_exposure_integrity_verified boolean,
  p_outcome_window_closed boolean,
  p_evidence_refs text[],
  p_evidence jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.experiment_causal_conclusions%ROWTYPE;
  observed_lift numeric;
  observed_relative numeric;
  direction text;
BEGIN
  IF trim(COALESCE(p_conclusion_key,''))='' THEN
    RAISE EXCEPTION 'conclusion_key required';
  END IF;
  IF trim(COALESCE(p_experiment_key,''))='' THEN
    RAISE EXCEPTION 'experiment_key required';
  END IF;
  IF trim(COALESCE(p_metric,''))='' THEN
    RAISE EXCEPTION 'metric required';
  END IF;
  IF p_control_count < 1 OR p_treatment_count < 1 THEN
    RAISE EXCEPTION 'conclusion requires observed arm samples';
  END IF;
  IF p_control_mean < 0 OR p_treatment_mean < 0 THEN
    RAISE EXCEPTION 'conclusion means must be nonnegative';
  END IF;
  IF NOT COALESCE(p_assignment_integrity_verified,false)
     OR NOT COALESCE(p_exposure_integrity_verified,false)
     OR NOT COALESCE(p_outcome_window_closed,false) THEN
    RAISE EXCEPTION 'experiment not eligible for causal conclusion';
  END IF;
  IF COALESCE(array_length(p_evidence_refs,1),0)=0 THEN
    RAISE EXCEPTION 'causal conclusion requires evidence refs';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'causal conclusion registry requires evidence';
  END IF;

  SELECT * INTO r
  FROM public.experiment_causal_conclusions
  WHERE conclusion_key=trim(p_conclusion_key);
  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'conclusion_id',r.id,
      'conclusion_key',r.conclusion_key
    );
  END IF;

  observed_lift := p_treatment_mean - p_control_mean;
  observed_relative := CASE
    WHEN p_control_mean = 0 THEN NULL
    ELSE observed_lift / p_control_mean
  END;
  direction := CASE
    WHEN observed_lift > 0 THEN 'positive_observed_lift'
    WHEN observed_lift < 0 THEN 'negative_observed_lift'
    ELSE 'no_observed_lift'
  END;

  INSERT INTO public.experiment_causal_conclusions(
    conclusion_key,experiment_key,metric,
    control_count,treatment_count,control_mean,treatment_mean,
    absolute_lift,relative_lift,effect_direction,
    assignment_integrity_verified,exposure_integrity_verified,
    outcome_window_closed,evidence_refs,evidence
  )
  VALUES(
    trim(p_conclusion_key),trim(p_experiment_key),trim(p_metric),
    p_control_count,p_treatment_count,p_control_mean,p_treatment_mean,
    observed_lift,observed_relative,direction,
    true,true,true,p_evidence_refs,
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'conclusion_id',r.id,
    'conclusion_key',r.conclusion_key,
    'effect_direction',r.effect_direction,
    'statistical_significance_available',
      r.statistical_significance_available
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_experiment_causal_conclusion(
  text,text,text,integer,integer,numeric,numeric,
  boolean,boolean,boolean,text[],jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_experiment_causal_conclusion(
  text,text,text,integer,integer,numeric,numeric,
  boolean,boolean,boolean,text[],jsonb
) TO empire_experiment_conclusion_writer;

COMMIT;
