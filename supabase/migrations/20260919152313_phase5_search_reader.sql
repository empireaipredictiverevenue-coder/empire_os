-- Phase 5 Search Intelligence least-privilege read transport.
-- Staged only: no credential is provisioned by this migration.
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'empire_search_reader'
  ) THEN
    CREATE ROLE empire_search_reader
      NOLOGIN
      NOINHERIT
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOREPLICATION
      NOBYPASSRLS;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'empire_search_reader_login'
  ) THEN
    CREATE ROLE empire_search_reader_login
      LOGIN
      NOINHERIT
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOREPLICATION
      NOBYPASSRLS
      CONNECTION LIMIT 5
      PASSWORD NULL;
  END IF;
END
$$;

GRANT empire_search_reader TO empire_search_reader_login;

ALTER ROLE empire_search_reader_login
  SET statement_timeout = '15s';
ALTER ROLE empire_search_reader_login
  SET idle_in_transaction_session_timeout = '30s';

GRANT USAGE ON SCHEMA public TO empire_search_reader;

GRANT SELECT ON
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
TO empire_search_reader;

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_sites;
CREATE POLICY empire_search_reader_select
  ON public.seo_sites
  FOR SELECT
  TO empire_search_reader
  USING (
    tenant_key = current_setting('app.tenant_key', true)
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_pages;
CREATE POLICY empire_search_reader_select
  ON public.seo_pages
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_sites AS site
      WHERE site.id = seo_pages.site_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_queries;
CREATE POLICY empire_search_reader_select
  ON public.seo_queries
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_sites AS site
      WHERE site.id = seo_queries.site_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_opportunities;
CREATE POLICY empire_search_reader_select
  ON public.seo_opportunities
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_sites AS site
      WHERE site.id = seo_opportunities.site_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_content_scores;
CREATE POLICY empire_search_reader_select
  ON public.seo_content_scores
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_pages AS page
      JOIN public.seo_sites AS site ON site.id = page.site_id
      WHERE page.id = seo_content_scores.page_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_indexation;
CREATE POLICY empire_search_reader_select
  ON public.seo_indexation
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_pages AS page
      JOIN public.seo_sites AS site ON site.id = page.site_id
      WHERE page.id = seo_indexation.page_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_search_console;
CREATE POLICY empire_search_reader_select
  ON public.seo_search_console
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_sites AS site
      WHERE site.id = seo_search_console.site_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_revenue_attribution;
CREATE POLICY empire_search_reader_select
  ON public.seo_revenue_attribution
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_sites AS site
      WHERE site.id = seo_revenue_attribution.site_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_alerts;
CREATE POLICY empire_search_reader_select
  ON public.seo_alerts
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_sites AS site
      WHERE site.id = seo_alerts.site_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

DROP POLICY IF EXISTS empire_search_reader_select ON public.seo_refresh_queue;
CREATE POLICY empire_search_reader_select
  ON public.seo_refresh_queue
  FOR SELECT
  TO empire_search_reader
  USING (
    EXISTS (
      SELECT 1
      FROM public.seo_pages AS page
      JOIN public.seo_sites AS site ON site.id = page.site_id
      WHERE page.id = seo_refresh_queue.page_id
        AND site.tenant_key = current_setting('app.tenant_key', true)
    )
  );

COMMIT;
