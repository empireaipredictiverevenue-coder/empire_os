-- Isolated TAM stage-1 post-commit verification, catalog only.
-- This is not a login/credential, company-data, tenant or market-read test.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
DO $tam043_verify$
DECLARE
  role_name text;
  relation_name text;
  privilege_name text;
BEGIN
  IF current_database() <> 'empiredb' OR pg_is_in_recovery() THEN
    RAISE EXCEPTION 'TAM043_POST_WRONG_DATABASE_OR_REPLICA';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_authid
      WHERE rolname IN ('empire_tam_market_reader','empire_tam_market_login')
        AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
        AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
        AND NOT rolinherit AND rolpassword IS NULL) <> 2 THEN
    RAISE EXCEPTION 'TAM043_POST_ROLES_NOT_DORMANT_NOLOGIN_NULL_PASSWORD';
  END IF;
  IF NOT pg_catalog.pg_has_role(
    'empire_tam_market_login','empire_tam_market_reader','MEMBER'
  ) THEN
    RAISE EXCEPTION 'TAM043_POST_ISOLATED_MEMBERSHIP_MISSING';
  END IF;
  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_proc p
    WHERE p.oid=to_regprocedure('public.get_tam_market_observations(integer)')
      AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                      WHERE rolname='empiredb_migrator')
      AND p.prosecdef AND p.provolatile='s'
      AND p.prorettype='pg_catalog.jsonb'::pg_catalog.regtype
      AND p.proconfig @> ARRAY['search_path=""']::text[]
  ) THEN
    RAISE EXCEPTION 'TAM043_POST_FUNCTION_CONTRACT_INVALID';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
    'empire_tam_market_reader',
    'public.get_tam_market_observations(integer)', 'EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empire_intelligence_materializer',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empire_intelligence_materializer_login',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empiredb_app',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) OR EXISTS (
    SELECT FROM pg_catalog.pg_proc p,
      LATERAL pg_catalog.aclexplode(
        COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))
      ) a
    WHERE p.oid=to_regprocedure('public.get_tam_market_observations(integer)')
      AND a.grantee=0 AND a.privilege_type='EXECUTE'
  ) THEN
    RAISE EXCEPTION 'TAM043_POST_FUNCTION_EXECUTE_PRIVILEGES_UNSAFE';
  END IF;
  FOREACH role_name IN ARRAY ARRAY[
    'empire_tam_market_reader', 'empire_tam_market_login'
  ] LOOP
    IF pg_catalog.pg_has_role(
      role_name,'empire_intelligence_materializer','MEMBER'
    ) OR pg_catalog.pg_has_role(
      role_name,'empiredb_migrator','MEMBER'
    ) OR pg_catalog.pg_has_role(
      role_name,'empiredb_app','MEMBER'
    ) THEN
      RAISE EXCEPTION 'TAM043_POST_FORBIDDEN_MEMBERSHIP';
    END IF;
    FOREACH relation_name IN ARRAY ARRAY[
      'public.prospect_acquisitions',
      'public.prospect_entity_links',
      'public.business_entities'
    ] LOOP
      FOREACH privilege_name IN ARRAY ARRAY[
        'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'
      ] LOOP
        IF pg_catalog.has_table_privilege(
          role_name,relation_name,privilege_name
        ) THEN
          RAISE EXCEPTION 'TAM043_POST_DIRECT_SOURCE_PRIVILEGE';
        END IF;
      END LOOP;
      IF pg_catalog.has_any_column_privilege(
        role_name,relation_name,'SELECT,INSERT,UPDATE,REFERENCES'
      ) THEN
        RAISE EXCEPTION 'TAM043_POST_DIRECT_COLUMN_PRIVILEGE';
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
    RAISE EXCEPTION 'TAM043_POST_LEGACY_MATERIALIZER_GRANTS_CHANGED';
  END IF;
  RAISE NOTICE 'TAM043_STAGE1_CATALOG_VERIFIED_DORMANT_NOLOGIN';
END $tam043_verify$;
ROLLBACK;
