-- EmpireOS TAM044 SOURCE QUALITY DIAGNOSTIC — read-only, aggregate-only.
-- Bounded deterministic candidate cohort, NOT a population census.
-- No company names, IDs, emails, phones or source URLs are returned.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='25s';
SET LOCAL work_mem='16MB';
DO $guard$
BEGIN
  IF current_database() <> 'empiredb' OR pg_is_in_recovery() THEN
    RAISE EXCEPTION 'TAM_SOURCE_AUDIT_WRONG_DATABASE_OR_REPLICA';
  END IF;
  IF to_regprocedure(
      'public.get_tam_market_observations_scoped(text[],text[],integer)'
    ) IS NULL THEN
    RAISE EXCEPTION 'TAM_SOURCE_AUDIT_REQUIRES_SCOPED_044';
  END IF;
  IF to_regclass('public.prospect_acquisitions') IS NULL
     OR to_regclass('public.prospect_entity_links') IS NULL
     OR to_regclass('public.business_entities') IS NULL THEN
    RAISE EXCEPTION 'TAM_SOURCE_AUDIT_REQUIRED_TABLE_ABSENT';
  END IF;
END $guard$;

WITH
candidate AS MATERIALIZED (
  SELECT e.id,e.canonical_name,e.canonical_niche,
    CASE
      WHEN lower(btrim(e.canonical_niche)) LIKE '%roof%' THEN 'roofing'
      WHEN lower(btrim(e.canonical_niche)) LIKE '%solar%' THEN 'solar'
      WHEN lower(btrim(e.canonical_niche)) LIKE '%insur%' THEN 'insurance'
    END AS sector,
    lower(btrim(e.canonical_niche)) IN (
      'roofing','solar','insurance'
    ) AS is_exact
  FROM public.business_entities e
  WHERE lower(btrim(COALESCE(e.canonical_niche,''))) LIKE '%roof%'
     OR lower(btrim(COALESCE(e.canonical_niche,''))) LIKE '%solar%'
     OR lower(btrim(COALESCE(e.canonical_niche,''))) LIKE '%insur%'
  ORDER BY e.id
  LIMIT 20000
),
acquisitions_by_entity AS MATERIALIZED (
  SELECT c.id,c.sector,c.is_exact,
    btrim(COALESCE(c.canonical_name,'')) <> '' AS has_name,
    l.entity_id IS NOT NULL AS linked,
    l.active IS TRUE AS active_link,
    a.id IS NOT NULL AS has_acquisition,
    upper(btrim(COALESCE(
      a.evidence #>> '{locale,country_code}',''
    ))) AS evidence_country,
    COALESCE(
      NULLIF(btrim(a.source_url),''),
      NULLIF(btrim(a.evidence->>'source_url'),'')
    ) IS NOT NULL AS has_source
  FROM candidate c
  LEFT JOIN public.prospect_entity_links l ON l.entity_id=c.id
  LEFT JOIN public.prospect_acquisitions a ON a.prospect_id=l.prospect_id
),
entity_quality AS MATERIALIZED (
  SELECT id,sector,is_exact,
    bool_or(has_name) AS has_name,
    bool_or(linked) AS any_link,
    bool_or(active_link) AS any_active_link,
    bool_or(active_link AND has_acquisition) AS any_active_acq,
    bool_or(active_link AND has_acquisition AND
      evidence_country NOT IN ('GB','US')) AS nonapproved_or_missing_country,
    bool_or(active_link AND has_acquisition AND evidence_country='GB')
      AS gb_country,
    bool_or(active_link AND has_acquisition AND evidence_country='US')
      AS us_country,
    bool_or(active_link AND has_acquisition AND evidence_country='GB'
      AND has_source) AS gb_source,
    bool_or(active_link AND has_acquisition AND evidence_country='US'
      AND has_source) AS us_source
  FROM acquisitions_by_entity
  GROUP BY id,sector,is_exact
),
scopes AS (
  SELECT sector,country FROM
    (VALUES ('roofing'),('solar'),('insurance')) i(sector)
  CROSS JOIN (VALUES ('GB'),('US')) c(country)
),
stats AS (
  SELECT s.sector,s.country,
    count(q.id) FILTER (WHERE q.is_exact)
      AS exact_niche_entities_in_sample,
    count(q.id) FILTER (WHERE q.is_exact AND q.any_link)
      AS exact_with_any_link,
    count(q.id) FILTER (WHERE q.is_exact AND q.any_active_link)
      AS exact_with_active_link,
    count(q.id) FILTER (WHERE q.is_exact AND q.any_active_acq)
      AS exact_with_active_acquisition,
    count(q.id) FILTER (WHERE q.is_exact AND
      CASE WHEN s.country='GB' THEN q.gb_country ELSE q.us_country END)
      AS exact_with_country_evidence,
    count(q.id) FILTER (WHERE q.is_exact AND
      CASE WHEN s.country='GB' THEN q.gb_source ELSE q.us_source END)
      AS exact_with_country_and_source,
    count(q.id) FILTER (WHERE q.is_exact AND q.has_name AND
      CASE WHEN s.country='GB' THEN q.gb_source ELSE q.us_source END)
      AS exact_reader_eligible_sample,
    count(q.id) FILTER (WHERE NOT q.is_exact)
      AS possible_niche_aliases_unverified,
    count(q.id) FILTER (WHERE NOT q.is_exact AND q.has_name AND
      CASE WHEN s.country='GB' THEN q.gb_source ELSE q.us_source END)
      AS aliases_with_country_and_source_not_reader_eligible,
    count(q.id) FILTER (WHERE q.is_exact AND NOT q.any_active_link)
      AS exact_without_active_link,
    count(q.id) FILTER (WHERE q.is_exact AND q.any_active_link
      AND NOT q.any_active_acq)
      AS exact_active_link_without_acquisition,
    count(q.id) FILTER (WHERE q.is_exact AND q.any_active_acq
      AND q.nonapproved_or_missing_country)
      AS exact_entities_with_other_or_missing_country_evidence,
    count(q.id) FILTER (WHERE q.is_exact AND
      CASE WHEN s.country='GB' THEN q.gb_country ELSE q.us_country END
      AND NOT (CASE WHEN s.country='GB'
        THEN q.gb_source ELSE q.us_source END))
      AS exact_country_evidence_without_usable_source,
    count(q.id) FILTER (WHERE q.is_exact AND NOT q.has_name)
      AS exact_niche_without_canonical_name
  FROM scopes s
  LEFT JOIN entity_quality q ON q.sector=s.sector
  GROUP BY s.sector,s.country
),
report AS (
  SELECT jsonb_build_object(
    'schema_version','empire.tam-source-quality-audit.v1',
    'mode','OBSERVE',
    'source_schema','canonical_empiredb',
    'sample_limit',20000,
    'sampling_method','CANDIDATE_ENTITIES_BY_ID_FIRST_20000',
    'population_complete',false,
    'scope_count',6,
    'candidate_entities_examined',(SELECT count(*) FROM candidate),
    'market_diagnostics',(
      SELECT jsonb_agg(to_jsonb(s) ORDER BY s.sector,s.country)
      FROM stats s
    ),
    'niche_alias_evidence_is_unverified',true,
    'contact_rows_returned',0,
    'company_rows_returned',0,
    'database_write',false,
    'execution_authority','none',
    'outbound_authorized',false,
    'tam_population_estimated',false
  ) AS result
)
SELECT result::text AS tam_source_quality_aggregate_only FROM report;
ROLLBACK;
