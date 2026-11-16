-- EmpireDB 077: original bounded UTC-day revenue source census, HELD.
-- No Supabase roles or migrations, no production auto-apply.
-- Existing REV051 restricted role + trusted session_user -> tenant resolver only.
-- READ-ONLY source candidate: not a finalized payment, daily close or accuracy label.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $preflight$
DECLARE source_relation text;
BEGIN
  IF current_database() <> 'empiredb' OR pg_catalog.pg_is_in_recovery() THEN
    RAISE EXCEPTION 'REV077_CANONICAL_EMPIREDB_REQUIRED';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname=current_user AND rolsuper) THEN
    RAISE EXCEPTION 'REV077_PRIVILEGED_DBA_REQUIRED';
  END IF;
  IF pg_catalog.to_regprocedure(
       'public.read_predictive_revenue_day_v1(date,text)') IS NOT NULL THEN
    RAISE EXCEPTION 'REV077_EXISTING_FUNCTION_REVIEW_REQUIRED';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname='empiredb_migrator') OR NOT
     pg_catalog.has_schema_privilege('empiredb_migrator','public','CREATE') THEN
    RAISE EXCEPTION 'REV077_EXISTING_MIGRATOR_AUTHORITY_REQUIRED';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname='empire_predictive_revenue_evidence_reader'
       AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
       AND NOT rolinherit AND NOT rolcreatedb AND NOT rolcreaterole
       AND NOT rolreplication) THEN
    RAISE EXCEPTION 'REV077_ORIGINAL_RESTRICTED_EVIDENCE_ROLE_REQUIRED';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc p
     WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
       AND p.prosecdef AND p.provolatile='s'
       AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
         WHERE rolname='empiredb_migrator')) THEN
    RAISE EXCEPTION 'REV077_TRUSTED_SESSION_TENANT_RESOLVER_REQUIRED';
  END IF;
  IF pg_catalog.to_regprocedure(
       'public.read_predictive_revenue_event_v1(uuid,text)') IS NULL THEN
    RAISE EXCEPTION 'REV077_ORIGINAL_SINGLE_EVENT_READER_REQUIRED';
  END IF;
  FOREACH source_relation IN ARRAY ARRAY[
    'public.commercial_events','public.fulfilment_orders','public.buyers'
  ] LOOP
    IF pg_catalog.to_regclass(source_relation) IS NULL OR NOT
       pg_catalog.has_table_privilege('empiredb_migrator',
         source_relation,'SELECT') THEN
      RAISE EXCEPTION 'REV077_EXISTING_EMPIREDB_SOURCE_UNAVAILABLE';
    END IF;
    IF pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',source_relation,'SELECT')
       OR pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',source_relation,'INSERT')
       OR pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',source_relation,'UPDATE')
       OR pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',source_relation,'DELETE') THEN
      RAISE EXCEPTION 'REV077_READER_HAS_UNEXPECTED_DIRECT_TABLE_RIGHTS';
    END IF;
  END LOOP;
END
$preflight$;

SET LOCAL ROLE empiredb_migrator;

-- Matches the existing Python read_daily_revenue_census() contract exactly.
-- A global incomplete source row blocks even an apparently valid tenant day;
-- never conceal unmapped ledger events, duplicates, refunds or missing finality.
CREATE FUNCTION public.read_predictive_revenue_day_v1(
  p_day date, p_tenant text
)
RETURNS TABLE (
  day_utc date,
  scope_tenant_id text,
  global_event_count bigint,
  valid_tenant_event_count bigint,
  tenant_amount_cents bigint,
  global_invalid_count bigint,
  tenant_invalid_count bigint,
  snapshot_at timestamptz
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = ''
AS $reader$
DECLARE
  trusted_tenant uuid;
  safe_tenant_count bigint;
  safe_tenant_amount bigint;
  invalid_source_count bigint;
BEGIN
  trusted_tenant := public.empire_current_tenant_id();
  IF trusted_tenant IS NULL OR p_tenant IS NULL
     OR p_tenant <> trusted_tenant::text THEN
    RAISE EXCEPTION 'REV077_UNAUTHENTICATED_TENANT';
  END IF;
  IF p_day IS NULL OR p_day >=
     (pg_catalog.transaction_timestamp() AT TIME ZONE 'UTC')::date THEN
    RAISE EXCEPTION 'REV077_COMPLETED_UTC_DAY_REQUIRED';
  END IF;
  -- The aggregate must observe the complete source-day ledger. If later
  -- migrations change source ownership or FORCE RLS, an owner-scoped SELECT
  -- can silently hide other tenant/unmapped records. Fail rather than falsely
  -- call a filtered count global or suppress an invalid source record.
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    WHERE c.oid IN (
      pg_catalog.to_regclass('public.commercial_events'),
      pg_catalog.to_regclass('public.fulfilment_orders'),
      pg_catalog.to_regclass('public.buyers'))
      AND (c.relforcerowsecurity OR c.relowner <>
        (SELECT oid FROM pg_catalog.pg_roles
         WHERE rolname='empiredb_migrator'))
  ) THEN
    RAISE EXCEPTION 'REV077_GLOBAL_LEDGER_VISIBILITY_UNPROVEN';
  END IF;

  -- Full ledger inspection stays inside this SECURITY DEFINER function.
  -- Never return other tenants' event counts or global invalid counts.
  -- An incomplete source returns only a generic failure, not a count.
  WITH source AS MATERIALIZED (
    SELECT
      e.amount_cents AS amount,
      COUNT(*) OVER (PARTITION BY e.fulfilment_order_id)
        AS order_recognition_count,
      eb.org_id = trusted_tenant AS belongs_to_tenant,
      (
        e.payload->>'actual_revenue'='true'
        AND e.buyer_id IS NOT NULL
        AND e.product_id IS NOT NULL
        AND o.id IS NOT NULL
        AND o.buyer_id=e.buyer_id
        AND o.product_id=e.product_id
        AND o.state IN ('settled','outcome_captured')
        AND o.settled_at IS NOT NULL
        -- A subsequent settlement cannot validate an earlier day as of its
        -- original close. Independent bank finality is still NOT attested.
        AND o.settled_at < ((p_day + 1)::timestamp AT TIME ZONE 'UTC')
        AND o.settled_at <= e.occurred_at
        -- The same order must not be recognized again on another date.
        -- An index on commercial_events(fulfilment_order_id) already exists.
        AND NOT EXISTS (
          SELECT 1 FROM public.commercial_events another
          WHERE another.fulfilment_order_id=e.fulfilment_order_id
            AND another.event_type='revenue_recognized'
            AND another.id<>e.id
        )
        AND o.price_cents>0
        AND e.amount_cents>0
        AND e.amount_cents=o.price_cents
        AND eb.id IS NOT NULL
        AND ob.id IS NOT NULL
        AND eb.org_id IS NOT NULL
        AND ob.org_id=eb.org_id
        AND e.payload->'causal_lineage' IS NOT NULL
        AND e.payload->'causal_lineage' <> '{}'::jsonb
        AND e.payload->'causal_lineage'
          IS NOT DISTINCT FROM o.commercial_payload->'causal_lineage'
      ) IS TRUE AS valid
    FROM public.commercial_events e
    LEFT JOIN public.fulfilment_orders o ON o.id=e.fulfilment_order_id
    LEFT JOIN public.buyers eb ON eb.id=e.buyer_id
    LEFT JOIN public.buyers ob ON ob.id=o.buyer_id
    WHERE e.event_type='revenue_recognized'
      AND e.occurred_at >= (p_day::timestamp AT TIME ZONE 'UTC')
      AND e.occurred_at < ((p_day + 1)::timestamp AT TIME ZONE 'UTC')
  )
  SELECT
    COUNT(*) FILTER (
      WHERE valid AND order_recognition_count=1
        AND belongs_to_tenant IS TRUE)::bigint,
    COALESCE(SUM(amount) FILTER (
      WHERE valid AND order_recognition_count=1
        AND belongs_to_tenant IS TRUE),0)::bigint,
    COUNT(*) FILTER (
      WHERE NOT valid OR order_recognition_count<>1)::bigint
  INTO safe_tenant_count, safe_tenant_amount, invalid_source_count
  FROM source;

  IF invalid_source_count<>0 THEN
    -- Nothing about other tenants or the malformed source count is returned.
    RAISE EXCEPTION 'REV077_SOURCE_DAY_INCOMPLETE';
  END IF;
  RETURN QUERY SELECT
    p_day::date,
    trusted_tenant::text,
    safe_tenant_count,
    safe_tenant_count,
    safe_tenant_amount,
    0::bigint,
    0::bigint,
    pg_catalog.transaction_timestamp();
END;
$reader$;

REVOKE ALL ON FUNCTION public.read_predictive_revenue_day_v1(date,text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.read_predictive_revenue_day_v1(date,text)
  TO empire_predictive_revenue_evidence_reader;

-- DO NOT grant table SELECT, login memberships or customer release.
-- Counts and sums are source-candidate observations ONLY.
-- Bank settlement, refunds/chargebacks, backfill closure and currency
-- reconciliation are independently unverified and remain fail-closed.
RESET ROLE;
COMMIT;
