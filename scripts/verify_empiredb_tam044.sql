-- HELD 044 post-release catalog-only verification. No market rows read.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
DO $verify$
DECLARE
  role_name text;
  relation_name text;
  privilege_name text;
BEGIN
  IF current_database()<>'empiredb' OR pg_is_in_recovery() THEN
    RAISE EXCEPTION 'TAM044_POST_WRONG_DATABASE_OR_REPLICA';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    WHERE p.oid=to_regprocedure(
      'public.get_tam_market_observations_scoped(text[],text[],integer)'
    ) AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
      WHERE rolname='empiredb_migrator')
      AND p.prosecdef AND p.provolatile='s'
      AND p.prorettype='pg_catalog.jsonb'::pg_catalog.regtype
      AND p.proconfig @> ARRAY['search_path=""']::text[]
  ) THEN
    RAISE EXCEPTION 'TAM044_POST_SCOPED_FUNCTION_SECURITY_UNVERIFIED';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
    'empire_tam_market_reader',
    'public.get_tam_market_observations_scoped(text[],text[],integer)',
    'EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empire_intelligence_materializer',
    'public.get_tam_market_observations_scoped(text[],text[],integer)',
    'EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empire_intelligence_materializer_login',
    'public.get_tam_market_observations_scoped(text[],text[],integer)',
    'EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empiredb_app',
    'public.get_tam_market_observations_scoped(text[],text[],integer)',
    'EXECUTE'
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p,
      LATERAL pg_catalog.aclexplode(
        COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))
      ) a
    WHERE p.oid=to_regprocedure(
      'public.get_tam_market_observations_scoped(text[],text[],integer)'
    ) AND a.grantee=0 AND a.privilege_type='EXECUTE'
  ) THEN
    RAISE EXCEPTION 'TAM044_POST_SCOPED_FUNCTION_EXECUTE_UNSAFE';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
    'empire_tam_market_reader',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) THEN
    RAISE EXCEPTION 'TAM044_POST_OLD_043_FUNCTION_INACCESSIBLE';
  END IF;
  FOREACH role_name IN ARRAY ARRAY[
    'empire_tam_market_reader','empire_tam_market_login'
  ] LOOP
    FOREACH relation_name IN ARRAY ARRAY[
      'public.prospect_acquisitions','public.prospect_entity_links',
      'public.business_entities'
    ] LOOP
      FOREACH privilege_name IN ARRAY ARRAY[
        'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'
      ] LOOP
        IF pg_catalog.has_table_privilege(
          role_name,relation_name,privilege_name
        ) THEN
          RAISE EXCEPTION 'TAM044_POST_NEW_ROLE_SOURCE_TABLE_PRIVILEGE';
        END IF;
      END LOOP;
      IF pg_catalog.has_any_column_privilege(
        role_name,relation_name,'SELECT,INSERT,UPDATE,REFERENCES'
      ) THEN
        RAISE EXCEPTION 'TAM044_POST_NEW_ROLE_SOURCE_COLUMN_PRIVILEGE';
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
    RAISE EXCEPTION 'TAM044_POST_LEGACY_MARKET_GPS_PRIVILEGES_CHANGED';
  END IF;
  RAISE NOTICE 'TAM044_SCOPED_FUNCTION_CATALOG_VERIFIED_RESEARCH_ONLY';
END $verify$;
ROLLBACK;
