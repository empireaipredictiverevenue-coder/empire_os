-- HELD TAM migration 044: read-only production catalog preflight.
-- Does not inspect market rows or modify roles/functions/data.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
DO $preflight$
DECLARE
  role_name text;
  relation_name text;
BEGIN
  IF current_database()<>'empiredb' OR pg_is_in_recovery() THEN
    RAISE EXCEPTION 'TAM044_PREFLIGHT_WRONG_DATABASE_OR_REPLICA';
  END IF;
  IF to_regprocedure(
    'public.get_tam_market_observations_scoped(text[],text[],integer)'
  ) IS NOT NULL THEN
    RAISE EXCEPTION 'TAM044_PREFLIGHT_SCOPED_FUNCTION_COLLISION';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    WHERE p.oid=to_regprocedure(
      'public.get_tam_market_observations(integer)'
    ) AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
      WHERE rolname='empiredb_migrator')
      AND p.prosecdef AND p.provolatile='s'
      AND p.prorettype='pg_catalog.jsonb'::pg_catalog.regtype
      AND p.proconfig @> ARRAY['search_path=""']::text[]
  ) THEN
    RAISE EXCEPTION 'TAM044_PREFLIGHT_EXISTING_043_FUNCTION_UNVERIFIED';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
    'empire_tam_market_reader',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empire_intelligence_materializer',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) THEN
    RAISE EXCEPTION 'TAM044_PREFLIGHT_ROLE_FUNCTION_PRIVILEGES_UNVERIFIED';
  END IF;
  FOREACH role_name IN ARRAY ARRAY[
    'empire_tam_market_reader','empire_tam_market_login'
  ] LOOP
    FOREACH relation_name IN ARRAY ARRAY[
      'public.prospect_acquisitions','public.prospect_entity_links',
      'public.business_entities'
    ] LOOP
      IF pg_catalog.to_regclass(relation_name) IS NULL THEN
        RAISE EXCEPTION 'TAM044_PREFLIGHT_SOURCE_TABLE_MISSING';
      END IF;
      IF pg_catalog.has_table_privilege(role_name,relation_name,
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
      ) OR pg_catalog.has_any_column_privilege(role_name,relation_name,
        'SELECT,INSERT,UPDATE,REFERENCES'
      ) THEN
        RAISE EXCEPTION 'TAM044_PREFLIGHT_UNEXPECTED_SOURCE_TABLE_PRIVILEGE';
      END IF;
    END LOOP;
  END LOOP;
  IF NOT pg_catalog.has_table_privilege(
    'empire_intelligence_materializer',
    'public.prospect_entity_links','SELECT'
  ) OR NOT pg_catalog.has_table_privilege(
    'empire_intelligence_materializer',
    'public.business_entities','SELECT'
  ) THEN
    RAISE EXCEPTION 'TAM044_PREFLIGHT_LEGACY_MARKET_GPS_GRANTS_CHANGED';
  END IF;
  RAISE NOTICE 'TAM044_SCOPED_READER_READ_ONLY_PREFLIGHT_PASS';
END $preflight$;
ROLLBACK;
