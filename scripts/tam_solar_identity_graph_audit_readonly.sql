-- Source Acquisition: existing UK solar identity graph/readiness audit.
-- No company names, prospect UUIDs, websites, phones or contact info leave SQL.
-- Only diagnostic aggregates; MUST NOT infer verified UK residence.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '20s';
SET LOCAL work_mem='16MB';
DO $guard$
BEGIN
  IF current_database()<>'empiredb' OR pg_is_in_recovery() THEN
    RAISE EXCEPTION 'SOURCE_IDENTITY_AUDIT_NONCANONICAL_DATABASE';
  END IF;
  IF to_regclass('public.business_entities') IS NULL
     OR to_regclass('public.prospect_entity_links') IS NULL
     OR to_regclass('public.prospects') IS NULL
     OR to_regclass('public.prospect_acquisitions') IS NULL THEN
    RAISE EXCEPTION 'SOURCE_IDENTITY_AUDIT_MISSING_CANONICAL_TABLE';
  END IF;
END $guard$;
WITH
targets AS MATERIALIZED (
  SELECT e.id,e.canonical_name,e.normalized_name,e.canonical_website,
         e.canonical_phone,e.identity_confidence,e.resolution_state,
         e.canonical_metro,e.provenance
  FROM public.business_entities e
  WHERE lower(btrim(e.canonical_niche))='solar'
    AND btrim(e.canonical_name)<>''
    AND EXISTS (
      SELECT 1 FROM public.prospect_entity_links l
      WHERE l.entity_id=e.id AND l.active IS TRUE
    )
    AND NOT EXISTS (
      SELECT 1 FROM public.prospect_entity_links l
      JOIN public.prospect_acquisitions a ON a.prospect_id=l.prospect_id
      WHERE l.entity_id=e.id AND l.active IS TRUE
    )
  ORDER BY e.id LIMIT 250
),
links AS MATERIALIZED (
  SELECT t.id,t.canonical_name,t.normalized_name,t.canonical_website,
         t.canonical_phone,t.identity_confidence,t.resolution_state,
         t.canonical_metro,t.provenance,
         l.prospect_id,l.match_method,
         p.business_name AS prospect_name,p.website AS prospect_website,
         p.phone AS prospect_phone,p.metro AS prospect_metro,
         p.niche AS prospect_niche,
         CASE
           WHEN p.website ~* '^https?://[^/ ]+' THEN
             lower(split_part(split_part(regexp_replace(p.website,
              '^https?://(www[.])?', '', 'i'), '/',1),':',1))
           ELSE ''
         END AS prospect_domain,
         CASE
           WHEN t.canonical_website ~* '^https?://[^/ ]+' THEN
             lower(split_part(split_part(regexp_replace(t.canonical_website,
              '^https?://(www[.])?', '', 'i'), '/',1),':',1))
           ELSE ''
         END AS entity_domain
  FROM targets t
  JOIN public.prospect_entity_links l
    ON l.entity_id=t.id AND l.active IS TRUE
  JOIN public.prospects p ON p.id=l.prospect_id
),
entity_quality AS MATERIALIZED (
  SELECT id,
     count(DISTINCT prospect_id) AS links,
     count(DISTINCT prospect_domain) FILTER (WHERE prospect_domain<>'')
       AS distinct_prospect_website_hosts,
     count(*) FILTER (WHERE prospect_domain<>'') AS links_with_website,
     count(*) FILTER (WHERE btrim(COALESCE(prospect_phone,''))<>'')
       AS links_with_phone,
     count(*) FILTER (
       WHERE lower(btrim(COALESCE(prospect_name,'')))
           <>lower(btrim(COALESCE(canonical_name,'')))
     ) AS names_differ_from_entity,
     count(*) FILTER (
       WHERE lower(btrim(COALESCE(prospect_niche,''))) <> 'solar'
     ) AS prospect_niche_disagreements,
     max(CASE WHEN identity_confidence IS NULL OR
         identity_confidence < 0.80 THEN 1 ELSE 0 END)
       AS low_identity_confidence,
     max(CASE WHEN lower(btrim(COALESCE(resolution_state,'')))
         NOT IN ('resolved','verified') THEN 1 ELSE 0 END)
       AS resolution_not_verified,
     max(CASE WHEN entity_domain<>'' THEN 1 ELSE 0 END)
       AS has_entity_domain,
     max(CASE WHEN btrim(COALESCE(canonical_phone,''))<>''
       THEN 1 ELSE 0 END) AS has_entity_phone,
     max(CASE WHEN btrim(COALESCE(canonical_metro,''))<>''
       THEN 1 ELSE 0 END) AS has_entity_metro,
     max(CASE WHEN upper(btrim(COALESCE(
       provenance #>> '{locale,country_code}','')))='GB'
       THEN 1 ELSE 0 END) AS provenance_explicitly_gb,
     count(*) FILTER (
       WHERE entity_domain<>'' AND prospect_domain<>''
         AND entity_domain<>prospect_domain
     ) AS entity_vs_prospect_website_disagreement
  FROM links GROUP BY id
),
total AS (
 SELECT
   (SELECT count(*) FROM targets) AS target_entities,
   (SELECT count(*) FROM links) AS active_link_rows,
   (SELECT count(DISTINCT prospect_id) FROM links) AS distinct_prospects,
   (SELECT count(*) FROM entity_quality WHERE links=1)
       AS single_prospect_entities,
   (SELECT count(*) FROM entity_quality WHERE low_identity_confidence=1)
       AS entities_with_low_or_missing_identity_confidence,
   (SELECT count(*) FROM entity_quality WHERE resolution_not_verified=1)
       AS entities_without_verified_resolution_state,
   (SELECT count(*) FROM entity_quality WHERE links BETWEEN 2 AND 5)
       AS entities_with_2_to_5_prospects,
   (SELECT count(*) FROM entity_quality WHERE links BETWEEN 6 AND 20)
       AS entities_with_6_to_20_prospects,
   (SELECT count(*) FROM entity_quality WHERE links>20)
       AS entities_with_more_than_20_prospects,
   (SELECT max(links) FROM entity_quality) AS maximum_links_on_one_entity,
   (SELECT count(*) FROM entity_quality
       WHERE distinct_prospect_website_hosts>1)
       AS entities_with_multiple_prospect_website_hosts,
   (SELECT count(*) FROM entity_quality WHERE has_entity_domain=1)
       AS entities_with_canonical_website,
   (SELECT count(*) FROM entity_quality
       WHERE has_entity_domain=0 AND links_with_website>0)
       AS entities_without_canonical_website_but_linked_website,
   (SELECT count(*) FROM entity_quality
       WHERE has_entity_domain=0 AND links_with_website=0)
       AS entities_without_any_website,
   (SELECT count(*) FROM entity_quality WHERE links_with_phone>0)
       AS entities_with_phone_on_linked_prospect,
   (SELECT count(*) FROM entity_quality WHERE has_entity_phone=1)
       AS entities_with_canonical_phone,
   (SELECT count(*) FROM entity_quality
       WHERE names_differ_from_entity>0)
       AS entities_with_linked_prospect_name_variants,
   (SELECT count(*) FROM entity_quality
       WHERE prospect_niche_disagreements>0)
       AS entities_with_linked_prospect_niche_mismatch,
   (SELECT count(*) FROM entity_quality
       WHERE entity_vs_prospect_website_disagreement>0)
       AS entities_with_website_host_disagreements,
   (SELECT count(*) FROM entity_quality WHERE has_entity_metro=1)
       AS entities_with_metro,
   (SELECT count(*) FROM entity_quality WHERE provenance_explicitly_gb=1)
       AS entities_with_explicit_gb_provenance
)
SELECT jsonb_build_object(
    'schema_version','empire.tam-source-identity-graph-audit.v1',
    'mode','OBSERVE',
    'source_population_complete',false,
    'sampled_entity_ceiling',250,
    'canonical_scope','SOLAR_LINKED_NO_ACQUISITION',
    'metrics',to_jsonb(total),
    'company_rows_returned',0,
    'contact_rows_returned',0,
    'identity_merges_authorized',false,
    'acquisitions_appended',0,
    'database_write',false,
    'execution_authority','none'
)::text FROM total;
ROLLBACK;
