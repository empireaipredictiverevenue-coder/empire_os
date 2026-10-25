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
DROP TABLE public.crm_search_site_bindings;
COMMIT;
