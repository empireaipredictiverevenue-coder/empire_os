-- Phase 14 governed Digital Twin scenario/result registry.
-- Staged only: simulation records cannot execute campaigns, capital or pricing.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_digital_twin_registry_writer'
  ) THEN
    CREATE ROLE empire_digital_twin_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_digital_twin_registry_writer;
REVOKE empire_digital_twin_registry_writer FROM service_role;

ALTER TABLE public.digital_twin_scenarios
  ADD COLUMN IF NOT EXISTS scenario_key text,
  ADD COLUMN IF NOT EXISTS evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS execution_authority text NOT NULL DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS capital_execution boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS campaign_execution boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS pricing_execution boolean NOT NULL DEFAULT false;

ALTER TABLE public.digital_twin_scenarios
  DROP CONSTRAINT IF EXISTS digital_twin_scenarios_execution_authority_check,
  ADD CONSTRAINT digital_twin_scenarios_execution_authority_check
    CHECK (execution_authority='none'),
  DROP CONSTRAINT IF EXISTS digital_twin_scenarios_capital_execution_check,
  ADD CONSTRAINT digital_twin_scenarios_capital_execution_check
    CHECK (NOT capital_execution),
  DROP CONSTRAINT IF EXISTS digital_twin_scenarios_campaign_execution_check,
  ADD CONSTRAINT digital_twin_scenarios_campaign_execution_check
    CHECK (NOT campaign_execution),
  DROP CONSTRAINT IF EXISTS digital_twin_scenarios_pricing_execution_check,
  ADD CONSTRAINT digital_twin_scenarios_pricing_execution_check
    CHECK (NOT pricing_execution);

ALTER TABLE public.digital_twin_results
  ADD COLUMN IF NOT EXISTS simulated_revenue_delta_cents bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS execution_authority text NOT NULL DEFAULT 'none';

ALTER TABLE public.digital_twin_results
  DROP CONSTRAINT IF EXISTS digital_twin_results_execution_authority_check,
  ADD CONSTRAINT digital_twin_results_execution_authority_check
    CHECK (execution_authority='none');

CREATE UNIQUE INDEX IF NOT EXISTS uq_digital_twin_scenario_key
  ON public.digital_twin_scenarios(scenario_key)
  WHERE scenario_key IS NOT NULL;

CREATE OR REPLACE FUNCTION public.guard_digital_twin_registry_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'digital twin registry is append-only';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_digital_twin_scenarios_append_only
ON public.digital_twin_scenarios;
CREATE TRIGGER guard_digital_twin_scenarios_append_only
BEFORE UPDATE OR DELETE ON public.digital_twin_scenarios
FOR EACH ROW EXECUTE FUNCTION
  public.guard_digital_twin_registry_append_only();

DROP TRIGGER IF EXISTS guard_digital_twin_results_append_only
ON public.digital_twin_results;
CREATE TRIGGER guard_digital_twin_results_append_only
BEFORE UPDATE OR DELETE ON public.digital_twin_results
FOR EACH ROW EXECUTE FUNCTION
  public.guard_digital_twin_registry_append_only();

REVOKE ALL ON public.digital_twin_scenarios,public.digital_twin_results
FROM empire_digital_twin_registry_writer;

CREATE OR REPLACE FUNCTION public.record_digital_twin_scenario(
  p_scenario_key text,
  p_niche text,
  p_metro text,
  p_baseline_evidence_ref text,
  p_baseline_observed_at timestamptz,
  p_observed_demand_units integer,
  p_observed_capacity_units integer,
  p_observed_price_per_unit_cents integer,
  p_demand_multiplier numeric,
  p_capacity_multiplier numeric,
  p_price_multiplier numeric,
  p_projected_served_units integer,
  p_projected_revenue_cents bigint,
  p_simulated_revenue_delta_cents bigint,
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
BEGIN
  IF trim(COALESCE(p_scenario_key,''))='' THEN
    RAISE EXCEPTION 'scenario_key required';
  END IF;
  IF trim(COALESCE(p_niche,''))='' OR trim(COALESCE(p_metro,''))='' THEN
    RAISE EXCEPTION 'baseline market identity required';
  END IF;
  IF trim(COALESCE(p_baseline_evidence_ref,''))='' THEN
    RAISE EXCEPTION 'baseline provenance required';
  END IF;
  IF p_observed_demand_units < 0 OR p_observed_capacity_units < 0 THEN
    RAISE EXCEPTION 'baseline units must be nonnegative';
  END IF;
  IF p_observed_price_per_unit_cents <= 0 THEN
    RAISE EXCEPTION 'baseline observed price must be positive';
  END IF;
  IF p_demand_multiplier < 0
     OR p_capacity_multiplier < 0
     OR p_price_multiplier < 0 THEN
    RAISE EXCEPTION 'scenario multipliers must be nonnegative';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'digital twin registry requires evidence';
  END IF;

  SELECT * INTO s
  FROM public.digital_twin_scenarios
  WHERE scenario_key=trim(p_scenario_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'scenario_id',s.id,
      'scenario_key',s.scenario_key
    );
  END IF;

  INSERT INTO public.digital_twin_scenarios(
    scenario_key,niche,metro,baseline_evidence_ref,baseline_observed_at,
    observed_demand_units,observed_capacity_units,
    observed_price_per_unit_cents,demand_multiplier,capacity_multiplier,
    price_multiplier,evidence
  )
  VALUES(
    trim(p_scenario_key),trim(p_niche),trim(p_metro),
    trim(p_baseline_evidence_ref),p_baseline_observed_at,
    p_observed_demand_units,p_observed_capacity_units,
    p_observed_price_per_unit_cents,p_demand_multiplier,
    p_capacity_multiplier,p_price_multiplier,COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO s;

  INSERT INTO public.digital_twin_results(
    scenario_id,projected_demand_units,projected_capacity_units,
    projected_served_units,projected_price_per_unit_cents,
    projected_revenue_cents,simulated_revenue_delta_cents,evidence
  )
  VALUES(
    s.id,
    round(p_observed_demand_units * p_demand_multiplier)::integer,
    round(p_observed_capacity_units * p_capacity_multiplier)::integer,
    p_projected_served_units,
    round(p_observed_price_per_unit_cents * p_price_multiplier)::integer,
    p_projected_revenue_cents,
    p_simulated_revenue_delta_cents,
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'scenario_id',s.id,
    'result_id',r.id,
    'scenario_key',s.scenario_key
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_digital_twin_scenario(
  text,text,text,text,timestamptz,integer,integer,integer,
  numeric,numeric,numeric,integer,bigint,bigint,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_digital_twin_scenario(
  text,text,text,text,timestamptz,integer,integer,integer,
  numeric,numeric,numeric,integer,bigint,bigint,jsonb
) TO empire_digital_twin_registry_writer;

COMMIT;
