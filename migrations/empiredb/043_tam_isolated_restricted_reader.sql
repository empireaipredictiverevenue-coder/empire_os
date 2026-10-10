-- HELD: replacement for incompatible 028, uses isolated TAM-only roles.
-- Requires separately approved tam_isolated_roles_bootstrap.sql first.
-- Do NOT apply or modify the existing intelligence materializer grants.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout='15s';
DO $tam_isolated_guard$
DECLARE
  role_name text;
  relation_name text;
  privilege_name text;
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'isolated TAM reader requires empiredb';
  END IF;
  IF to_regprocedure('public.get_tam_market_observations(integer)') IS NOT NULL THEN
    RAISE EXCEPTION 'existing TAM RPC requires separate catalog review';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_tam_market_reader'
    AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
  ) OR NOT EXISTS (SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_tam_market_login'
    AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
  ) OR NOT pg_catalog.pg_has_role(
    'empire_tam_market_login','empire_tam_market_reader','MEMBER'
  ) THEN
    RAISE EXCEPTION 'dedicated isolated TAM bootstrap required';
  END IF;
  IF pg_catalog.pg_has_role(
    'empire_tam_market_login','empire_intelligence_materializer','MEMBER'
  ) OR pg_catalog.pg_has_role(
    'empiredb_app','empire_tam_market_reader','MEMBER'
  ) OR pg_catalog.pg_has_role(
    'empire_intelligence_materializer_login','empire_tam_market_reader','MEMBER'
  ) THEN RAISE EXCEPTION 'TAM privilege separation violated'; END IF;
  FOREACH role_name IN ARRAY ARRAY[
    'empire_tam_market_reader','empire_tam_market_login'
  ] LOOP
    FOREACH relation_name IN ARRAY ARRAY[
      'public.prospect_acquisitions',
      'public.prospect_entity_links',
      'public.business_entities'
    ] LOOP
      IF to_regclass(relation_name) IS NULL THEN
        RAISE EXCEPTION 'TAM source table not present: %',relation_name;
      END IF;
      FOREACH privilege_name IN ARRAY ARRAY[
        'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'
      ] LOOP
        IF pg_catalog.has_table_privilege(
          role_name,relation_name,privilege_name
        ) THEN RAISE EXCEPTION 'isolated TAM role table authority violation'; END IF;
      END LOOP;
      IF pg_catalog.has_any_column_privilege(
        role_name,relation_name,'SELECT,INSERT,UPDATE,REFERENCES'
      ) THEN RAISE EXCEPTION 'isolated TAM role column authority violation'; END IF;
    END LOOP;
  END LOOP;
END $tam_isolated_guard$;

CREATE OR REPLACE FUNCTION public.get_tam_market_observations(
  p_limit integer DEFAULT 1000
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $tam$
DECLARE
  payload jsonb;
BEGIN
  IF p_limit IS NULL OR p_limit < 1 OR p_limit > 5000 THEN
    RAISE EXCEPTION 'TAM observation limit must be 1-5000';
  END IF;

  SELECT COALESCE(
    pg_catalog.jsonb_agg(row_data ORDER BY observed_at DESC, entity_id),
    '[]'::jsonb
  )
  INTO payload
  FROM (
    SELECT DISTINCT ON (
      l.entity_id,
      pg_catalog.lower(pg_catalog.btrim(e.canonical_niche)),
      pg_catalog.upper(pg_catalog.btrim(
        a.evidence #>> '{locale,country_code}'
      ))
    )
      a.created_at AS observed_at,
      l.entity_id,
      pg_catalog.jsonb_build_object(
        'entity_id',l.entity_id,
        'company_name',pg_catalog.btrim(e.canonical_name),
        'industry',pg_catalog.btrim(e.canonical_niche),
        'country_code',pg_catalog.upper(pg_catalog.btrim(
          a.evidence #>> '{locale,country_code}'
        )),
        'source_ref',COALESCE(
          NULLIF(pg_catalog.btrim(a.source_url),''),
          NULLIF(pg_catalog.btrim(a.evidence->>'source_url'),'')
        ),
        'observed_at',a.created_at,
        'acquisition_source',a.source,
        'locale_resolution',a.evidence #>> '{locale,resolved_from}',
        'execution_authority','none'
      ) AS row_data
    FROM public.prospect_acquisitions a
    JOIN public.prospect_entity_links l
      ON l.prospect_id=a.prospect_id
     AND l.active=true
    JOIN public.business_entities e
      ON e.id=l.entity_id
    WHERE pg_catalog.btrim(COALESCE(e.canonical_name,'')) <> ''
      AND pg_catalog.btrim(COALESCE(e.canonical_niche,'')) <> ''
      AND pg_catalog.upper(pg_catalog.btrim(
        COALESCE(a.evidence #>> '{locale,country_code}','')
      )) ~ '^[A-Z]{2}$'
      AND COALESCE(
        NULLIF(pg_catalog.btrim(a.source_url),''),
        NULLIF(pg_catalog.btrim(a.evidence->>'source_url'),'')
      ) IS NOT NULL
    ORDER BY
      l.entity_id,
      pg_catalog.lower(pg_catalog.btrim(e.canonical_niche)),
      pg_catalog.upper(pg_catalog.btrim(
        a.evidence #>> '{locale,country_code}'
      )),
      a.created_at DESC,
      a.id DESC
    LIMIT p_limit
  ) q;

  RETURN payload;
END;
$tam$;

REVOKE ALL ON FUNCTION public.get_tam_market_observations(integer)
  FROM PUBLIC, empire_intelligence_materializer,
  empire_intelligence_materializer_login, empiredb_app,
  empire_tam_market_login;
GRANT EXECUTE ON FUNCTION public.get_tam_market_observations(integer)
  TO empire_tam_market_reader;
COMMENT ON FUNCTION public.get_tam_market_observations(integer)
IS 'Bounded research-only TAM market observations. Isolated TAM role only.';
DO $verify_tam_function$
BEGIN
  IF NOT pg_catalog.has_function_privilege(
    'empire_tam_market_reader',
    'public.get_tam_market_observations(integer)','EXECUTE'
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
    SELECT 1 FROM pg_catalog.pg_proc p,
      LATERAL pg_catalog.aclexplode(
        COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))
      ) a
    WHERE p.oid=to_regprocedure(
      'public.get_tam_market_observations(integer)'
    ) AND a.grantee=0 AND a.privilege_type='EXECUTE'
  ) THEN
    RAISE EXCEPTION 'isolated TAM function privilege verification failed';
  END IF;
END $verify_tam_function$;
COMMIT;
