-- Phase 14 governed Digital Twin realization registry.
-- Staged only: realization reviews observe outcomes and never create revenue or execution.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_digital_twin_realization_writer'
  ) THEN
    CREATE ROLE empire_digital_twin_realization_writer NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_digital_twin_realization_reader'
  ) THEN
    CREATE ROLE empire_digital_twin_realization_reader NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public
TO empire_digital_twin_realization_writer,
   empire_digital_twin_realization_reader;

REVOKE empire_digital_twin_realization_writer,
       empire_digital_twin_realization_reader
FROM service_role;

CREATE TABLE IF NOT EXISTS public.digital_twin_realizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  realization_key text NOT NULL UNIQUE,
  scenario_id uuid NOT NULL
    REFERENCES public.digital_twin_scenarios(id) ON DELETE RESTRICT,
  observed_served_units integer NOT NULL
    CHECK (observed_served_units >= 0),
  observed_revenue_cents bigint
    CHECK (observed_revenue_cents IS NULL OR observed_revenue_cents >= 0),
  revenue_recognized boolean NOT NULL DEFAULT false,
  observed_at timestamptz NOT NULL,
  evidence_refs text[] NOT NULL,
  served_unit_error integer NOT NULL,
  revenue_error_cents bigint,
  revenue_error_ratio numeric,
  revenue_comparison_available boolean NOT NULL DEFAULT false,
  blockers text[] NOT NULL DEFAULT ARRAY[]::text[],
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  simulation_only boolean NOT NULL DEFAULT true
    CHECK (simulation_only=true),
  creates_actual_revenue boolean NOT NULL DEFAULT false
    CHECK (creates_actual_revenue=false),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  capital_execution boolean NOT NULL DEFAULT false
    CHECK (NOT capital_execution),
  campaign_execution boolean NOT NULL DEFAULT false
    CHECK (NOT campaign_execution),
  pricing_execution boolean NOT NULL DEFAULT false
    CHECK (NOT pricing_execution),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (
    NOT revenue_recognized
    OR observed_revenue_cents IS NOT NULL
  ),
  CHECK (
    revenue_comparison_available = (
      revenue_recognized AND observed_revenue_cents IS NOT NULL
    )
  )
);

ALTER TABLE public.digital_twin_realizations ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS guard_digital_twin_realizations_append_only
ON public.digital_twin_realizations;
CREATE TRIGGER guard_digital_twin_realizations_append_only
BEFORE UPDATE OR DELETE ON public.digital_twin_realizations
FOR EACH ROW EXECUTE FUNCTION
  public.guard_digital_twin_registry_append_only();

REVOKE ALL ON public.digital_twin_realizations
FROM PUBLIC,anon,authenticated,service_role,
     empire_digital_twin_realization_writer,
     empire_digital_twin_realization_reader;

GRANT SELECT ON public.digital_twin_realizations
TO empire_digital_twin_realization_reader;

CREATE OR REPLACE FUNCTION public.record_digital_twin_realization(
  p_realization_key text,
  p_scenario_key text,
  p_observed_served_units integer,
  p_observed_revenue_cents bigint,
  p_revenue_recognized boolean,
  p_observed_at timestamptz,
  p_evidence_refs text[],
  p_evidence jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  s public.digital_twin_scenarios%ROWTYPE;
  r public.digital_twin_results%ROWTYPE;
  z public.digital_twin_realizations%ROWTYPE;
  stored_revenue bigint;
  revenue_available boolean;
  revenue_error bigint;
  revenue_ratio numeric;
  review_blockers text[];
BEGIN
  IF trim(COALESCE(p_realization_key,''))='' THEN
    RAISE EXCEPTION 'realization_key required';
  END IF;
  IF trim(COALESCE(p_scenario_key,''))='' THEN
    RAISE EXCEPTION 'scenario_key required';
  END IF;
  IF p_observed_served_units < 0 THEN
    RAISE EXCEPTION 'observed served units must be nonnegative';
  END IF;
  IF p_revenue_recognized AND p_observed_revenue_cents IS NULL THEN
    RAISE EXCEPTION 'recognized revenue amount required';
  END IF;
  IF p_observed_revenue_cents IS NOT NULL
     AND p_observed_revenue_cents < 0 THEN
    RAISE EXCEPTION 'observed revenue must be nonnegative';
  END IF;
  IF COALESCE(array_length(p_evidence_refs,1),0)=0 THEN
    RAISE EXCEPTION 'realization evidence refs required';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'digital twin realization registry requires evidence';
  END IF;

  SELECT * INTO z
  FROM public.digital_twin_realizations
  WHERE realization_key=trim(p_realization_key);
  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'realization_id',z.id,
      'realization_key',z.realization_key
    );
  END IF;

  SELECT * INTO s
  FROM public.digital_twin_scenarios
  WHERE scenario_key=trim(p_scenario_key);
  IF NOT FOUND THEN
    RAISE EXCEPTION 'registered scenario not found';
  END IF;

  SELECT * INTO r
  FROM public.digital_twin_results
  WHERE scenario_id=s.id
  ORDER BY generated_at DESC,id DESC
  LIMIT 1;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'registered scenario result not found';
  END IF;

  stored_revenue := CASE
    WHEN p_revenue_recognized THEN p_observed_revenue_cents
    ELSE NULL
  END;
  revenue_available := (
    p_revenue_recognized AND stored_revenue IS NOT NULL
  );
  revenue_error := CASE
    WHEN revenue_available
    THEN stored_revenue - r.projected_revenue_cents
    ELSE NULL
  END;
  revenue_ratio := CASE
    WHEN revenue_available AND r.projected_revenue_cents > 0
    THEN revenue_error::numeric / r.projected_revenue_cents::numeric
    ELSE NULL
  END;
  review_blockers := CASE
    WHEN revenue_available THEN ARRAY[]::text[]
    ELSE ARRAY['recognized_revenue_evidence_missing']::text[]
  END;

  INSERT INTO public.digital_twin_realizations(
    realization_key,scenario_id,observed_served_units,
    observed_revenue_cents,revenue_recognized,observed_at,evidence_refs,
    served_unit_error,revenue_error_cents,revenue_error_ratio,
    revenue_comparison_available,blockers,evidence
  )
  VALUES(
    trim(p_realization_key),s.id,p_observed_served_units,
    stored_revenue,p_revenue_recognized,p_observed_at,p_evidence_refs,
    p_observed_served_units-r.projected_served_units,
    revenue_error,revenue_ratio,revenue_available,review_blockers,
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO z;

  RETURN jsonb_build_object(
    'status','recorded',
    'realization_id',z.id,
    'realization_key',z.realization_key,
    'scenario_id',z.scenario_id,
    'revenue_comparison_available',z.revenue_comparison_available
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_digital_twin_realization(
  text,text,integer,bigint,boolean,timestamptz,text[],jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_digital_twin_realization(
  text,text,integer,bigint,boolean,timestamptz,text[],jsonb
) TO empire_digital_twin_realization_writer;

COMMIT;
