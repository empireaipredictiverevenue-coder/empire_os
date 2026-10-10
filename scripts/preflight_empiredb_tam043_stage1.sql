-- Isolated TAM Stage-1 DBA preflight. READ ONLY. NO DDL / no TAM rows.
-- Run under an authorised PostgreSQL DBA on canonical empiredb.
-- Approval for stage 1 does not override failed backup or catalog gates.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
DO $tam043_preflight$
DECLARE
  expected_columns integer;
  current_columns integer;
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_WRONG_DATABASE';
  END IF;
  IF pg_is_in_recovery() THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_DATABASE_IS_REPLICA';
  END IF;
  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname = 'empiredb_migrator'
      AND NOT rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_MIGRATOR_ROLE_UNVERIFIED';
  END IF;
  IF (
    SELECT count(*) FROM pg_catalog.pg_roles
    WHERE rolname IN (
      'empire_intelligence_materializer',
      'empire_intelligence_materializer_login',
      'empiredb_app'
    )
  ) <> 3 THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_LEGACY_MATERIALIZER_NOT_READY';
  END IF;
  IF EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname IN ('empire_tam_market_reader', 'empire_tam_market_login')
  ) THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_ISOLATED_ROLE_COLLISION';
  END IF;
  IF to_regprocedure('public.get_tam_market_observations(integer)') IS NOT NULL
  THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_RESTRICTED_FUNCTION_COLLISION';
  END IF;
  IF NOT has_table_privilege(
    'empire_intelligence_materializer',
    'public.prospect_entity_links',
    'SELECT'
  ) OR NOT has_table_privilege(
    'empire_intelligence_materializer',
    'public.business_entities',
    'SELECT'
  ) THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_LEGACY_GRANTS_NOT_VERIFIED';
  END IF;
  WITH required(rel,att,type_name) AS (
    VALUES
      ('public.prospect_acquisitions','id','uuid'),
      ('public.prospect_acquisitions','prospect_id','uuid'),
      ('public.prospect_acquisitions','source','text'),
      ('public.prospect_acquisitions','source_url','text'),
      ('public.prospect_acquisitions','evidence','jsonb'),
      ('public.prospect_acquisitions','created_at','timestamp with time zone'),
      ('public.prospect_entity_links','prospect_id','uuid'),
      ('public.prospect_entity_links','entity_id','uuid'),
      ('public.prospect_entity_links','active','boolean'),
      ('public.business_entities','id','uuid'),
      ('public.business_entities','canonical_name','text'),
      ('public.business_entities','canonical_niche','text')
  )
  SELECT count(*), 12 INTO current_columns, expected_columns
  FROM required r
  JOIN pg_catalog.pg_attribute a
    ON a.attrelid=to_regclass(r.rel)
   AND a.attname=r.att
   AND a.attnum>0 AND NOT a.attisdropped
   AND pg_catalog.format_type(a.atttypid,a.atttypmod)=r.type_name;
  IF current_columns <> expected_columns THEN
    RAISE EXCEPTION 'TAM043_PRECHECK_SOURCE_COLUMN_CONTRACT_DRIFT';
  END IF;
  RAISE NOTICE 'TAM043_STAGE1_READ_ONLY_CATALOG_PREFLIGHT_PASS';
END $tam043_preflight$;
ROLLBACK;
