-- Phase 9 Advertising Brain canonical observation spine.
-- Staged only: no campaign launch, budget mutation, pause or retarget execution.
BEGIN;

CREATE TABLE IF NOT EXISTS public.ad_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  platform text NOT NULL CHECK (
    platform IN ('google','meta','tiktok','linkedin','other')
  ),
  external_account_id text NOT NULL,
  account_name text,
  currency text,
  status text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(platform, external_account_id)
);

CREATE TABLE IF NOT EXISTS public.ad_campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id uuid NOT NULL
    REFERENCES public.ad_accounts(id) ON DELETE RESTRICT,
  external_campaign_id text NOT NULL,
  campaign_name text,
  objective text,
  status text,
  landing_page_url text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(account_id, external_campaign_id)
);
CREATE TABLE IF NOT EXISTS public.ad_creatives (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid NOT NULL
    REFERENCES public.ad_campaigns(id) ON DELETE RESTRICT,
  external_creative_id text NOT NULL,
  creative_name text,
  creative_type text,
  asset_reference text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(campaign_id, external_creative_id)
);

CREATE TABLE IF NOT EXISTS public.ad_performance_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid NOT NULL
    REFERENCES public.ad_campaigns(id) ON DELETE RESTRICT,
  creative_id uuid
    REFERENCES public.ad_creatives(id) ON DELETE RESTRICT,
  observed_at timestamptz NOT NULL,
  interval_start timestamptz,
  interval_end timestamptz,
  spend_cents bigint NOT NULL CHECK (spend_cents >= 0),
  attributed_revenue_cents bigint CHECK (
    attributed_revenue_cents IS NULL OR attributed_revenue_cents >= 0
  ),
  attributed_gross_profit_cents bigint CHECK (
    attributed_gross_profit_cents IS NULL OR attributed_gross_profit_cents >= 0
  ),
  impressions bigint CHECK (impressions IS NULL OR impressions >= 0),
  clicks bigint CHECK (clicks IS NULL OR clicks >= 0),
  conversions bigint CHECK (conversions IS NULL OR conversions >= 0),
  source text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS idx_ad_performance_campaign_time
  ON public.ad_performance_observations(campaign_id, observed_at DESC);

ALTER TABLE public.ad_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ad_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ad_creatives ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ad_performance_observations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.ad_accounts,public.ad_campaigns,
  public.ad_creatives,public.ad_performance_observations
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.ad_accounts,public.ad_campaigns,
  public.ad_creatives,public.ad_performance_observations
TO service_role;

CREATE OR REPLACE FUNCTION public.guard_ad_performance_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'ad performance observations are append-only';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER guard_ad_performance_append_only
BEFORE UPDATE OR DELETE ON public.ad_performance_observations
FOR EACH ROW EXECUTE FUNCTION public.guard_ad_performance_append_only();

COMMIT;
