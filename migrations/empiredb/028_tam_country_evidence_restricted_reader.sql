-- Bounded TAM market-observation reader from canonical acquisition evidence.
-- HELD until explicit database activation.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $tam_guard$
DECLARE
  relation text;
  privilege text;
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'EmpireDB required';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator'
      AND NOT rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'TAM reader requires guarded non-login migrator';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_intelligence_materializer'
      AND NOT rolcanlogin AND NOT rolsuper
  ) OR NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_intelligence_materializer_login'
      AND rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'TAM materializer roles missing or unsafe';
  END IF;

  IF NOT pg_catalog.pg_has_role(
      'empire_intelligence_materializer_login',
      'empire_intelligence_materializer',
      'MEMBER'
  ) THEN
    RAISE EXCEPTION 'materializer login lacks capability membership';
  END IF;

  IF pg_catalog.pg_has_role(
      'empire_intelligence_materializer',
      'empiredb_migrator',
      'MEMBER'
  ) OR pg_catalog.pg_has_role(
      'empire_intelligence_materializer_login',
      'empiredb_migrator',
      'MEMBER'
  ) OR pg_catalog.pg_has_role(
      'empiredb_app',
      'empiredb_migrator',
      'MEMBER'
  ) OR pg_catalog.pg_has_role(
      'empiredb_app',
      'empire_intelligence_materializer',
      'MEMBER'
  ) THEN
    RAISE EXCEPTION 'TAM reader authority boundary violated';
  END IF;

  FOREACH relation IN ARRAY ARRAY[
    'public.prospect_acquisitions',
    'public.prospect_entity_links',
    'public.business_entities'
  ] LOOP
    IF pg_catalog.to_regclass(relation) IS NULL THEN
      RAISE EXCEPTION 'TAM reader relation missing: %', relation;
    END IF;
    FOREACH privilege IN ARRAY ARRAY[
      'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'
    ] LOOP
      IF pg_catalog.has_table_privilege(
          'empire_intelligence_materializer',
          relation,
          privilege
      ) THEN
        RAISE EXCEPTION
          'unexpected TAM materializer table authority: % %',
          relation, privilege;
      END IF;
    END LOOP;
  END LOOP;
END;
$tam_guard$;

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
  FROM PUBLIC, empire_intelligence_materializer_login, empiredb_app;
GRANT EXECUTE ON FUNCTION public.get_tam_market_observations(integer)
  TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.get_tam_market_observations(integer)
IS 'Bounded read-only TAM market observations from canonical acquisition locale evidence. No execution authority.';

COMMIT;
