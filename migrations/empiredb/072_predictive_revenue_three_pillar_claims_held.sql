-- EmpireDB 072: V4.20 three-pillar reconciliation CANDIDATES, HELD ONLY.
-- DO NOT apply to production without explicit DBA/Security/Finance approval.
-- No new canonical tenant, GTM, order, payment, reconciliation authority.
BEGIN;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='10s';
DO $preflight$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v415_fixture') THEN
  RAISE EXCEPTION 'V420_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='empiredb_migrator'
  AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='empire_predictive_cash_candidate_reader'
  AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'V420_OWNER_AND_READER_ROLES_REQUIRED'; END IF;
 IF pg_catalog.to_regprocedure(
  'public.read_predictive_revenue_source_lineage_held_v1(uuid,timestamptz,timestamptz)'
 ) IS NULL OR pg_catalog.to_regclass('public.empire_predictive_opportunity_custody_v418') IS NULL
 OR pg_catalog.to_regclass('public.fulfilment_orders') IS NULL
 OR pg_catalog.to_regclass('public.buyers') IS NULL
 OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
 THEN RAISE EXCEPTION 'V420_ORIGINAL_EVIDENCE_CHAIN_REQUIRED'; END IF;
 IF pg_catalog.to_regclass('public.empire_predictive_source_authorization_claims_v420') IS NOT NULL
 OR pg_catalog.to_regclass('public.empire_predictive_source_revocation_claims_v420') IS NOT NULL
 OR pg_catalog.to_regclass('public.empire_predictive_event_coverage_claims_v420') IS NOT NULL
 OR pg_catalog.to_regclass('public.empire_predictive_financial_match_claims_v420') IS NOT NULL
 OR pg_catalog.to_regprocedure(
  'public.read_predictive_revenue_three_pillar_held_v1(uuid,text,timestamptz,timestamptz)'
 ) IS NOT NULL THEN RAISE EXCEPTION 'V420_EXISTING_CHAIN_RECONCILE'; END IF;
END;
$preflight$;
SET LOCAL ROLE empiredb_migrator;

-- Source licence CLAIM is NOT a verified legal right. One append-only record
-- anchored to the existing tenant-owned custody source digest + channel.
CREATE TABLE public.empire_predictive_source_authorization_claims_v420 (
 tenant_id uuid NOT NULL,
 source_evidence_digest text NOT NULL CHECK(source_evidence_digest ~ '^[a-f0-9]{64}$'),
 channel_name text NOT NULL CHECK(channel_name ~ '^[a-z0-9_]{2,48}$'),
 license_document_digest text NOT NULL CHECK(license_document_digest ~ '^[a-f0-9]{64}$'),
 publisher_identifier_digest text NOT NULL CHECK(publisher_identifier_digest ~ '^[a-f0-9]{64}$'),
 declared_consent_framework text NOT NULL CHECK(
  declared_consent_framework IN ('TCPA','GDPR','CASL','DIRECT_BUY','NOT_APPLICABLE')),
 consent_artifact_digest text CHECK(consent_artifact_digest IS NULL OR consent_artifact_digest ~ '^[a-f0-9]{64}$'),
 publisher_network_scope_digest text CHECK(publisher_network_scope_digest IS NULL OR publisher_network_scope_digest ~ '^[a-f0-9]{64}$'),
 claimed_license_state text NOT NULL CHECK(
  claimed_license_state IN ('PENDING','CLAIMED_ACTIVE','EXPIRED','REVOKED')),
 declared_effective_at timestamptz NOT NULL,
 declared_expires_at timestamptz NOT NULL,
 claim_observed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY(tenant_id,source_evidence_digest,channel_name),
 CHECK(declared_expires_at>declared_effective_at),
 CHECK(declared_consent_framework NOT IN ('TCPA','GDPR','CASL')
   OR consent_artifact_digest IS NOT NULL)
);
-- Append-only revocation supersedes even a still-unexpired CLAIMED_ACTIVE document.
CREATE TABLE public.empire_predictive_source_revocation_claims_v420 (
 tenant_id uuid NOT NULL,
 source_evidence_digest text NOT NULL,
 channel_name text NOT NULL,
 revocation_evidence_digest text NOT NULL CHECK(revocation_evidence_digest ~ '^[a-f0-9]{64}$'),
 claimed_revoked_at timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY(tenant_id,source_evidence_digest,channel_name),
 FOREIGN KEY(tenant_id,source_evidence_digest,channel_name)
 REFERENCES public.empire_predictive_source_authorization_claims_v420
 (tenant_id,source_evidence_digest,channel_name) ON DELETE RESTRICT
);
CREATE TABLE public.empire_predictive_event_coverage_claims_v420 (
 opportunity_id uuid PRIMARY KEY
  REFERENCES public.empire_predictive_opportunity_custody_v418(opportunity_id)
  ON DELETE RESTRICT,
 tenant_id uuid NOT NULL,
 source_evidence_digest text NOT NULL,
 channel_name text NOT NULL,
 raw_event_digest text NOT NULL CHECK(raw_event_digest ~ '^[a-f0-9]{64}$'),
 event_method text NOT NULL CHECK(
  event_method IN ('CARRIER_CDR','SERVER_WEB_TAG','FORM_RECEIPT','CRM_MANUAL','OTHER')),
 event_occurred_at timestamptz NOT NULL,
 claimed_source_record_digest text NOT NULL CHECK(claimed_source_record_digest ~ '^[a-f0-9]{64}$'),
 claim_observed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 FOREIGN KEY(tenant_id,source_evidence_digest,channel_name)
  REFERENCES public.empire_predictive_source_authorization_claims_v420
  (tenant_id,source_evidence_digest,channel_name) ON DELETE RESTRICT
);
-- Paired hashes are *claims*, not independently checked clearing receipts.
CREATE TABLE public.empire_predictive_financial_match_claims_v420 (
 order_id uuid PRIMARY KEY REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL,
 buyer_remittance_digest text NOT NULL CHECK(buyer_remittance_digest ~ '^[a-f0-9]{64}$'),
 clearing_receipt_digest text NOT NULL CHECK(clearing_receipt_digest ~ '^[a-f0-9]{64}$'),
 gross_claim_minor bigint NOT NULL CHECK(gross_claim_minor BETWEEN 1 AND 100000000000),
 cleared_claim_minor bigint NOT NULL CHECK(cleared_claim_minor BETWEEN 0 AND 100000000000),
 declared_currency text NOT NULL CHECK(declared_currency IN ('GBP','USD','EUR')),
 declared_cleared_at timestamptz NOT NULL,
 claim_observed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);
CREATE INDEX v420_source_claims_tenant_channel_idx ON public.empire_predictive_source_authorization_claims_v420(tenant_id,channel_name);
CREATE INDEX v420_coverage_claims_tenant_channel_idx ON public.empire_predictive_event_coverage_claims_v420(tenant_id,channel_name);
CREATE INDEX v420_financial_claims_tenant_idx ON public.empire_predictive_financial_match_claims_v420(tenant_id);
REVOKE ALL ON public.empire_predictive_source_authorization_claims_v420
 FROM PUBLIC,empire_predictive_cash_candidate_reader;
REVOKE ALL ON public.empire_predictive_source_revocation_claims_v420
 FROM PUBLIC,empire_predictive_cash_candidate_reader;
REVOKE ALL ON public.empire_predictive_event_coverage_claims_v420
 FROM PUBLIC,empire_predictive_cash_candidate_reader;
REVOKE ALL ON public.empire_predictive_financial_match_claims_v420
 FROM PUBLIC,empire_predictive_cash_candidate_reader;
ALTER TABLE public.empire_predictive_source_authorization_claims_v420 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_source_authorization_claims_v420 FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_source_revocation_claims_v420 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_source_revocation_claims_v420 FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_event_coverage_claims_v420 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_event_coverage_claims_v420 FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_financial_match_claims_v420 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_financial_match_claims_v420 FORCE ROW LEVEL SECURITY;
CREATE POLICY v420_owner_source ON public.empire_predictive_source_authorization_claims_v420
 TO empiredb_migrator USING (true) WITH CHECK(true);
CREATE POLICY v420_owner_revocation ON public.empire_predictive_source_revocation_claims_v420
 TO empiredb_migrator USING (true) WITH CHECK(true);
CREATE POLICY v420_owner_event ON public.empire_predictive_event_coverage_claims_v420
 TO empiredb_migrator USING (true) WITH CHECK(true);
CREATE POLICY v420_owner_finance ON public.empire_predictive_financial_match_claims_v420
 TO empiredb_migrator USING (true) WITH CHECK(true);
CREATE FUNCTION public.deny_predictive_v420_claim_mutation() RETURNS trigger
 LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $immutable$
BEGIN RAISE EXCEPTION 'V420_APPEND_ONLY_CLAIM_HISTORY'; END;
$immutable$;
CREATE TRIGGER v420_source_immutable BEFORE UPDATE OR DELETE
 ON public.empire_predictive_source_authorization_claims_v420
 FOR EACH ROW EXECUTE FUNCTION public.deny_predictive_v420_claim_mutation();
CREATE TRIGGER v420_revocation_immutable BEFORE UPDATE OR DELETE
 ON public.empire_predictive_source_revocation_claims_v420
 FOR EACH ROW EXECUTE FUNCTION public.deny_predictive_v420_claim_mutation();
CREATE TRIGGER v420_event_immutable BEFORE UPDATE OR DELETE
 ON public.empire_predictive_event_coverage_claims_v420
 FOR EACH ROW EXECUTE FUNCTION public.deny_predictive_v420_claim_mutation();
CREATE TRIGGER v420_finance_immutable BEFORE UPDATE OR DELETE
 ON public.empire_predictive_financial_match_claims_v420
 FOR EACH ROW EXECUTE FUNCTION public.deny_predictive_v420_claim_mutation();
CREATE FUNCTION public.read_predictive_revenue_three_pillar_held_v1(
 p_tenant uuid,p_channel text,p_start timestamptz,p_end timestamptz
)
RETURNS TABLE (
 opportunity_count bigint,
 source_document_claim_count bigint,
 claimed_active_source_count bigint,
 event_evidence_claim_count bigint,
 matched_source_and_event_claim_count bigint,
 original_accepted_order_opportunity_count bigint,
 paired_clearing_claim_count bigint,
 conflicting_clearing_claim_count bigint,
 claimed_acquisition_cost_minor numeric,
 claimed_coverage_basis_points integer,
 source_licensing_independently_verified boolean,
 upstream_event_census_independently_verified boolean,
 independent_settlement_verified boolean,
 fully_audited_authorized boolean,
 verified_cvr_ecac_authorized boolean,
 verified_30_60_90_cash_authorized boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $audit$
DECLARE v_tenant uuid; v_total bigint;
BEGIN
 IF session_user<>'empire_predictive_cash_candidate_login' THEN
  RAISE EXCEPTION 'V420_RESTRICTED_ORIGINAL_LOGIN_REQUIRED';
 END IF;
 v_tenant:=public.empire_current_tenant_id();
 IF p_tenant IS NULL OR v_tenant IS NULL OR p_tenant<>v_tenant THEN
  RAISE EXCEPTION 'V420_SIGNED_SESSION_TENANT_REQUIRED';
 END IF;
 IF p_channel IS NULL OR p_channel !~ '^[a-z0-9_]{2,48}$' THEN
  RAISE EXCEPTION 'V420_EXACT_CHANNEL_REQUIRED';
 END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_start>=p_end
 OR p_end>pg_catalog.statement_timestamp()
 OR p_end-p_start>interval '31 days'
 OR p_start<pg_catalog.statement_timestamp()-interval '5 years' THEN
  RAISE EXCEPTION 'V420_BOUNDED_AUDIT_WINDOW_REQUIRED';
 END IF;
 SELECT count(*) INTO v_total
 FROM public.empire_predictive_opportunity_custody_v418 c
 JOIN public.gtm_opportunities g ON g.id=c.opportunity_id
 WHERE c.tenant_id=v_tenant
  AND c.first_seen_at>=p_start AND c.first_seen_at<p_end
  AND pg_catalog.lower(pg_catalog.btrim(g.source_channel))=p_channel;
 IF v_total>5000 THEN RAISE EXCEPTION 'V420_CHANNEL_COHORT_TOO_LARGE'; END IF;

 RETURN QUERY
 WITH cohort AS (
  SELECT c.opportunity_id,c.source_evidence_digest,c.acquisition_cost_minor,
         c.currency_code,c.first_seen_at
  FROM public.empire_predictive_opportunity_custody_v418 c
  JOIN public.gtm_opportunities g ON g.id=c.opportunity_id
  WHERE c.tenant_id=v_tenant
   AND c.first_seen_at>=p_start AND c.first_seen_at<p_end
   AND pg_catalog.lower(pg_catalog.btrim(g.source_channel))=p_channel
 ), proof AS (
  SELECT c.*,
   (a.tenant_id IS NOT NULL) AS has_authorization_claim,
   (a.claimed_license_state='CLAIMED_ACTIVE'
     AND NOT EXISTS(
      SELECT 1 FROM public.empire_predictive_source_revocation_claims_v420 r
      WHERE r.tenant_id=v_tenant AND r.channel_name=p_channel
       AND r.source_evidence_digest=c.source_evidence_digest
       AND r.recorded_at<=pg_catalog.statement_timestamp())
     AND a.declared_effective_at<=c.first_seen_at
     AND a.declared_expires_at>c.first_seen_at
     AND a.claim_observed_at<=pg_catalog.statement_timestamp())
       IS TRUE AS active_authorization_claim,
   (e.opportunity_id IS NOT NULL) AS has_event_claim,
   (e.opportunity_id IS NOT NULL AND
     e.source_evidence_digest=c.source_evidence_digest
     AND e.tenant_id=v_tenant AND e.channel_name=p_channel
     AND e.event_occurred_at<=pg_catalog.statement_timestamp()
     AND e.event_occurred_at>=c.first_seen_at-interval '1 day')
       IS TRUE AS event_consistent,
   EXISTS(
    SELECT 1 FROM public.fulfilment_orders o
    JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
    WHERE o.opportunity_id=c.opportunity_id
      AND o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')
   ) AS has_accepted_order,
   EXISTS(
    SELECT 1 FROM public.fulfilment_orders o
    JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
    JOIN public.empire_predictive_financial_match_claims_v420 f
     ON f.order_id=o.id AND f.tenant_id=v_tenant
    WHERE o.opportunity_id=c.opportunity_id
     AND o.state IN ('accepted','delivered','confirmed','invoiced','paid','settled','outcome_captured')
     AND o.price_cents BETWEEN 1 AND 100000000000
     AND f.declared_currency=c.currency_code
     AND f.gross_claim_minor=o.price_cents
     AND f.cleared_claim_minor=f.gross_claim_minor
     AND f.buyer_remittance_digest<>f.clearing_receipt_digest
     AND f.declared_cleared_at<=pg_catalog.statement_timestamp()
   ) AS has_paired_claim,
   EXISTS(
    SELECT 1 FROM public.fulfilment_orders o
    JOIN public.buyers b ON b.id=o.buyer_id AND b.org_id=v_tenant
    JOIN public.empire_predictive_financial_match_claims_v420 f
     ON f.order_id=o.id AND f.tenant_id=v_tenant
    WHERE o.opportunity_id=c.opportunity_id
     AND (f.declared_currency<>c.currency_code
       OR f.gross_claim_minor<>o.price_cents
       OR f.cleared_claim_minor<>f.gross_claim_minor
       OR f.buyer_remittance_digest=f.clearing_receipt_digest)
   ) AS conflicting_claim
  FROM cohort c
  LEFT JOIN public.empire_predictive_source_authorization_claims_v420 a
   ON a.tenant_id=v_tenant AND a.channel_name=p_channel
     AND a.source_evidence_digest=c.source_evidence_digest
  LEFT JOIN public.empire_predictive_event_coverage_claims_v420 e
   ON e.opportunity_id=c.opportunity_id AND e.tenant_id=v_tenant
     AND e.channel_name=p_channel
 )
 SELECT v_total,
   count(*) FILTER(WHERE has_authorization_claim),
   count(*) FILTER(WHERE active_authorization_claim),
   count(*) FILTER(WHERE has_event_claim),
   count(*) FILTER(WHERE active_authorization_claim AND event_consistent),
   count(*) FILTER(WHERE has_accepted_order),
   count(*) FILTER(WHERE has_paired_claim),
   count(*) FILTER(WHERE conflicting_claim),
   COALESCE(sum(acquisition_cost_minor),0)::numeric,
   CASE WHEN v_total=0 THEN NULL ELSE
    pg_catalog.round(
     (count(*) FILTER(WHERE active_authorization_claim AND event_consistent))::numeric
     *10000/v_total)::integer END,
   false,false,false,false,false,false
 FROM proof;
END;
$audit$;
REVOKE ALL ON FUNCTION public.read_predictive_revenue_three_pillar_held_v1(
 uuid,text,timestamptz,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.read_predictive_revenue_three_pillar_held_v1(
 uuid,text,timestamptz,timestamptz) TO empire_predictive_cash_candidate_reader;
COMMENT ON FUNCTION public.read_predictive_revenue_three_pillar_held_v1(
 uuid,text,timestamptz,timestamptz) IS
 'HELD: source/coverage/settlement claims only. No independently authorised licence, complete upstream event census, real bank settlement, audited CVR/eCAC or live forecasts.';
COMMIT;
