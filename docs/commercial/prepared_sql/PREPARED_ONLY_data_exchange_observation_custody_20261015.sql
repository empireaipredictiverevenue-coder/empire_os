-- Empire Data Exchange V15: PREPARED ONLY. DO NOT APPLY from feature branch.
-- Intentionally UNNUMBERED: multiple other active branches reserve migration 052.
-- Production sequencing and independent review are required before renumbering.
-- Requires a separately provisioned dedicated NOLOGIN/NOINHERIT role.
-- No role membership, LOGIN, password, service activation or data backfill here.
-- No change to payment, outbound, authorisation or generic empiredb_app.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $custody_guard$
BEGIN
 IF current_database() NOT IN ('empiredb','data_exchange_custody_fixture') THEN
    RAISE EXCEPTION 'unexpected Data Exchange custody migration target';
 END IF;
 IF pg_catalog.to_regclass('public.empire_data_exchange_observations') IS NOT NULL THEN
    RAISE EXCEPTION 'Data Exchange custody table exists: reconcile before migration';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_data_exchange_custodian'
     AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
     AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN
   RAISE EXCEPTION 'separately provisioned NOLOGIN data custodian role required';
 END IF;
END;
$custody_guard$;

CREATE TABLE public.empire_data_exchange_observations (
 sequence bigint PRIMARY KEY CHECK (sequence BETWEEN 0 AND 1000000000),
 schema_version text NOT NULL DEFAULT 'empire.data_exchange.observation_custody.v15'
   CHECK (schema_version = 'empire.data_exchange.observation_custody.v15'),
 source_id text NOT NULL CHECK (source_id = 'gb_planning_data'),
 dataset_id text NOT NULL CHECK (dataset_id = 'brownfield-land'),
 region text NOT NULL CHECK (region = 'north_west_england'),
 source_observed_at timestamptz NOT NULL,
 snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
 previous_chain_sha256 text NOT NULL CHECK (previous_chain_sha256 ~ '^[0-9a-f]{64}$'),
 chain_sha256 text NOT NULL UNIQUE CHECK (chain_sha256 ~ '^[0-9a-f]{64}$'),
 snapshot_json jsonb NOT NULL CHECK (
    jsonb_typeof(snapshot_json) = 'object'
    AND octet_length(snapshot_json::text) <= 131072
    AND snapshot_json->>'schema_version' = 'empire.data_exchange.construction_preview.v1'
    AND snapshot_json->>'mode' = 'OBSERVE'
    AND snapshot_json->>'data_source' = 'gb_planning_data'
    AND snapshot_json->>'source_dataset' = 'brownfield-land'
    AND snapshot_json->>'pilot_region' = 'north_west_england'
    AND snapshot_json->>'assessment_status' = 'HOLD'
    AND snapshot_json->>'rights_review_eligible' = 'false'
    AND snapshot_json->>'source_claim_verification' = 'NOT_INDEPENDENTLY_VERIFIED'
    AND snapshot_json->>'customer_delivery_enabled' = 'false'
    AND snapshot_json->>'data_resale_authorized' = 'false'
    AND snapshot_json->>'outbound_enabled' = 'false'
    AND snapshot_json->>'payment_execution' = 'false'
    AND snapshot_json->>'actual_revenue' = 'false'
    AND snapshot_json->>'production_writes' = 'false'
    AND snapshot_json->>'execution_authority' = 'NONE'
    AND jsonb_typeof(snapshot_json->'records') = 'array'
    AND jsonb_array_length(snapshot_json->'records') BETWEEN 1 AND 50
 ),
 recorded_by_server_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.empire_data_exchange_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_data_exchange_observations FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.empire_data_exchange_observations FROM PUBLIC;

CREATE POLICY empire_data_exchange_custody_select
  ON public.empire_data_exchange_observations FOR SELECT
  TO empire_data_exchange_custodian USING (true);
CREATE POLICY empire_data_exchange_custody_insert
  ON public.empire_data_exchange_observations FOR INSERT
  TO empire_data_exchange_custodian WITH CHECK (
    snapshot_json->>'customer_delivery_enabled'='false'
    AND snapshot_json->>'execution_authority'='NONE'
  );

-- In addition to the Python normalizer, the database bans private fields
-- and insists on linear, non-future source custody even if a caller bypasses
-- the Python script. This does not cryptographically verify government origin.
CREATE FUNCTION public.empire_data_exchange_before_custody_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER AS $body$
DECLARE
  prior public.empire_data_exchange_observations%ROWTYPE;
  item jsonb;
  key_name text;
BEGIN
  PERFORM pg_catalog.pg_advisory_xact_lock(510218720);
  IF NEW.source_observed_at > clock_timestamp() THEN
    RAISE EXCEPTION 'future Data Exchange observation';
  END IF;
  IF NEW.source_observed_at < clock_timestamp() - interval '90 days' THEN
    RAISE EXCEPTION 'stale Data Exchange observation';
  END IF;
  IF (
    jsonb_typeof(NEW.snapshot_json->'records') IS DISTINCT FROM 'array'
    OR NEW.snapshot_json->'rights_holds' IS DISTINCT FROM '["RIGHTS_REVIEW_MISSING"]'::jsonb
    OR (NEW.snapshot_json->>'dataset_record_count')::integer
         IS DISTINCT FROM jsonb_array_length(NEW.snapshot_json->'records')
  ) THEN
    RAISE EXCEPTION 'invalid Data Exchange record collection or rights hold';
  END IF;
  FOR key_name IN SELECT jsonb_object_keys(NEW.snapshot_json) LOOP
    IF key_name NOT IN (
      'schema_version','mode','product','pilot_region','data_source',
      'source_dataset','dataset_record_count','records','rejected_counts',
      'rights_review_eligible','rights_holds','assessment_status',
      'source_claim_verification','signal_semantics',
      'customer_delivery_enabled','data_resale_authorized',
      'outbound_enabled','payment_execution','production_writes',
      'actual_revenue','execution_authority'
    ) THEN
      RAISE EXCEPTION 'unreviewed Data Exchange snapshot metadata';
    END IF;
  END LOOP;
  FOR item IN SELECT value FROM jsonb_array_elements(NEW.snapshot_json->'records')
  LOOP
    IF jsonb_typeof(item) IS DISTINCT FROM 'object' THEN
       RAISE EXCEPTION 'invalid Data Exchange source record';
    END IF;
    IF (
      item->>'source_id' IS DISTINCT FROM 'gb_planning_data'
      OR item->>'dataset_id' IS DISTINCT FROM 'brownfield-land'
      OR item->>'region' IS DISTINCT FROM 'north_west_england'
      OR item->>'record_type' IS DISTINCT FROM 'brownfield_land'
      OR item->>'signal_class' IS DISTINCT FROM 'development_context_not_buyer_intent'
      OR (item->>'record_id') IS NULL
      OR (item->>'record_id') !~ '^[0-9]{1,12}$'
      OR (item->>'source_url') IS DISTINCT FROM
           ('https://www.planning.data.gov.uk/entity/' || (item->>'record_id'))
      OR (item->>'source_observed_at') IS NULL
      OR (item->>'source_observed_at')::timestamptz IS DISTINCT FROM NEW.source_observed_at
    ) THEN
      RAISE EXCEPTION 'Data Exchange record identity or observation invalid';
    END IF;
    FOR key_name IN SELECT jsonb_object_keys(item) LOOP
      IF key_name NOT IN (
        'record_id','source_id','dataset_id','region','record_type',
        'source_url','source_observed_at','signal_class',
        'planning_permission_status','site_area_hectares','source_entry_date'
      ) THEN
        RAISE EXCEPTION 'unreviewed Data Exchange source field';
      END IF;
    END LOOP;
  END LOOP;
  SELECT * INTO prior
    FROM public.empire_data_exchange_observations
    ORDER BY sequence DESC LIMIT 1;
  IF NOT FOUND THEN
    IF NEW.sequence <> 0 OR NEW.previous_chain_sha256 <> repeat('0',64) THEN
      RAISE EXCEPTION 'invalid Data Exchange genesis commitment';
    END IF;
  ELSIF (
    NEW.sequence <> prior.sequence+1
    OR NEW.previous_chain_sha256 <> prior.chain_sha256
    OR NEW.source_observed_at <= prior.source_observed_at
    OR NEW.source_observed_at > prior.source_observed_at + interval '90 days'
  ) THEN
    RAISE EXCEPTION 'Data Exchange continuity mismatch';
  END IF;
  RETURN NEW;
END;
$body$;
CREATE TRIGGER empire_data_exchange_custody_append_guard
BEFORE INSERT ON public.empire_data_exchange_observations
FOR EACH ROW EXECUTE FUNCTION public.empire_data_exchange_before_custody_insert();

CREATE FUNCTION public.empire_data_exchange_deny_custody_change()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER AS $body$
BEGIN
  RAISE EXCEPTION 'append-only Data Exchange custody: mutation prohibited';
END;
$body$;
CREATE TRIGGER empire_data_exchange_custody_immutable_rows
BEFORE UPDATE OR DELETE ON public.empire_data_exchange_observations
FOR EACH ROW EXECUTE FUNCTION public.empire_data_exchange_deny_custody_change();
CREATE TRIGGER empire_data_exchange_custody_no_truncate
BEFORE TRUNCATE ON public.empire_data_exchange_observations
FOR EACH STATEMENT EXECUTE FUNCTION public.empire_data_exchange_deny_custody_change();

GRANT USAGE ON SCHEMA public TO empire_data_exchange_custodian;
GRANT SELECT,INSERT ON public.empire_data_exchange_observations
 TO empire_data_exchange_custodian;
COMMENT ON TABLE public.empire_data_exchange_observations IS
 'Local append-only Planning Data observation custody, source-claimed not independently authenticated. OBSERVE only; never buyer intent, licensed export or revenue.';
COMMIT;
