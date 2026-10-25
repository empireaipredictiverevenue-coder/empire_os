-- EmpireDB 069 PREPARED ONLY: complete tenant-owned ORDER cohort window.
-- Original EmpireDB, original buyer-bound ownership, 067 reader capability.
-- No new database, login, RLS grants, payments, CRM writes or model promotion.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $preflight$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v415_fixture') THEN
    RAISE EXCEPTION 'V417_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
      AND NOT rolsuper AND NOT rolbypassrls)
 OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_predictive_cash_candidate_reader'
      AND NOT rolcanlogin AND NOT rolsuper AND NOT rolinherit
      AND NOT rolbypassrls) THEN
    RAISE EXCEPTION 'V417_ORIGINAL_READER_ROLES_REQUIRED';
 END IF;
 IF pg_catalog.to_regprocedure(
   'public.read_predictive_direct_bsc_cash_candidate_v1(uuid,uuid[])') IS NULL
 THEN RAISE EXCEPTION 'V417_ORIGINAL_067_REQUIRED'; END IF;
 IF pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_reversal_signals_v1(uuid,uuid[])') IS NULL
 THEN RAISE EXCEPTION 'V417_ORIGINAL_068_REQUIRED'; END IF;
 IF pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_tenant_order_cohort_v1(uuid,timestamptz,timestamptz)')
    IS NOT NULL THEN RAISE EXCEPTION 'V417_READER_ALREADY_EXISTS'; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc
    WHERE oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
      AND prosecdef AND proowner=pg_catalog.to_regrole('empiredb_migrator'))
 THEN RAISE EXCEPTION 'V417_ORIGINAL_SESSION_TENANT_REQUIRED'; END IF;
 IF pg_catalog.to_regclass('public.buyers') IS NULL
 OR pg_catalog.to_regclass('public.fulfilment_orders') IS NULL
 OR NOT pg_catalog.has_table_privilege('empiredb_migrator','public.buyers','SELECT')
 OR NOT pg_catalog.has_table_privilege('empiredb_migrator','public.fulfilment_orders','SELECT')
 OR pg_catalog.has_table_privilege(
      'empire_predictive_cash_candidate_reader','public.fulfilment_orders','SELECT')
 OR pg_catalog.has_table_privilege(
      'empire_predictive_cash_candidate_reader','public.buyers','SELECT')
 THEN RAISE EXCEPTION 'V417_ORIGINAL_ORDER_ACL_CONTRACT_FAILED'; END IF;
END;
$preflight$;

SET LOCAL ROLE empiredb_migrator;

CREATE FUNCTION public.read_predictive_revenue_tenant_order_cohort_v1(
 p_tenant uuid, p_start timestamptz, p_end timestamptz
)
RETURNS TABLE(
 selected_order_count bigint,
 current_state_settled_or_outcome_captured bigint,
 current_state_rejected bigint,
 current_state_cancelled bigint,
 current_state_other_or_open bigint,
 selected_orders_without_opportunity_id bigint,
 distinct_order_linked_opportunity_ids bigint,
 multiple_orders_per_opportunity boolean,
 complete_buyer_owned_order_window_scanned boolean,
 complete_gtm_opportunity_denominator_verified boolean,
 historical_status_as_of_window_end_verified boolean,
 settled_cash_independently_verified boolean,
 eligible_for_revenue_model_calibration boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=''
AS $reader$
DECLARE
 v_tenant uuid;
 v_total bigint;
 v_terminal bigint;
 v_rejected bigint;
 v_cancelled bigint;
 v_other bigint;
 v_unbound bigint;
 v_distinct bigint;
BEGIN
 IF session_user <> 'empire_predictive_cash_candidate_login' THEN
   RAISE EXCEPTION 'V417_DEDICATED_RESTRICTED_LOGIN_REQUIRED';
 END IF;
 v_tenant := public.empire_current_tenant_id();
 IF p_tenant IS NULL OR v_tenant IS NULL OR p_tenant<>v_tenant THEN
   RAISE EXCEPTION 'V417_SESSION_BOUND_TENANT_REQUIRED';
 END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_start>=p_end
    OR p_end>pg_catalog.statement_timestamp()
    OR p_end-p_start>interval '31 days'
    OR p_start<pg_catalog.statement_timestamp()-interval '5 years'
 THEN RAISE EXCEPTION 'V417_BOUNDED_HISTORICAL_WINDOW_REQUIRED'; END IF;
 -- All orders attributable through EXISTING buyers.org_id in [start,end).
 -- This does NOT enumerate tenant-unowned GTM opportunities or market leads.
 SELECT
   count(*),
   count(*) FILTER (WHERE o.state IN ('settled','outcome_captured')),
   count(*) FILTER (WHERE o.state='rejected'),
   count(*) FILTER (WHERE o.state='cancelled'),
   count(*) FILTER (WHERE o.opportunity_id IS NULL),
   count(DISTINCT o.opportunity_id)
 INTO v_total,v_terminal,v_rejected,v_cancelled,v_unbound,v_distinct
 FROM public.fulfilment_orders o
 JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
 WHERE o.created_at>=p_start AND o.created_at<p_end;
 IF v_total>5000 THEN
    RAISE EXCEPTION 'V417_WINDOW_EXCEEDS_5000_ORDERS_FAIL_CLOSED';
 END IF;
 v_other:=v_total-v_terminal-v_rejected-v_cancelled;
 selected_order_count:=v_total;
 current_state_settled_or_outcome_captured:=v_terminal;
 current_state_rejected:=v_rejected;
 current_state_cancelled:=v_cancelled;
 current_state_other_or_open:=v_other;
 selected_orders_without_opportunity_id:=v_unbound;
 distinct_order_linked_opportunity_ids:=v_distinct;
 multiple_orders_per_opportunity:=(v_total-v_unbound)>v_distinct;
 complete_buyer_owned_order_window_scanned:=true;
 complete_gtm_opportunity_denominator_verified:=false;
 historical_status_as_of_window_end_verified:=false;
 settled_cash_independently_verified:=false;
 eligible_for_revenue_model_calibration:=false;
 RETURN NEXT;
END;
$reader$;

REVOKE ALL ON FUNCTION
 public.read_predictive_revenue_tenant_order_cohort_v1(uuid,timestamptz,timestamptz)
 FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
 public.read_predictive_revenue_tenant_order_cohort_v1(uuid,timestamptz,timestamptz)
 TO empire_predictive_cash_candidate_reader;
COMMENT ON FUNCTION
 public.read_predictive_revenue_tenant_order_cohort_v1(uuid,timestamptz,timestamptz)
IS 'HELD: full buyer-owned order denominator in bounded window at present-day states; GTM opportunity denominator, as-of historical status, actual cash and forecast calibration NOT verified.';
COMMIT;
