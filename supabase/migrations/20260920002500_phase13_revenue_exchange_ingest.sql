-- Phase 13 governed Revenue Exchange observation ingestion.
-- Staged only: no allocation, pricing, exclusivity or settlement execution.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_revenue_exchange_ingest'
  ) THEN
    CREATE ROLE empire_revenue_exchange_ingest NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_revenue_exchange_ingest;
REVOKE empire_revenue_exchange_ingest FROM service_role;

ALTER TABLE public.revenue_exchange_observations
  ADD COLUMN IF NOT EXISTS observation_key text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_revenue_exchange_observation_key
  ON public.revenue_exchange_observations(observation_key)
  WHERE observation_key IS NOT NULL;

REVOKE ALL ON public.revenue_exchange_observations
FROM empire_revenue_exchange_ingest;

CREATE OR REPLACE FUNCTION public.record_revenue_exchange_observation(
  p_observation_key text,
  p_niche text,
  p_metro text,
  p_qualified_inventory_count integer,
  p_active_buyer_capacity integer,
  p_verified_price_per_lead_cents integer[],
  p_observed_at timestamptz,
  p_source text,
  p_evidence jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  o public.revenue_exchange_observations%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_observation_key,''))='' THEN
    RAISE EXCEPTION 'observation_key required';
  END IF;
  IF trim(COALESCE(p_niche,''))='' OR trim(COALESCE(p_metro,''))='' THEN
    RAISE EXCEPTION 'niche and metro required';
  END IF;
  IF p_qualified_inventory_count IS NULL
     OR p_qualified_inventory_count < 0 THEN
    RAISE EXCEPTION 'qualified inventory must be nonnegative';
  END IF;
  IF p_active_buyer_capacity IS NULL OR p_active_buyer_capacity < 0 THEN
    RAISE EXCEPTION 'buyer capacity must be nonnegative';
  END IF;
  IF p_observed_at IS NULL THEN
    RAISE EXCEPTION 'observed_at required';
  END IF;
  IF trim(COALESCE(p_source,''))='' THEN
    RAISE EXCEPTION 'source required';
  END IF;
  IF EXISTS (
    SELECT 1 FROM unnest(
      COALESCE(p_verified_price_per_lead_cents,'{}'::integer[])
    ) AS price
    WHERE price <= 0
  ) THEN
    RAISE EXCEPTION 'verified prices must be positive';
  END IF;

  SELECT * INTO o
  FROM public.revenue_exchange_observations
  WHERE observation_key=trim(p_observation_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'observation_id',o.id,
      'observation_key',o.observation_key
    );
  END IF;

  INSERT INTO public.revenue_exchange_observations(
    observation_key,
    niche,
    metro,
    qualified_inventory_count,
    active_buyer_capacity,
    verified_price_per_lead_cents,
    observed_at,
    source,
    evidence
  )
  VALUES(
    trim(p_observation_key),
    trim(p_niche),
    trim(p_metro),
    p_qualified_inventory_count,
    p_active_buyer_capacity,
    COALESCE(p_verified_price_per_lead_cents,'{}'::integer[]),
    p_observed_at,
    trim(p_source),
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO o;

  RETURN jsonb_build_object(
    'status','recorded',
    'observation_id',o.id,
    'observation_key',o.observation_key
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_revenue_exchange_observation(
  text,text,text,integer,integer,integer[],timestamptz,text,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_revenue_exchange_observation(
  text,text,text,integer,integer,integer[],timestamptz,text,jsonb
) TO empire_revenue_exchange_ingest;

COMMIT;
