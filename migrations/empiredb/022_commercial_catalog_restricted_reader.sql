-- Restore the existing bounded catalog-reader capability, not table authority.
-- Apply explicitly; independent of held migration 018.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $catalog_guard$
DECLARE
  reader text;
  relation text;
  privilege text;
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
  ) OR (SELECT proowner FROM pg_catalog.pg_proc
        WHERE oid='public.get_commercial_product_catalog(text,integer)'::pg_catalog.regprocedure)
       <> 'empiredb_migrator'::pg_catalog.regrole THEN
    RAISE EXCEPTION 'catalog owner requires non-login migration authority review';
  END IF;
  FOREACH reader IN ARRAY ARRAY['empire_intelligence_materializer',
      'empire_intelligence_materializer_login','empiredb_app'] LOOP
    IF pg_catalog.pg_has_role(reader,'empiredb_migrator','MEMBER') THEN
      RAISE EXCEPTION 'runtime role must not inherit catalog owner';
    END IF;
  END LOOP;
  FOREACH reader IN ARRAY ARRAY['empire_intelligence_materializer',
      'empire_intelligence_materializer_login'] LOOP
    FOREACH relation IN ARRAY ARRAY['public.commercial_products',
        'public.commercial_product_versions'] LOOP
      FOREACH privilege IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE',
          'TRUNCATE','REFERENCES','TRIGGER'] LOOP
        IF pg_catalog.has_table_privilege(reader,relation,privilege)
           OR (privilege IN ('SELECT','INSERT','UPDATE','REFERENCES')
               AND pg_catalog.has_any_column_privilege(reader,relation,privilege)) THEN
          RAISE EXCEPTION 'unexpected materializer commercial table authority';
        END IF;
      END LOOP;
    END LOOP;
  END LOOP;
END;
$catalog_guard$;

ALTER FUNCTION public.get_commercial_product_catalog(text,integer)
  SECURITY DEFINER;
ALTER FUNCTION public.get_commercial_product_catalog(text,integer)
  SET search_path = '';
REVOKE ALL ON FUNCTION public.get_commercial_product_catalog(text,integer)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_commercial_product_catalog(text,integer)
  TO empire_intelligence_materializer;
COMMIT;
