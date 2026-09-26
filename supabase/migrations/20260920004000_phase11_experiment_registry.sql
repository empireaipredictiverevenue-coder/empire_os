-- Phase 11 governed experiment registry.
-- Staged only: no traffic mutation, rollout, pricing, payment or allocation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_experiment_registry_writer'
  ) THEN
    CREATE ROLE empire_experiment_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_experiment_registry_writer;
REVOKE empire_experiment_registry_writer FROM service_role;

CREATE TABLE IF NOT EXISTS public.experiment_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_key text NOT NULL UNIQUE,
  hypothesis text NOT NULL,
  metric text NOT NULL,
  control_variant text NOT NULL,
  treatment_variants jsonb NOT NULL DEFAULT '[]'::jsonb,
  assignment_integrity_verified boolean NOT NULL DEFAULT false,
  exposure_integrity_verified boolean NOT NULL DEFAULT false,
  outcome_window_closed boolean NOT NULL DEFAULT false,
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

ALTER TABLE public.experiment_registry ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.experiment_registry
FROM PUBLIC,anon,authenticated,service_role,empire_experiment_registry_writer;

GRANT SELECT ON public.experiment_registry TO service_role;

CREATE OR REPLACE FUNCTION public.guard_experiment_registry_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'experiment registry is append-only';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_experiment_registry_append_only
ON public.experiment_registry;

CREATE TRIGGER guard_experiment_registry_append_only
BEFORE UPDATE OR DELETE ON public.experiment_registry
FOR EACH ROW EXECUTE FUNCTION
  public.guard_experiment_registry_append_only();

CREATE OR REPLACE FUNCTION public.record_experiment_registry(
  p_experiment_key text,
  p_hypothesis text,
  p_metric text,
  p_control_variant text,
  p_treatment_variants jsonb DEFAULT '[]'::jsonb,
  p_assignment_integrity_verified boolean DEFAULT false,
  p_exposure_integrity_verified boolean DEFAULT false,
  p_outcome_window_closed boolean DEFAULT false,
  p_evidence jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.experiment_registry%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_experiment_key,''))='' THEN
    RAISE EXCEPTION 'experiment_key required';
  END IF;
  IF trim(COALESCE(p_hypothesis,''))='' THEN
    RAISE EXCEPTION 'hypothesis required';
  END IF;
  IF trim(COALESCE(p_metric,''))='' THEN
    RAISE EXCEPTION 'metric required';
  END IF;
  IF trim(COALESCE(p_control_variant,''))='' THEN
    RAISE EXCEPTION 'control_variant required';
  END IF;
  IF jsonb_typeof(COALESCE(p_treatment_variants,'[]'::jsonb)) <> 'array'
     OR jsonb_array_length(COALESCE(p_treatment_variants,'[]'::jsonb)) < 1 THEN
    RAISE EXCEPTION 'at least one treatment variant required';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'experiment registry requires evidence';
  END IF;

  SELECT * INTO r
  FROM public.experiment_registry
  WHERE experiment_key=trim(p_experiment_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'registry_id',r.id,
      'experiment_key',r.experiment_key
    );
  END IF;

  INSERT INTO public.experiment_registry(
    experiment_key,hypothesis,metric,control_variant,treatment_variants,
    assignment_integrity_verified,exposure_integrity_verified,
    outcome_window_closed,evidence
  )
  VALUES(
    trim(p_experiment_key),trim(p_hypothesis),trim(p_metric),
    trim(p_control_variant),COALESCE(p_treatment_variants,'[]'::jsonb),
    COALESCE(p_assignment_integrity_verified,false),
    COALESCE(p_exposure_integrity_verified,false),
    COALESCE(p_outcome_window_closed,false),
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'registry_id',r.id,
    'experiment_key',r.experiment_key
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_experiment_registry(
  text,text,text,text,jsonb,boolean,boolean,boolean,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_experiment_registry(
  text,text,text,text,jsonb,boolean,boolean,boolean,jsonb
) TO empire_experiment_registry_writer;

COMMIT;
