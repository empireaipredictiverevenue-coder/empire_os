-- EmpireDB 073: V4.21 HELD six-stage lifecycle and refund CLAIMS.
-- PREPARED ONLY, NEVER production-applied in this release.
-- Earlier migrations 066-072 remain held; no finance/retraining gates opened.
BEGIN;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='10s';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v415_fixture') THEN
  RAISE EXCEPTION 'V421_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='empiredb_migrator'
   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='empire_predictive_cash_candidate_reader'
   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'V421_ORIGINAL_RESTRICTED_ROLES_REQUIRED'; END IF;
 IF pg_catalog.to_regprocedure(
 'public.read_predictive_revenue_three_pillar_held_v1(uuid,text,timestamptz,timestamptz)'
 ) IS NULL OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
 OR pg_catalog.to_regclass('public.empire_predictive_financial_match_claims_v420') IS NULL
 OR pg_catalog.to_regclass('public.empire_predictive_event_coverage_claims_v420') IS NULL
 OR pg_catalog.to_regclass('public.empire_predictive_opportunity_custody_v418') IS NULL
 OR pg_catalog.to_regclass('public.gtm_opportunities') IS NULL
 THEN RAISE EXCEPTION 'V421_072_PROOF_CHAIN_REQUIRED'; END IF;
 IF pg_catalog.to_regclass('public.empire_predictive_refund_clawback_claims_v421') IS NOT NULL
 OR pg_catalog.to_regprocedure(
 'public.read_predictive_revenue_lifecycle_held_v421(uuid,text,timestamptz,timestamptz)'
 ) IS NOT NULL THEN RAISE EXCEPTION 'V421_EXISTING_CLAIMS_RECONCILE'; END IF;
END;
$guard$;
SET LOCAL ROLE empiredb_migrator;
CREATE TABLE public.empire_predictive_refund_clawback_claims_v421 (
 order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL,
 reversal_digest text NOT NULL CHECK(reversal_digest ~ '^[a-f0-9]{64}$'),
 claim_kind text NOT NULL CHECK(claim_kind IN ('REFUND','CLAWBACK','DISPUTE')),
 currency_code text NOT NULL CHECK(currency_code IN ('GBP','USD','EUR')),
 amount_minor bigint NOT NULL CHECK(amount_minor BETWEEN 1 AND 100000000000),
 claimed_event_at timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY(order_id,reversal_digest)
);
CREATE INDEX v421_refund_claims_tenant_idx
 ON public.empire_predictive_refund_clawback_claims_v421(tenant_id,order_id);
REVOKE ALL ON public.empire_predictive_refund_clawback_claims_v421
 FROM PUBLIC,empire_predictive_cash_candidate_reader;
ALTER TABLE public.empire_predictive_refund_clawback_claims_v421 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_refund_clawback_claims_v421 FORCE ROW LEVEL SECURITY;
CREATE POLICY v421_owner_claims ON public.empire_predictive_refund_clawback_claims_v421
 TO empiredb_migrator USING (true) WITH CHECK (true);
CREATE TRIGGER v421_append_only_refund_claim
 BEFORE UPDATE OR DELETE ON public.empire_predictive_refund_clawback_claims_v421
 FOR EACH ROW EXECUTE FUNCTION public.deny_predictive_v420_claim_mutation();

CREATE FUNCTION public.read_predictive_revenue_lifecycle_held_v421(
 p_tenant uuid,p_channel text,p_start timestamptz,p_end timestamptz
) RETURNS TABLE(
 opportunity_count bigint,
 claimed_authorized_inbound_count bigint,
 event_covered_opportunity_count bigint,
 accepted_order_opportunity_count bigint,
 paired_clearing_opportunity_count bigint,
 unmatched_or_discrepant_finance_opportunity_count bigint,
 refund_or_clawback_claimed_order_count bigint,
 refund_or_clawback_claim_count bigint,
 claimed_gross_clearing_minor numeric,
 claimed_refund_clawback_minor numeric,
 claimed_acquisition_cost_minor numeric,
 illustrative_net_after_claims_minor numeric,
 complete_upstream_census_verified boolean,
 independently_verified_source_rights boolean,
 bank_settlement_finality_verified boolean,
 refunds_and_chargebacks_complete_verified boolean,
 realized_net_cash_verified boolean,
 forecast_retraining_authorized boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $audit$
DECLARE v_tenant uuid; v_n bigint;
BEGIN
 IF session_user<>'empire_predictive_cash_candidate_login' THEN
  RAISE EXCEPTION 'V421_RESTRICTED_ORIGINAL_LOGIN_REQUIRED';
 END IF;
 v_tenant:=public.empire_current_tenant_id();
 IF p_tenant IS NULL OR v_tenant IS NULL OR p_tenant<>v_tenant THEN
  RAISE EXCEPTION 'V421_SESSION_TENANT_DENIED';
 END IF;
 IF p_channel IS NULL OR p_channel !~ '^[a-z0-9_]{2,48}$' THEN
  RAISE EXCEPTION 'V421_EXACT_SOURCE_CHANNEL_REQUIRED';
 END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_start>=p_end
  OR p_end>pg_catalog.statement_timestamp()
  OR p_end-p_start>interval '31 days'
  OR p_start<pg_catalog.statement_timestamp()-interval '5 years'
 THEN RAISE EXCEPTION 'V421_BOUNDED_COHORT_REQUIRED'; END IF;
 SELECT count(*) INTO v_n
 FROM public.empire_predictive_opportunity_custody_v418 c
 JOIN public.gtm_opportunities g ON g.id=c.opportunity_id
 WHERE c.tenant_id=v_tenant
 AND c.first_seen_at>=p_start AND c.first_seen_at<p_end
 AND pg_catalog.lower(pg_catalog.btrim(g.source_channel))=p_channel;
 IF v_n>5000 THEN RAISE EXCEPTION 'V421_COHORT_LIMIT_EXCEEDED'; END IF;
 RETURN QUERY
 WITH cohort AS (
 SELECT c.opportunity_id,c.source_evidence_digest,c.first_seen_at,
        c.currency_code,c.acquisition_cost_minor
 FROM public.empire_predictive_opportunity_custody_v418 c
 JOIN public.gtm_opportunities g ON g.id=c.opportunity_id
 WHERE c.tenant_id=v_tenant
 AND c.first_seen_at>=p_start AND c.first_seen_at<p_end
 AND pg_catalog.lower(pg_catalog.btrim(g.source_channel))=p_channel
 ), eligible AS (
 SELECT c.*,
  (a.tenant_id IS NOT NULL AND a.claimed_license_state='CLAIMED_ACTIVE'
   AND a.declared_effective_at<=c.first_seen_at
   AND a.declared_expires_at>c.first_seen_at
   AND NOT EXISTS(
    SELECT 1 FROM public.empire_predictive_source_revocation_claims_v420 r
    WHERE r.tenant_id=v_tenant AND r.channel_name=p_channel
    AND r.source_evidence_digest=c.source_evidence_digest)
  ) AS source_claim,
  (e.opportunity_id IS NOT NULL AND e.source_evidence_digest=c.source_evidence_digest
    AND e.channel_name=p_channel AND e.tenant_id=v_tenant
    AND e.event_occurred_at<=pg_catalog.statement_timestamp()
    AND e.event_occurred_at>=c.first_seen_at-interval '1 day') AS event_claim
 FROM cohort c
 LEFT JOIN public.empire_predictive_source_authorization_claims_v420 a
 ON a.tenant_id=v_tenant AND a.channel_name=p_channel
 AND a.source_evidence_digest=c.source_evidence_digest
 LEFT JOIN public.empire_predictive_event_coverage_claims_v420 e
 ON e.opportunity_id=c.opportunity_id AND e.tenant_id=v_tenant
 AND e.channel_name=p_channel
 ), orders AS (
 SELECT e.*,
  (SELECT count(*) FROM public.fulfilment_orders o
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
   WHERE o.opportunity_id=e.opportunity_id
   AND o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')
  ) AS accepted_orders,
  (SELECT count(*) FROM public.fulfilment_orders o
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
   JOIN public.empire_predictive_financial_match_claims_v420 f
    ON f.order_id=o.id AND f.tenant_id=v_tenant
   WHERE o.opportunity_id=e.opportunity_id
   AND o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')
   AND o.price_cents>0
   AND f.gross_claim_minor=o.price_cents
   AND f.cleared_claim_minor=f.gross_claim_minor
   AND f.declared_currency=e.currency_code
   AND f.buyer_remittance_digest<>f.clearing_receipt_digest
   AND f.declared_cleared_at<=pg_catalog.statement_timestamp()
  ) AS paired_orders,
  (SELECT count(*) FROM public.fulfilment_orders o
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
   JOIN public.empire_predictive_financial_match_claims_v420 f
    ON f.order_id=o.id AND f.tenant_id=v_tenant
   WHERE o.opportunity_id=e.opportunity_id
   AND (f.gross_claim_minor<>o.price_cents
    OR f.cleared_claim_minor<>f.gross_claim_minor
    OR f.declared_currency<>e.currency_code
    OR f.buyer_remittance_digest=f.clearing_receipt_digest)
  ) AS discrepancies,
  (SELECT COALESCE(sum(f.cleared_claim_minor),0)::numeric
   FROM public.fulfilment_orders o
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
   JOIN public.empire_predictive_financial_match_claims_v420 f
    ON f.order_id=o.id AND f.tenant_id=v_tenant
   WHERE o.opportunity_id=e.opportunity_id
   AND o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')
   AND f.gross_claim_minor=o.price_cents
   AND f.cleared_claim_minor=f.gross_claim_minor
   AND f.declared_currency=e.currency_code
   AND f.buyer_remittance_digest<>f.clearing_receipt_digest
  ) AS gross_claim_minor,
  (SELECT count(*) FROM public.empire_predictive_refund_clawback_claims_v421 r
   JOIN public.fulfilment_orders o ON o.id=r.order_id
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
   WHERE o.opportunity_id=e.opportunity_id AND r.tenant_id=v_tenant
   AND r.currency_code=e.currency_code) AS refund_claims,
  (SELECT count(DISTINCT r.order_id) FROM public.empire_predictive_refund_clawback_claims_v421 r
   JOIN public.fulfilment_orders o ON o.id=r.order_id
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
   WHERE o.opportunity_id=e.opportunity_id AND r.tenant_id=v_tenant
   AND r.currency_code=e.currency_code) AS refunded_orders,
  (SELECT COALESCE(sum(r.amount_minor),0)::numeric
   FROM public.empire_predictive_refund_clawback_claims_v421 r
   JOIN public.fulfilment_orders o ON o.id=r.order_id
   JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
   WHERE o.opportunity_id=e.opportunity_id AND r.tenant_id=v_tenant
   AND r.currency_code=e.currency_code) AS refund_amount_minor
 FROM eligible e
 )
 SELECT v_n,
   count(*) FILTER(WHERE source_claim),
   count(*) FILTER(WHERE source_claim AND event_claim),
   count(*) FILTER(WHERE accepted_orders>0),
   count(*) FILTER(WHERE paired_orders>0),
   count(*) FILTER(WHERE discrepancies>0),
   COALESCE(sum(refunded_orders),0)::bigint,
   COALESCE(sum(refund_claims),0)::bigint,
   COALESCE(sum(gross_claim_minor),0)::numeric,
   COALESCE(sum(refund_amount_minor),0)::numeric,
   COALESCE(sum(acquisition_cost_minor),0)::numeric,
   (COALESCE(sum(gross_claim_minor),0)-COALESCE(sum(refund_amount_minor),0)
     -COALESCE(sum(acquisition_cost_minor),0))::numeric,
   false,false,false,false,false,false
 FROM orders;
END;
$audit$;
REVOKE ALL ON FUNCTION public.read_predictive_revenue_lifecycle_held_v421(
 uuid,text,timestamptz,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.read_predictive_revenue_lifecycle_held_v421(
 uuid,text,timestamptz,timestamptz)
 TO empire_predictive_cash_candidate_reader;
COMMENT ON FUNCTION public.read_predictive_revenue_lifecycle_held_v421(
 uuid,text,timestamptz,timestamptz)
IS 'Research-only claimed six-stage lifecycle. No real cash, authenticated refund finality, source intake completeness or live calibration authority.';
COMMIT;
