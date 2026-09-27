-- Phase 13 Revenue Exchange observation layer.
-- Staged only: no allocation, exclusivity enforcement or settlement execution.
BEGIN;

CREATE TABLE IF NOT EXISTS public.revenue_exchange_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  niche text NOT NULL,
  metro text NOT NULL,
  qualified_inventory_count integer NOT NULL
    CHECK (qualified_inventory_count >= 0),
  active_buyer_capacity integer NOT NULL
    CHECK (active_buyer_capacity >= 0),
  verified_price_per_lead_cents integer[] NOT NULL DEFAULT '{}',
  observed_at timestamptz NOT NULL,
  source text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (0 < ALL (verified_price_per_lead_cents))
);

CREATE INDEX IF NOT EXISTS idx_revenue_exchange_market_time
  ON public.revenue_exchange_observations(
    niche,metro,observed_at DESC
  );

ALTER TABLE public.revenue_exchange_observations
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.revenue_exchange_observations
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.revenue_exchange_observations
TO service_role;

COMMIT;
