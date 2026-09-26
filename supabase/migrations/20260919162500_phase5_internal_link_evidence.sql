-- Phase 5 canonical internal-link evidence.
-- Staged only: do not apply without explicit production approval.
BEGIN;

CREATE TABLE IF NOT EXISTS public.seo_internal_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE CASCADE,
  source_page_id uuid NOT NULL REFERENCES public.seo_pages(id) ON DELETE CASCADE,
  target_page_id uuid REFERENCES public.seo_pages(id) ON DELETE SET NULL,
  source_url text NOT NULL,
  target_url text NOT NULL,
  anchor_text text,
  rel text,
  first_observed_at timestamptz NOT NULL DEFAULT now(),
  last_observed_at timestamptz NOT NULL DEFAULT now(),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seo_internal_links_source
  ON public.seo_internal_links(site_id, source_page_id);
CREATE INDEX IF NOT EXISTS idx_seo_internal_links_target
  ON public.seo_internal_links(site_id, target_page_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_seo_internal_links_observed_edge
  ON public.seo_internal_links(
    site_id,
    source_url,
    target_url,
    coalesce(anchor_text, ''),
    coalesce(rel, '')
  );

ALTER TABLE public.seo_internal_links ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS empire_search_reader_select
  ON public.seo_internal_links;
CREATE POLICY empire_search_reader_select
  ON public.seo_internal_links
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_sites AS site
      WHERE site.id = seo_internal_links.site_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

GRANT SELECT ON public.seo_internal_links TO empire_search_reader;

COMMIT;
