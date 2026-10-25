-- PREPARED ONLY: EmpireDB 068 V4.16 bounded operational reversal signals.
-- Extends prepared 067 capability; does not create login, table, source grant,
-- mutate any canonical records, process refunds or recognise revenue.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v415_fixture','empire_v416_fixture') THEN
   RAISE EXCEPTION 'V416_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE
   rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE
   rolname='empire_predictive_cash_candidate_reader'
   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'V416_ORIGINAL_READER_CAPABILITY_REQUIRED'; END IF;
 IF pg_catalog.to_regprocedure(
   'public.read_predictive_direct_bsc_cash_candidate_v1(uuid,uuid[])') IS NULL
 THEN RAISE EXCEPTION 'V416_MIGRATION_067_NOT_PRESENT'; END IF;
 IF pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_reversal_signals_v1(uuid,uuid[])') IS NOT NULL
 THEN RAISE EXCEPTION 'V416_DUPLICATE_READER'; END IF;
 IF pg_catalog.to_regclass('public.commercial_outcomes') IS NULL
 OR NOT pg_catalog.has_table_privilege(
   'empiredb_migrator','public.commercial_outcomes','SELECT')
 THEN RAISE EXCEPTION 'V416_CANONICAL_OUTCOMES_NOT_READABLE'; END IF;
 IF pg_catalog.has_table_privilege(
   'empire_predictive_cash_candidate_reader','public.commercial_outcomes','SELECT')
 THEN RAISE EXCEPTION 'V416_READER_HAS_RAW_OUTCOME_SELECT'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_proc
   WHERE oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
   AND prosecdef AND proowner=pg_catalog.to_regrole('empiredb_migrator'))
 THEN RAISE EXCEPTION 'V416_ORIGINAL_TENANT_RESOLVER_REQUIRED'; END IF;
END;
$guard$;
SET LOCAL ROLE empiredb_migrator;
CREATE FUNCTION public.read_predictive_revenue_reversal_signals_v1(
  p_tenant uuid, p_order_ids uuid[]
) RETURNS TABLE(
  selected_order_id uuid,
  operational_signal_status text,
  refunded_delivery_signal_count integer,
  failed_or_rejected_delivery_signal_count integer,
  monetary_reversal_independently_verified boolean,
  full_refund_census_verified boolean,
  net_cash_earned_verified boolean,
  automatic_execution_authorized boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=''
AS $reader$
DECLARE
  v_tenant uuid;
  order_to_check uuid;
  v_visible boolean;
  v_refunded bigint;
  v_failed bigint;
BEGIN
 IF session_user <> 'empire_predictive_cash_candidate_login' THEN
   RAISE EXCEPTION 'V416_DEDICATED_LOGIN_REQUIRED';
 END IF;
 v_tenant:=public.empire_current_tenant_id();
 IF p_tenant IS NULL OR v_tenant IS NULL OR p_tenant <> v_tenant THEN
   RAISE EXCEPTION 'V416_SESSION_TENANT_DENIED';
 END IF;
 IF p_order_ids IS NULL
   OR pg_catalog.cardinality(p_order_ids) NOT BETWEEN 1 AND 8
   OR EXISTS(SELECT 1 FROM pg_catalog.unnest(p_order_ids) AS item WHERE item IS NULL)
   OR (SELECT count(DISTINCT item) FROM pg_catalog.unnest(p_order_ids) AS item)
       <> pg_catalog.cardinality(p_order_ids)
 THEN RAISE EXCEPTION 'V416_BOUNDED_UNIQUE_ORDERS_REQUIRED'; END IF;
 FOREACH order_to_check IN ARRAY p_order_ids LOOP
   -- Check the original buyer's org, never GUC, unbound caller or hidden row.
   SELECT EXISTS(
     SELECT 1 FROM public.fulfilment_orders o JOIN public.buyers b
       ON b.id=o.buyer_id
     WHERE o.id=order_to_check AND b.org_id=v_tenant
   ) INTO v_visible;
   selected_order_id:=order_to_check;
   refunded_delivery_signal_count:=0;
   failed_or_rejected_delivery_signal_count:=0;
   monetary_reversal_independently_verified:=false;
   full_refund_census_verified:=false;
   net_cash_earned_verified:=false;
   automatic_execution_authorized:=false;
   IF v_visible THEN
     SELECT count(*) FILTER (WHERE delivery_outcome='refunded'),
            count(*) FILTER (WHERE delivery_outcome IN ('failed','rejected'))
     INTO v_refunded,v_failed
     FROM public.commercial_outcomes c
     WHERE c.fulfilment_order_id=order_to_check
       AND c.recorded_at<=pg_catalog.statement_timestamp();
     refunded_delivery_signal_count:=LEAST(v_refunded,100000)::integer;
     failed_or_rejected_delivery_signal_count:=LEAST(v_failed,100000)::integer;
     operational_signal_status:=CASE
       WHEN v_refunded>0 THEN 'REFUND_LIKE_DELIVERY_SIGNAL_HELD'
       WHEN v_failed>0 THEN 'FAILED_OR_REJECTED_DELIVERY_SIGNAL_HELD'
       ELSE 'NO_REFUND_LIKE_DELIVERY_RECORD_OBSERVED_HELD' END;
   ELSE
     operational_signal_status:='ORDER_NOT_VISIBLE_OR_UNKNOWN_HELD';
   END IF;
   RETURN NEXT;
 END LOOP;
END;
$reader$;
REVOKE ALL ON FUNCTION
  public.read_predictive_revenue_reversal_signals_v1(uuid,uuid[])
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  public.read_predictive_revenue_reversal_signals_v1(uuid,uuid[])
  TO empire_predictive_cash_candidate_reader;
COMMENT ON FUNCTION
 public.read_predictive_revenue_reversal_signals_v1(uuid,uuid[])
IS 'Held, tenant-restricted operational delivery status only. Does NOT attest financial refund, chargeback, absence of reversals, complete cohort or net cash.';
COMMIT;
