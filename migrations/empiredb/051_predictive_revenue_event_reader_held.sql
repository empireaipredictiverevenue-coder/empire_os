-- EmpireDB 051: founder-approval-held single-event evidence capability.
-- STAGED ONLY. NEVER run during normal app boot, cron, or agent startup.
-- Canonical EmpireDB; one existing commercial_event / fulfilment_order.
-- Creates NO LOGIN, credential, tenant binding or scheduled task.
-- Requires separate explicit founder DDL approval, independently reviewed
-- schema/security, backups and a privileged DBA. No customer report release.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

-- Privileged DBA creates ONLY the dedicated, non-login permission role.
-- No overwrite/replacement if somebody else has already created it.
DO $bootstrap$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'REV051_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname=current_user AND rolsuper
  ) THEN
    RAISE EXCEPTION 'REV051_PRIVILEGED_DBA_REQUIRED';
  END IF;
  IF EXISTS(
    SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname='empire_predictive_revenue_evidence_reader'
  ) THEN
    RAISE EXCEPTION 'REV051_EXISTING_ROLE_REVIEW_BEFORE_CHANGE';
  END IF;
  IF pg_catalog.to_regprocedure(
      'public.read_predictive_revenue_event_v1(uuid,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'REV051_EXISTING_FUNCTION_REVIEW_BEFORE_CHANGE';
  END IF;
  CREATE ROLE empire_predictive_revenue_evidence_reader
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
  -- Function execution needs schema USAGE, never source-table SELECT.
  GRANT USAGE ON SCHEMA public TO empire_predictive_revenue_evidence_reader;
END;
$bootstrap$;

SET LOCAL ROLE empiredb_migrator;
DO $guard$
DECLARE relation text;
BEGIN
  IF current_user <> 'empiredb_migrator' THEN
    RAISE EXCEPTION 'REV051_UNTRUSTED_OWNER';
  END IF;
  IF NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname='empire_predictive_revenue_evidence_reader'
       AND NOT rolcanlogin AND NOT rolsuper AND NOT rolinherit
       AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb
       AND NOT rolreplication
  ) THEN
    RAISE EXCEPTION 'REV051_CAPABILITY_ROLE_UNSAFE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
      AND p.prosecdef IS TRUE AND p.provolatile='s'
      AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                        WHERE rolname='empiredb_migrator')
  ) THEN
    RAISE EXCEPTION 'REV051_AUTHENTICATED_SESSION_TENANT_RESOLVER_MISSING';
  END IF;
  FOREACH relation IN ARRAY ARRAY[
    'public.commercial_events', 'public.fulfilment_orders', 'public.buyers'
  ] LOOP
    IF pg_catalog.to_regclass(relation) IS NULL
       OR NOT pg_catalog.has_table_privilege(current_user,relation,'SELECT') THEN
      RAISE EXCEPTION 'REV051_READER_SOURCE_UNAVAILABLE';
    END IF;
  END LOOP;
  -- Reject accidental broad capability-table rights before function creation.
  FOREACH relation IN ARRAY ARRAY[
    'public.commercial_events', 'public.fulfilment_orders', 'public.buyers'
  ] LOOP
    IF pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',relation,'SELECT')
      OR pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',relation,'INSERT')
      OR pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',relation,'UPDATE')
      OR pg_catalog.has_table_privilege(
         'empire_predictive_revenue_evidence_reader',relation,'DELETE')
    THEN
      RAISE EXCEPTION 'REV051_UNEXPECTED_CAPABILITY_TABLE_RIGHTS';
    END IF;
  END LOOP;
END;
$guard$;

-- Caller-supplied p_tenant may NOT select the tenant. Only the
-- canonical session_user -> active DB tenant binding authorises source.
-- No cross-tenant records or original source data are returned on mismatch.
CREATE FUNCTION public.read_predictive_revenue_event_v1(
  p_event_id uuid,
  p_tenant text
)
RETURNS TABLE (
  id uuid,
  order_id uuid,
  event_type text,
  amount_cents bigint,
  occurred_at timestamptz,
  product_id uuid,
  actual_revenue_flag text,
  event_tenant_id text,
  order_tenant_id text,
  lineage_matches boolean,
  product_matches boolean,
  price_matches boolean
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $reader$
  SELECT e.id, o.id, e.event_type, e.amount_cents, e.occurred_at,
         e.product_id,
         e.payload->>'actual_revenue',
         event_buyer.org_id::text,
         order_buyer.org_id::text,
         (e.payload->'causal_lineage'
           IS NOT DISTINCT FROM o.commercial_payload->'causal_lineage'
          AND e.payload->'causal_lineage' IS NOT NULL
          AND e.payload->'causal_lineage' <> '{}'::jsonb),
         (e.product_id=o.product_id),
         (e.amount_cents=o.price_cents)
    FROM public.commercial_events AS e
    JOIN public.fulfilment_orders AS o ON o.id=e.fulfilment_order_id
    JOIN public.buyers AS event_buyer ON event_buyer.id=e.buyer_id
    JOIN public.buyers AS order_buyer ON order_buyer.id=o.buyer_id
   WHERE p_event_id IS NOT NULL
     AND e.id=p_event_id
     AND e.event_type='revenue_recognized'
     AND e.payload->>'actual_revenue'='true'
     AND e.buyer_id=o.buyer_id
     AND e.product_id=o.product_id
     AND e.product_id IS NOT NULL
     AND e.amount_cents>0 AND e.amount_cents=o.price_cents
     AND o.price_cents>0
     AND o.state IN ('settled','outcome_captured')
     AND o.settled_at IS NOT NULL
     AND event_buyer.org_id IS NOT NULL
     AND event_buyer.org_id=order_buyer.org_id
     AND event_buyer.org_id=public.empire_current_tenant_id()
     AND p_tenant=public.empire_current_tenant_id()::text
     AND e.payload->'causal_lineage' IS NOT NULL
     AND e.payload->'causal_lineage' <> '{}'::jsonb
     AND e.payload->'causal_lineage'
       IS NOT DISTINCT FROM o.commercial_payload->'causal_lineage'
$reader$;

REVOKE ALL ON FUNCTION
  public.read_predictive_revenue_event_v1(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  public.read_predictive_revenue_event_v1(uuid,text)
  TO empire_predictive_revenue_evidence_reader;

-- Deliberately DO NOT grant membership to any login or bind any tenant.
-- Post-migration catalog proof will consequently still HOLD on login checks,
-- until a separately approved per-tenant dedicated credential is provisioned.
-- No buyer/payment/ledger table SELECT is granted to this capability.
RESET ROLE;
COMMIT;
