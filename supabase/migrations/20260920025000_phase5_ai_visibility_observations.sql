-- Phase 5 AEO/GEO/citation evidence observations.
-- Staged only: read-side evidence, no publishing/indexing/provider mutation.
BEGIN;

CREATE TABLE IF NOT EXISTS public.seo_ai_visibility_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL
    REFERENCES public.seo_sites(id) ON DELETE RESTRICT,
  query text NOT NULL,
  engine text NOT NULL,
  cited_url text NOT NULL,
  source_url text,
  citation_position integer CHECK (
    citation_position IS NULL OR citation_position > 0
  ),
  mention_text text,
  provenance text[] NOT NULL,
  observed_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (cardinality(provenance) > 0)
);

CREATE INDEX IF NOT EXISTS idx_seo_ai_visibility_site_observed
  ON public.seo_ai_visibility_observations(
    site_id,observed_at DESC,id
  );

CREATE INDEX IF NOT EXISTS idx_seo_ai_visibility_query_engine
  ON public.seo_ai_visibility_observations(
    site_id,query,engine,observed_at DESC
  );

ALTER TABLE public.seo_ai_visibility_observations
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.seo_ai_visibility_observations
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.seo_ai_visibility_observations
TO service_role;

GRANT SELECT ON public.seo_ai_visibility_observations
TO empire_search_reader;

DROP POLICY IF EXISTS seo_ai_visibility_reader_scope
ON public.seo_ai_visibility_observations;

CREATE POLICY seo_ai_visibility_reader_scope
ON public.seo_ai_visibility_observations
FOR SELECT
TO empire_search_reader
USING (
  EXISTS (
    SELECT 1
    FROM public.seo_sites s
    WHERE s.id = seo_ai_visibility_observations.site_id
      AND s.tenant_key = current_setting('app.tenant_key', true)
  )
);

COMMIT;
