-- CANDIDATE ONLY. Separate production rollback approval required.
-- Refuse to discard any provisioned binding, including inactive history.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';
SET LOCAL ROLE empiredb_migrator;
DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb', 'crm_search_fixture') THEN
    RAISE EXCEPTION 'unexpected CRM search rollback database';
  END IF;
  IF EXISTS (SELECT 1 FROM public.crm_search_site_bindings) THEN
    RAISE EXCEPTION 'preserve provisioned bindings; reviewed recovery required';
  END IF;
END;
$guard$;
DROP FUNCTION public.empire_crm_search_evidence(uuid,uuid,text,text,integer);
RESET ROLE;
DROP POLICY crm_search_bound_sites ON public.seo_sites;
DROP POLICY crm_search_bound_backlinks ON public.seo_backlink_observations;
DROP POLICY crm_search_bound_citations ON public.seo_ai_visibility_observations;
REVOKE SELECT ON public.seo_sites,public.seo_backlink_observations,
  public.seo_ai_visibility_observations FROM empiredb_migrator;
SET LOCAL ROLE empiredb_migrator;
DROP TABLE public.crm_search_site_bindings;
COMMIT;
