-- Empire Search Intelligence foundation.
-- Schema only: no synthetic rows, no production activation.
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.seo_sites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_key text NOT NULL,
  name text,
  base_url text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_key, base_url)
);

CREATE TABLE IF NOT EXISTS public.seo_pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE CASCADE,
  url text NOT NULL,
  slug text,
  page_type text,
  title text,
  meta_description text,
  canonical_url text,
  robots_state text,
  indexable boolean,
  content_quality_score numeric CHECK (
    content_quality_score IS NULL OR content_quality_score BETWEEN 0 AND 1
  ),
  opportunity_score numeric CHECK (
    opportunity_score IS NULL OR opportunity_score BETWEEN 0 AND 1
  ),
  target_query text,
  search_intent text,
  industry text,
  location text,
  service text,
  topic text,
  entity_references jsonb NOT NULL DEFAULT '[]'::jsonb,
  publish_state text,
  index_state text NOT NULL DEFAULT 'DISCOVERED',
  first_published_at timestamptz,
  last_modified_at timestamptz,
  last_crawled_at timestamptz,
  last_indexed_at timestamptz,
  refresh_required boolean NOT NULL DEFAULT false,
  revenue_attributed_cents bigint,
  leads_attributed integer,
  conversions_attributed integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (site_id, url),
  CHECK (index_state IN (
    'DISCOVERED','DRAFT','QUALITY_REVIEW','APPROVED','PUBLISHED',
    'INDEXABLE','SUBMITTED','DISCOVERED_BY_GOOGLE','CRAWLED','INDEXED',
    'DECLINED','NOINDEX','REFRESH_REQUIRED','ARCHIVED'
  ))
);

CREATE INDEX IF NOT EXISTS idx_seo_pages_site_state
  ON public.seo_pages(site_id, index_state);
CREATE INDEX IF NOT EXISTS idx_seo_pages_target_query
  ON public.seo_pages(site_id, target_query);
CREATE INDEX IF NOT EXISTS idx_seo_pages_refresh
  ON public.seo_pages(site_id, refresh_required)
  WHERE refresh_required = true;

CREATE TABLE IF NOT EXISTS public.seo_queries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE CASCADE,
  query text NOT NULL,
  topic text,
  intent text,
  industry text,
  geography text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (site_id, query)
);

CREATE TABLE IF NOT EXISTS public.seo_opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE CASCADE,
  query_id uuid REFERENCES public.seo_queries(id) ON DELETE SET NULL,
  query text NOT NULL,
  topic text,
  intent text,
  commercial_intent numeric,
  competitor_presence numeric,
  current_empire_coverage numeric,
  content_gap numeric,
  target_page_type text,
  relevance numeric,
  authority_fit numeric,
  trend_signal numeric,
  conversion_history numeric,
  revenue_history_cents bigint,
  estimated_business_value_cents bigint,
  intent_score numeric,
  conversion_probability numeric,
  freshness numeric,
  competition numeric,
  opportunity_score numeric,
  score_reason text,
  observed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (site_id, query),
  CHECK (commercial_intent IS NULL OR commercial_intent BETWEEN 0 AND 1),
  CHECK (relevance IS NULL OR relevance BETWEEN 0 AND 1),
  CHECK (authority_fit IS NULL OR authority_fit BETWEEN 0 AND 1),
  CHECK (conversion_probability IS NULL OR conversion_probability BETWEEN 0 AND 1),
  CHECK (freshness IS NULL OR freshness BETWEEN 0 AND 1),
  CHECK (competition IS NULL OR competition BETWEEN 0 AND 1),
  CHECK (opportunity_score IS NULL OR opportunity_score BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS idx_seo_opportunities_site_score
  ON public.seo_opportunities(site_id, opportunity_score DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS public.seo_content_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id uuid NOT NULL REFERENCES public.seo_pages(id) ON DELETE CASCADE,
  overall_score numeric,
  factor_scores jsonb NOT NULL,
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
  recommended_actions jsonb NOT NULL DEFAULT '[]'::jsonb,
  index_decision text NOT NULL,
  evaluated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (overall_score IS NULL OR overall_score BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS idx_seo_content_scores_page_time
  ON public.seo_content_scores(page_id, evaluated_at DESC);

CREATE TABLE IF NOT EXISTS public.seo_indexation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id uuid NOT NULL REFERENCES public.seo_pages(id) ON DELETE CASCADE,
  state text NOT NULL,
  source text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  observed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seo_indexation_page_time
  ON public.seo_indexation(page_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS public.seo_search_console (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE CASCADE,
  page_id uuid REFERENCES public.seo_pages(id) ON DELETE SET NULL,
  date date NOT NULL,
  query text,
  page text,
  impressions bigint,
  clicks bigint,
  ctr numeric,
  average_position numeric,
  country text,
  device text,
  search_appearance text,
  ingested_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seo_search_console_site_date
  ON public.seo_search_console(site_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_seo_search_console_query
  ON public.seo_search_console(site_id, query);

CREATE TABLE IF NOT EXISTS public.seo_revenue_attribution (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE CASCADE,
  page_id uuid REFERENCES public.seo_pages(id) ON DELETE SET NULL,
  query text,
  external_session_id text,
  prospect_id uuid REFERENCES public.prospects(id) ON DELETE RESTRICT,
  external_conversation_id text,
  opportunity_id uuid REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
  fulfilment_order_id uuid REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  commercial_event_id uuid REFERENCES public.commercial_events(id) ON DELETE RESTRICT,
  revenue_cents bigint CHECK (revenue_cents IS NULL OR revenue_cents >= 0),
  attribution_kind text NOT NULL,
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seo_revenue_page
  ON public.seo_revenue_attribution(page_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_seo_revenue_query
  ON public.seo_revenue_attribution(site_id, query, occurred_at DESC);

CREATE TABLE IF NOT EXISTS public.seo_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE CASCADE,
  page_id uuid REFERENCES public.seo_pages(id) ON DELETE CASCADE,
  alert_type text NOT NULL,
  severity text NOT NULL DEFAULT 'info',
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'open',
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_seo_alerts_open
  ON public.seo_alerts(site_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.seo_refresh_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id uuid NOT NULL REFERENCES public.seo_pages(id) ON DELETE CASCADE,
  reason text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  recommended_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'recommended',
  UNIQUE (page_id, reason, status)
);

ALTER TABLE public.seo_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_content_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_indexation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_search_console ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_revenue_attribution ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_refresh_queue ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON
  public.seo_sites,
  public.seo_pages,
  public.seo_queries,
  public.seo_opportunities,
  public.seo_content_scores,
  public.seo_indexation,
  public.seo_search_console,
  public.seo_revenue_attribution,
  public.seo_alerts,
  public.seo_refresh_queue
FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON
  public.seo_sites,
  public.seo_pages,
  public.seo_queries,
  public.seo_opportunities,
  public.seo_alerts,
  public.seo_refresh_queue
TO service_role;

GRANT SELECT, INSERT ON
  public.seo_content_scores,
  public.seo_indexation,
  public.seo_search_console,
  public.seo_revenue_attribution
TO service_role;

COMMENT ON TABLE public.seo_search_console IS
'Observed Google Search Console data only; no synthetic values.';
COMMENT ON TABLE public.seo_revenue_attribution IS
'Search-to-revenue linkage using real event identifiers and observed revenue only.';

COMMIT;
