-- Phase 15 Capital Allocator recommendation records.
-- Staged only: no funds movement or budget mutation.
BEGIN;

CREATE TABLE IF NOT EXISTS public.capital_allocation_recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_key text NOT NULL,
  expected_return_cents bigint NOT NULL CHECK (expected_return_cents >= 0),
  required_capital_cents bigint NOT NULL CHECK (required_capital_cents > 0),
  downside_loss_cents bigint NOT NULL CHECK (downside_loss_cents >= 0),
  confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  time_to_revenue_days integer NOT NULL CHECK (time_to_revenue_days >= 0),
  expected_return_multiple numeric NOT NULL,
  downside_ratio numeric NOT NULL,
  time_factor numeric NOT NULL,
  risk_adjusted_score numeric NOT NULL,
  evidence_refs text[] NOT NULL,
  recommendation_only boolean NOT NULL DEFAULT true
    CHECK (recommendation_only=true),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.capital_allocation_recommendations
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.capital_allocation_recommendations
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.capital_allocation_recommendations
TO service_role;

COMMIT;
