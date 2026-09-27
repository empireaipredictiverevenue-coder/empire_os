-- Phase 14 Digital Twin scenario/result records.
-- Staged only: simulations cannot be recorded as actual revenue.
BEGIN;

CREATE TABLE IF NOT EXISTS public.digital_twin_scenarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  niche text NOT NULL,
  metro text NOT NULL,
  baseline_evidence_ref text NOT NULL,
  baseline_observed_at timestamptz NOT NULL,
  observed_demand_units integer NOT NULL CHECK (observed_demand_units >= 0),
  observed_capacity_units integer NOT NULL CHECK (observed_capacity_units >= 0),
  observed_price_per_unit_cents integer NOT NULL CHECK (
    observed_price_per_unit_cents > 0
  ),
  demand_multiplier numeric NOT NULL CHECK (demand_multiplier >= 0),
  capacity_multiplier numeric NOT NULL CHECK (capacity_multiplier >= 0),
  price_multiplier numeric NOT NULL CHECK (price_multiplier >= 0),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.digital_twin_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scenario_id uuid NOT NULL
    REFERENCES public.digital_twin_scenarios(id) ON DELETE RESTRICT,
  projected_demand_units integer NOT NULL CHECK (projected_demand_units >= 0),
  projected_capacity_units integer NOT NULL CHECK (projected_capacity_units >= 0),
  projected_served_units integer NOT NULL CHECK (projected_served_units >= 0),
  projected_price_per_unit_cents integer NOT NULL CHECK (
    projected_price_per_unit_cents >= 0
  ),
  projected_revenue_cents bigint NOT NULL CHECK (projected_revenue_cents >= 0),
  simulation_only boolean NOT NULL DEFAULT true CHECK (simulation_only=true),
  actual_revenue boolean NOT NULL DEFAULT false CHECK (actual_revenue=false),
  generated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.digital_twin_scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.digital_twin_results ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.digital_twin_scenarios,public.digital_twin_results
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.digital_twin_scenarios,public.digital_twin_results
TO service_role;

COMMIT;
