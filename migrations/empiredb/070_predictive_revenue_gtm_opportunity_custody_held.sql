-- EmpireDB 070, PREPARED/HELD ONLY. Do not apply to production.
-- Complete tenant-CLAIMED GTM opportunity denominator, never a duplicate
-- opportunity/order source-of-truth. No broad grants, login or activation.
BEGIN;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='10s';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v415_fixture') THEN
  RAISE EXCEPTION 'V418_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empiredb_migrator'
  AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
  OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE
  rolname='empire_predictive_cash_candidate_reader'
  AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'V418_ORIGINAL_ROLES_REQUIRED'; END IF;
 IF pg_catalog.to_regclass('public.gtm_opportunities') IS NULL
  OR pg_catalog.to_regclass('public.fulfilment_orders') IS NULL
  OR pg_catalog.to_regclass('public.buyers') IS NULL
  OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
  OR pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_tenant_order_cohort_v1(uuid,timestamptz,timestamptz)') IS NULL
 THEN RAISE EXCEPTION 'V418_EXISTING_EMPIREDB_CONTRACT_REQUIRED'; END IF;
 IF pg_catalog.to_regclass('public.empire_predictive_opportunity_custody_v418') IS NOT NULL
  OR pg_catalog.to_regclass('public.empire_predictive_opportunity_states_v418') IS NOT NULL
 THEN RAISE EXCEPTION 'V418_CUSTODY_ALREADY_EXISTS_RECONCILE'; END IF;
END;
$guard$;
SET LOCAL ROLE empiredb_migrator;
CREATE TABLE public.empire_predictive_opportunity_custody_v418 (
 opportunity_id uuid PRIMARY KEY REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL,
 source_evidence_digest text NOT NULL CHECK(source_evidence_digest ~ '^[a-f0-9]{64}$'),
 owner_evidence_digest text NOT NULL CHECK(owner_evidence_digest ~ '^[a-f0-9]{64}$'),
 first_seen_at timestamptz NOT NULL,
 acquisition_cost_minor bigint NOT NULL DEFAULT 0 CHECK(acquisition_cost_minor BETWEEN 0 AND 100000000000),
 currency_code text NOT NULL CHECK(currency_code IN ('GBP','USD','EUR')),
 custody_claim_recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);
CREATE TABLE public.empire_predictive_opportunity_states_v418 (
 opportunity_id uuid NOT NULL REFERENCES public.empire_predictive_opportunity_custody_v418(opportunity_id) ON DELETE RESTRICT,
 state_seq integer NOT NULL CHECK(state_seq BETWEEN 1 AND 10000),
 state_name text NOT NULL CHECK(state_name IN ('OPEN','DISQUALIFIED','DEAD','CONVERTED')),
 state_at timestamptz NOT NULL,
 state_evidence_digest text NOT NULL CHECK(state_evidence_digest ~ '^[a-f0-9]{64}$'),
 PRIMARY KEY (opportunity_id,state_seq),
 UNIQUE (opportunity_id,state_at)
);
CREATE INDEX empire_predictive_opportunity_custody_v418_tenant_window_idx
 ON public.empire_predictive_opportunity_custody_v418(tenant_id,first_seen_at,opportunity_id);
CREATE INDEX empire_predictive_opportunity_states_v418_latest_idx
 ON public.empire_predictive_opportunity_states_v418(opportunity_id,state_seq DESC);
REVOKE ALL ON public.empire_predictive_opportunity_custody_v418 FROM PUBLIC;
REVOKE ALL ON public.empire_predictive_opportunity_states_v418 FROM PUBLIC;
ALTER TABLE public.empire_predictive_opportunity_custody_v418 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_opportunity_custody_v418 FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_opportunity_states_v418 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_opportunity_states_v418 FORCE ROW LEVEL SECURITY;
CREATE POLICY v418_owner_custody_only ON public.empire_predictive_opportunity_custody_v418
 TO empiredb_migrator USING (true) WITH CHECK (true);
CREATE POLICY v418_owner_states_only ON public.empire_predictive_opportunity_states_v418
 TO empiredb_migrator USING (true) WITH CHECK (true);

CREATE FUNCTION public.check_predictive_gtm_transition_v418()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $transition$
DECLARE v_previous text; v_seq integer; v_time timestamptz;
DECLARE v_start timestamptz; v_tenant uuid;
BEGIN
 SELECT c.first_seen_at,c.tenant_id INTO v_start,v_tenant
 FROM public.empire_predictive_opportunity_custody_v418 c
 WHERE c.opportunity_id=NEW.opportunity_id FOR UPDATE;
 IF v_start IS NULL THEN RAISE EXCEPTION 'V418_CUSTODY_REQUIRED'; END IF;
 IF NEW.state_at < v_start OR NEW.state_at>pg_catalog.statement_timestamp() THEN
   RAISE EXCEPTION 'V418_CAUSAL_EVENT_TIME_REQUIRED';
 END IF;
 SELECT e.state_name,e.state_seq,e.state_at INTO v_previous,v_seq,v_time
 FROM public.empire_predictive_opportunity_states_v418 e
 WHERE e.opportunity_id=NEW.opportunity_id ORDER BY e.state_seq DESC LIMIT 1;
 IF v_previous IS NULL THEN
   IF NEW.state_seq<>1 OR NEW.state_name<>'OPEN' THEN
     RAISE EXCEPTION 'V418_FIRST_STATE_MUST_BE_OPEN';
   END IF;
 ELSE
   IF v_previous<>'OPEN' OR NEW.state_seq<>v_seq+1
     OR NEW.state_name NOT IN ('DISQUALIFIED','DEAD','CONVERTED')
     OR NEW.state_at<=v_time THEN
     RAISE EXCEPTION 'V418_INVALID_TERMINAL_TRANSITION';
   END IF;
 END IF;
 IF NEW.state_name='CONVERTED' AND NOT EXISTS (
  SELECT 1 FROM public.fulfilment_orders o
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
  WHERE o.opportunity_id=NEW.opportunity_id
    AND o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')
 ) THEN RAISE EXCEPTION 'V418_CROSS_TENANT_OR_MISSING_CONVERSION_ORDER'; END IF;
 RETURN NEW;
END;
$transition$;
CREATE TRIGGER v418_append_only_transition_check
BEFORE INSERT ON public.empire_predictive_opportunity_states_v418
FOR EACH ROW EXECUTE FUNCTION public.check_predictive_gtm_transition_v418();
CREATE FUNCTION public.deny_predictive_opportunity_mutation_v418()
RETURNS trigger LANGUAGE plpgsql AS $deny$
BEGIN
 RAISE EXCEPTION 'V418_APPEND_ONLY_CUSTODY_EVENTS';
END;
$deny$;
CREATE TRIGGER v418_custody_no_update_delete
BEFORE UPDATE OR DELETE ON public.empire_predictive_opportunity_custody_v418
FOR EACH ROW EXECUTE FUNCTION public.deny_predictive_opportunity_mutation_v418();
CREATE TRIGGER v418_states_no_update_delete
BEFORE UPDATE OR DELETE ON public.empire_predictive_opportunity_states_v418
FOR EACH ROW EXECUTE FUNCTION public.deny_predictive_opportunity_mutation_v418();

CREATE FUNCTION public.read_predictive_revenue_gtm_denominator_v418(
 p_tenant uuid,p_start timestamptz,p_end timestamptz
) RETURNS TABLE(
 custody_count bigint,open_count bigint,disqualified_count bigint,dead_count bigint,
 converted_claim_count bigint,converted_with_tenant_order_count bigint,
 missing_state_evidence_count bigint,unlinked_converted_count bigint,
 acquisition_cost_minor_sum numeric,mixed_currency_count bigint,cohort_currency_code text,
 opportunity_population_complete_verified boolean,customer_cvr_verified boolean,
 finance_cash_matched boolean,model_calibration_authorized boolean
) LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=''
AS $reader$
DECLARE v_tenant uuid; v_rows bigint;
BEGIN
 IF session_user<>'empire_predictive_cash_candidate_login' THEN
  RAISE EXCEPTION 'V418_ORIGINAL_CASH_READER_LOGIN_REQUIRED';
 END IF;
 v_tenant:=public.empire_current_tenant_id();
 IF v_tenant IS NULL OR p_tenant IS NULL OR p_tenant<>v_tenant THEN
  RAISE EXCEPTION 'V418_SESSION_TENANT_REQUIRED';
 END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_start>=p_end
   OR p_end>pg_catalog.statement_timestamp()
   OR p_end-p_start>interval '31 days'
   OR p_start<pg_catalog.statement_timestamp()-interval '5 years'
 THEN RAISE EXCEPTION 'V418_BOUNDED_WINDOW_REQUIRED'; END IF;
 SELECT count(*) INTO v_rows
 FROM public.empire_predictive_opportunity_custody_v418 c
 WHERE c.tenant_id=v_tenant AND c.first_seen_at>=p_start AND c.first_seen_at<p_end;
 IF v_rows>5000 THEN RAISE EXCEPTION 'V418_COHORT_TOO_LARGE_HELD'; END IF;
 RETURN QUERY
 WITH cohort AS (
   SELECT c.opportunity_id,c.acquisition_cost_minor,c.currency_code,s.state_name
   FROM public.empire_predictive_opportunity_custody_v418 c
   LEFT JOIN LATERAL(
     SELECT state_name FROM public.empire_predictive_opportunity_states_v418 se
     WHERE se.opportunity_id=c.opportunity_id AND se.state_at<=pg_catalog.statement_timestamp()
     ORDER BY se.state_seq DESC LIMIT 1
   ) s ON true
   WHERE c.tenant_id=v_tenant AND c.first_seen_at>=p_start AND c.first_seen_at<p_end
 ), outcome AS (
   SELECT cohort.*,
    EXISTS(
     SELECT 1 FROM public.fulfilment_orders o
      JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
     WHERE o.opportunity_id=cohort.opportunity_id AND
      o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')
    ) AS order_linked
   FROM cohort
 )
 SELECT count(*)::bigint,
  count(*) FILTER(WHERE state_name='OPEN')::bigint,
  count(*) FILTER(WHERE state_name='DISQUALIFIED')::bigint,
  count(*) FILTER(WHERE state_name='DEAD')::bigint,
  count(*) FILTER(WHERE state_name='CONVERTED')::bigint,
  count(*) FILTER(WHERE state_name='CONVERTED' AND order_linked)::bigint,
  count(*) FILTER(WHERE state_name IS NULL)::bigint,
  count(*) FILTER(WHERE state_name='CONVERTED' AND NOT order_linked)::bigint,
  COALESCE(sum(acquisition_cost_minor),0)::numeric,
  count(DISTINCT currency_code)::bigint,min(currency_code)::text,
  false,false,false,false
 FROM outcome;
END;
$reader$;
REVOKE ALL ON FUNCTION public.read_predictive_revenue_gtm_denominator_v418(uuid,timestamptz,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.read_predictive_revenue_gtm_denominator_v418(uuid,timestamptz,timestamptz)
 TO empire_predictive_cash_candidate_reader;
COMMENT ON FUNCTION public.read_predictive_revenue_gtm_denominator_v418(uuid,timestamptz,timestamptz)
IS 'HELD: claimed tenant opportunity custody; never full-population, verified CVR, finance settlement, or revenue forecast authority.';
COMMIT;
