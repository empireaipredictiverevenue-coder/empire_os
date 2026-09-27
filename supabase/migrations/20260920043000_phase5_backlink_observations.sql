-- Phase 5 observed backlink/authority graph evidence.
-- Staged only: no link-building, outreach or publishing mutation.
BEGIN;

CREATE TABLE IF NOT EXISTS public.seo_backlink_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL
    REFERENCES public.seo_sites(id) ON DELETE RESTRICT,
  source_url text NOT NULL,
  target_url text NOT NULL,
  anchor_text text,
  rel text,
  source text NOT NULL,
  provenance text[] NOT NULL,
  observed_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (cardinality(provenance) > 0)
);

CREATE INDEX IF NOT EXISTS idx_seo_backlinks_site_observed
  ON public.seo_backlink_observations(
    site_id, observed_at DESC, id
  );

ALTER TABLE public.seo_backlink_observations
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.seo_backlink_observations
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.seo_backlink_observations
TO service_role;

GRANT SELECT ON public.seo_backlink_observations
TO empire_search_reader;

DROP POLICY IF EXISTS seo_backlinks_reader_scope
ON public.seo_backlink_observations;

CREATE POLICY seo_backlinks_reader_scope
ON public.seo_backlink_observations
FOR SELECT
TO empire_search_reader
USING (
  EXISTS (
    SELECT 1
    FROM public.seo_sites s
    WHERE s.id = seo_backlink_observations.site_id
      AND s.tenant_key = current_setting(
        'app.tenant_key',
        true
      )
  )
);

COMMIT;
