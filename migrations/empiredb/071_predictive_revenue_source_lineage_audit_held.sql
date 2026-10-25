-- EmpireDB 071 V4.19: HELD/NO PRODUCTION APPLY.
-- No new source table, writer, data import, login, or tenant authority.
-- Single source metadata completeness audit: existing original GTM + 070.
BEGIN;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='10s';
DO $preflight$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v415_fixture') THEN
   RAISE EXCEPTION 'V419_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
   AND NOT rolbypassrls)
 OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_predictive_cash_candidate_reader'
   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'V419_ORIGINAL_SECURITY_ROLES_REQUIRED'; END IF;
 IF pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_gtm_denominator_v418(uuid,timestamptz,timestamptz)'
 ) IS NULL OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
 OR pg_catalog.to_regclass('public.gtm_opportunities') IS NULL
 OR pg_catalog.to_regclass('public.empire_predictive_opportunity_custody_v418') IS NULL
 THEN RAISE EXCEPTION 'V419_V418_AND_ORIGINAL_GTM_REQUIRED'; END IF;
 IF pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_source_lineage_held_v1(uuid,timestamptz,timestamptz)'
 ) IS NOT NULL THEN RAISE EXCEPTION 'V419_READER_EXISTS_RECONCILE'; END IF;
 IF NOT pg_catalog.has_table_privilege('empiredb_migrator',
   'public.gtm_opportunities','SELECT')
 OR NOT pg_catalog.has_table_privilege('empiredb_migrator',
   'public.empire_predictive_opportunity_custody_v418','SELECT')
 OR pg_catalog.has_table_privilege('empire_predictive_cash_candidate_reader',
   'public.gtm_opportunities','SELECT')
 OR pg_catalog.has_table_privilege('empire_predictive_cash_candidate_reader',
   'public.empire_predictive_opportunity_custody_v418','SELECT')
 THEN RAISE EXCEPTION 'V419_UNEXPECTED_SOURCE_READ_PRIVILEGES'; END IF;
END;
$preflight$;
SET LOCAL ROLE empiredb_migrator;
CREATE FUNCTION public.read_predictive_revenue_source_lineage_held_v1(
 p_tenant uuid,p_start timestamptz,p_end timestamptz
)
RETURNS TABLE(
 selected_custody_claim_count bigint,
 original_gtm_rows_matched bigint,
 empty_source_channel_count bigint,
 empty_niche_count bigint,
 empty_opportunity_type_count bigint,
 late_custody_claim_over_24h_count bigint,
 zero_cost_claim_count bigint,
 distinct_source_evidence_digests bigint,
 distinct_owner_evidence_digests bigint,
 original_niche_categories bigint,
 original_source_channel_categories bigint,
 original_type_categories bigint,
 complete_upstream_event_intake_verified boolean,
 tenant_owner_provenance_independently_verified boolean,
 independent_source_licence_verified boolean,
 acquisition_cost_invoice_verified boolean,
 automated_opportunity_ingestion_authorized boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=''
AS $reader$
DECLARE v_session_tenant uuid; v_count bigint;
BEGIN
 IF session_user<>'empire_predictive_cash_candidate_login' THEN
  RAISE EXCEPTION 'V419_RESTRICTED_SESSION_REQUIRED';
 END IF;
 v_session_tenant := public.empire_current_tenant_id();
 IF p_tenant IS NULL OR v_session_tenant IS NULL OR p_tenant<>v_session_tenant THEN
  RAISE EXCEPTION 'V419_SESSION_TENANT_DENIED';
 END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_start>=p_end
 OR p_end>pg_catalog.statement_timestamp()
 OR p_end-p_start>interval '31 days'
 OR p_start<pg_catalog.statement_timestamp()-interval '5 years'
 THEN RAISE EXCEPTION 'V419_BOUNDED_COHORT_WINDOW_REQUIRED'; END IF;
 SELECT count(*) INTO v_count
 FROM public.empire_predictive_opportunity_custody_v418 c
 WHERE c.tenant_id=v_session_tenant
  AND c.first_seen_at>=p_start AND c.first_seen_at<p_end;
 IF v_count>5000 THEN RAISE EXCEPTION 'V419_COHORT_EXCEEDS_READ_CAP'; END IF;
 RETURN QUERY
 SELECT v_count,
  count(g.id),
  count(*) FILTER (WHERE g.source_channel IS NULL OR
                      pg_catalog.length(pg_catalog.btrim(g.source_channel))=0),
  count(*) FILTER (WHERE g.niche IS NULL OR
                      pg_catalog.length(pg_catalog.btrim(g.niche))=0),
  count(*) FILTER (WHERE g.opportunity_type IS NULL OR
                      pg_catalog.length(pg_catalog.btrim(g.opportunity_type))=0),
  count(*) FILTER (WHERE c.custody_claim_recorded_at>g.created_at+interval '24 hours'),
  count(*) FILTER (WHERE c.acquisition_cost_minor=0),
  count(DISTINCT c.source_evidence_digest),
  count(DISTINCT c.owner_evidence_digest),
  count(DISTINCT pg_catalog.lower(pg_catalog.btrim(g.niche))),
  count(DISTINCT pg_catalog.lower(pg_catalog.btrim(g.source_channel))),
  count(DISTINCT pg_catalog.lower(pg_catalog.btrim(g.opportunity_type))),
  false,false,false,false,false
 FROM public.empire_predictive_opportunity_custody_v418 c
 JOIN public.gtm_opportunities g ON g.id=c.opportunity_id
 WHERE c.tenant_id=v_session_tenant
  AND c.first_seen_at>=p_start AND c.first_seen_at<p_end;
END;
$reader$;
REVOKE ALL ON FUNCTION public.read_predictive_revenue_source_lineage_held_v1(uuid,timestamptz,timestamptz)
 FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.read_predictive_revenue_source_lineage_held_v1(uuid,timestamptz,timestamptz)
 TO empire_predictive_cash_candidate_reader;
COMMENT ON FUNCTION public.read_predictive_revenue_source_lineage_held_v1(uuid,timestamptz,timestamptz)
IS 'HELD aggregate of existing GTM source fields vs tenant-claimed custody. No source licence, intake completeness, invoice/cost or independent owner proof. A repeated digest can cover a licensed batch and is not automatically a duplicate.';
COMMIT;
