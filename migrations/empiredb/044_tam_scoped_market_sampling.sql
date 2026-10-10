-- HELD for separate founder DBA approval. Does not replace live 043.
-- Scoped, bounded market RESEARCH sampling on the canonical EmpireDB only.
-- Source and target role privileges stay unchanged; no legacy market reads.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout = '15s';
DO $guard$
DECLARE
  name text;
  relation_name text;
BEGIN
  IF current_database()<>'empiredb' THEN
    RAISE EXCEPTION 'TAM scoped reader requires empiredb';
  END IF;
  IF to_regprocedure(
    'public.get_tam_market_observations_scoped(text[],text[],integer)'
  ) IS NOT NULL THEN
    RAISE EXCEPTION 'TAM scoped reader collision; review catalog first';
  END IF;
  IF to_regprocedure('public.get_tam_market_observations(integer)')
    IS NULL OR NOT pg_catalog.has_function_privilege(
      'empire_tam_market_reader',
      'public.get_tam_market_observations(integer)','EXECUTE'
    ) THEN
    RAISE EXCEPTION 'existing isolated TAM 043 function required';
  END IF;
  FOREACH name IN ARRAY ARRAY[
    'empire_tam_market_reader','empire_tam_market_login'
  ] LOOP
    FOREACH relation_name IN ARRAY ARRAY[
      'public.prospect_acquisitions','public.prospect_entity_links',
      'public.business_entities'
    ] LOOP
      IF pg_catalog.has_table_privilege(
        name,relation_name,
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
      ) OR pg_catalog.has_any_column_privilege(
        name,relation_name,'SELECT,INSERT,UPDATE,REFERENCES'
      ) THEN
        RAISE EXCEPTION 'isolated TAM role gained direct source authority';
      END IF;
    END LOOP;
  END LOOP;
END $guard$;

CREATE FUNCTION public.get_tam_market_observations_scoped(
  p_industries text[],
  p_countries text[],
  p_limit integer DEFAULT 1000
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $scoped$
DECLARE
  result jsonb;
  scope_count integer;
BEGIN
  IF p_industries IS NULL OR p_countries IS NULL
    OR pg_catalog.array_ndims(p_industries)<>1
    OR pg_catalog.array_ndims(p_countries)<>1
    OR pg_catalog.cardinality(p_industries) NOT BETWEEN 1 AND 3
    OR pg_catalog.cardinality(p_countries) NOT BETWEEN 1 AND 2
    OR pg_catalog.array_position(p_industries,NULL) IS NOT NULL
    OR pg_catalog.array_position(p_countries,NULL) IS NOT NULL
    OR EXISTS (
      SELECT 1 FROM pg_catalog.unnest(p_industries) v
      WHERE v NOT IN ('roofing','solar','insurance')
    )
    OR EXISTS (
      SELECT 1 FROM pg_catalog.unnest(p_countries) v
      WHERE v NOT IN ('GB','US')
    )
    OR (SELECT count(DISTINCT v) FROM pg_catalog.unnest(p_industries) v)
         <> pg_catalog.cardinality(p_industries)
    OR (SELECT count(DISTINCT v) FROM pg_catalog.unnest(p_countries) v)
         <> pg_catalog.cardinality(p_countries)
  THEN
    RAISE EXCEPTION 'TAM scoped markets must be unique approved countries/sectors';
  END IF;
  scope_count := pg_catalog.cardinality(p_industries)
    * pg_catalog.cardinality(p_countries);
  IF p_limit IS NULL OR p_limit < scope_count OR p_limit > 1000 THEN
    RAISE EXCEPTION 'TAM scoped sample limit must be per-scope to 1000';
  END IF;

  WITH requested AS (
    SELECT i.industry, c.country_code,
      pg_catalog.row_number() OVER (
        ORDER BY i.industry,c.country_code
      )::integer AS scope_rank
    FROM pg_catalog.unnest(p_industries) AS i(industry)
    CROSS JOIN pg_catalog.unnest(p_countries) AS c(country_code)
  ), budgets AS (
    SELECT r.*, (
      p_limit / scope_count
      + CASE WHEN r.scope_rank <= p_limit % scope_count THEN 1 ELSE 0 END
    ) AS quota
    FROM requested r
  ), deduplicated AS (
    SELECT DISTINCT ON (b.industry,b.country_code,l.entity_id)
      b.industry, b.country_code, b.quota,
      l.entity_id, a.created_at AS observed_at, a.id AS acquisition_id,
      pg_catalog.jsonb_build_object(
        'entity_id',l.entity_id,
        'company_name',pg_catalog.btrim(e.canonical_name),
        'industry',b.industry,
        'country_code',b.country_code,
        'source_ref',COALESCE(
          NULLIF(pg_catalog.btrim(a.source_url),''),
          NULLIF(pg_catalog.btrim(a.evidence->>'source_url'),'')
        ),
        'observed_at',a.created_at,
        'acquisition_source',a.source,
        'locale_resolution',a.evidence #>> '{locale,resolved_from}',
        'execution_authority','none'
      ) AS row_data
    FROM budgets b
    JOIN public.business_entities e
      ON pg_catalog.lower(pg_catalog.btrim(e.canonical_niche))=b.industry
    JOIN public.prospect_entity_links l
      ON l.entity_id=e.id AND l.active=true
    JOIN public.prospect_acquisitions a
      ON a.prospect_id=l.prospect_id
      AND pg_catalog.upper(pg_catalog.btrim(
        a.evidence #>> '{locale,country_code}'
      ))=b.country_code
    WHERE pg_catalog.btrim(COALESCE(e.canonical_name,''))<>''
      AND COALESCE(
        NULLIF(pg_catalog.btrim(a.source_url),''),
        NULLIF(pg_catalog.btrim(a.evidence->>'source_url'),'')
      ) IS NOT NULL
    ORDER BY b.industry,b.country_code,l.entity_id,
      a.created_at DESC,a.id DESC
  ), ranked AS (
    SELECT d.*,
      pg_catalog.row_number() OVER (
        PARTITION BY d.industry,d.country_code
        ORDER BY d.observed_at DESC,d.entity_id
      ) AS sample_rank
    FROM deduplicated d
  ), selected AS (
    SELECT * FROM ranked WHERE sample_rank <= quota
  )
  SELECT pg_catalog.jsonb_build_object(
    'schema_version','empire.tam-scoped-reader.v1',
    'selection_method','MARKET_QUOTA_SAMPLED',
    'source_population_complete',false,
    'requested_limit',p_limit,
    'requested_scope_count',scope_count,
    'rows',COALESCE(
      (SELECT pg_catalog.jsonb_agg(
        s.row_data ORDER BY s.sample_rank,s.industry,s.country_code,s.entity_id
      ) FROM selected s),'[]'::jsonb
    ),
    'scope_coverage',COALESCE(
      (SELECT pg_catalog.jsonb_agg(
        pg_catalog.jsonb_build_object(
          'industry',b.industry,
          'country_code',b.country_code,
          'sample_quota',b.quota,
          'selected_count',(SELECT count(*) FROM selected s
            WHERE s.industry=b.industry AND s.country_code=b.country_code),
          'population_complete',false
        ) ORDER BY b.industry,b.country_code
      ) FROM budgets b),'[]'::jsonb
    ),
    'execution_authority','none',
    'buyer_intent_inferred',false,
    'tam_inferred_from_roster',false
  ) INTO result;
  RETURN result;
END;
$scoped$;

REVOKE ALL ON FUNCTION
  public.get_tam_market_observations_scoped(text[],text[],integer)
  FROM PUBLIC, empire_tam_market_login, empire_intelligence_materializer,
    empire_intelligence_materializer_login, empiredb_app;
GRANT EXECUTE ON FUNCTION
  public.get_tam_market_observations_scoped(text[],text[],integer)
  TO empire_tam_market_reader;

DO $verify$
BEGIN
  IF NOT pg_catalog.has_function_privilege(
    'empire_tam_market_reader',
    'public.get_tam_market_observations_scoped(text[],text[],integer)',
    'EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empire_intelligence_materializer',
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
    RAISE EXCEPTION 'scoped TAM function privilege isolation failed';
  END IF;
END $verify$;
COMMIT;
