-- EmpireDB 067: PREPARED ONLY, owner-approved restricted direct BSC cash candidate.
-- Requires DBA/security review, backup, RLS inventory, rollback and separate
-- provisioning. Does NOT run at boot. No new login, payment or settlement.
-- No production migrations were executed while authoring/rehearsing this.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
DECLARE source_name text;
BEGIN
  IF current_database() NOT IN ('empiredb','empire_v415_fixture') THEN
    RAISE EXCEPTION 'V415_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
      AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole) THEN
    RAISE EXCEPTION 'V415_ORIGINAL_RESTRICTED_OWNER_REQUIRED';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_predictive_cash_candidate_reader'
      AND NOT rolcanlogin AND NOT rolsuper AND NOT rolinherit
      AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
      AND NOT rolreplication) THEN
    RAISE EXCEPTION 'V415_DEDICATED_NOLOGIN_READER_ROLE_REQUIRED';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members
    WHERE roleid=pg_catalog.to_regrole('empire_predictive_cash_candidate_reader')) THEN
    RAISE EXCEPTION 'V415_READER_CAPABILITY_ALREADY_ASSIGNED_REVIEW';
  END IF;
  IF pg_catalog.to_regprocedure(
    'public.read_predictive_direct_bsc_cash_candidate_v1(uuid,uuid[])'
  ) IS NOT NULL THEN RAISE EXCEPTION 'V415_EXISTING_READER_RECONCILE'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc
    WHERE oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
      AND prosecdef AND provolatile='s'
      AND proowner=pg_catalog.to_regrole('empiredb_migrator')) THEN
    RAISE EXCEPTION 'V415_ORIGINAL_TENANT_SESSION_RESOLVER_REQUIRED';
  END IF;
  FOREACH source_name IN ARRAY ARRAY[
    'public.buyers','public.fulfilment_orders',
    'public.bsc_payment_requests','public.bsc_payment_evidence'
  ] LOOP
    IF pg_catalog.to_regclass(source_name) IS NULL
     OR NOT pg_catalog.has_table_privilege(
       'empiredb_migrator',source_name,'SELECT') THEN
      RAISE EXCEPTION 'V415_OWNER_SOURCE_TABLE_NOT_AVAILABLE';
    END IF;
    IF pg_catalog.has_table_privilege(
      'empire_predictive_cash_candidate_reader',source_name,'SELECT')
     OR pg_catalog.has_table_privilege(
      'empire_predictive_cash_candidate_reader',source_name,'INSERT')
     OR pg_catalog.has_table_privilege(
      'empire_predictive_cash_candidate_reader',source_name,'UPDATE')
     OR pg_catalog.has_table_privilege(
      'empire_predictive_cash_candidate_reader',source_name,'DELETE') THEN
      RAISE EXCEPTION 'V415_UNEXPECTED_DIRECT_SOURCE_TABLE_PRIVILEGE';
    END IF;
  END LOOP;
END;
$guard$;

-- Privileged operator grants schema visibility, never source-table SELECT.
GRANT USAGE ON SCHEMA public TO empire_predictive_cash_candidate_reader;
SET LOCAL ROLE empiredb_migrator;
CREATE FUNCTION public.read_predictive_direct_bsc_cash_candidate_v1(
  p_tenant uuid, p_order_ids uuid[]
) RETURNS TABLE(
  selected_order_id uuid,
  evidence_status text,
  selected_direct_usdt_candidate_usd_cents bigint,
  payment_and_tenant_lineage_matches boolean,
  independent_refund_finality_verified boolean,
  cash_collected_by_finance_verified boolean,
  commercial_action_authorized boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=''
AS $reader$
DECLARE
  v_tenant uuid;
  v_id uuid;
  v_matches bigint;
  v_amount bigint;
BEGIN
  -- This is the ORIGINAL separately managed restricted tenant login.
  -- The migration grants no LOGIN and no membership or tenant binding.
  IF session_user <> 'empire_predictive_cash_candidate_login' THEN
    RAISE EXCEPTION 'V415_UNTRUSTED_SESSION_USER';
  END IF;
  v_tenant := public.empire_current_tenant_id();
  IF v_tenant IS NULL OR p_tenant IS NULL OR p_tenant <> v_tenant THEN
    RAISE EXCEPTION 'V415_SESSION_BOUND_TENANT_REQUIRED';
  END IF;
  IF p_order_ids IS NULL OR pg_catalog.cardinality(p_order_ids) NOT BETWEEN 1 AND 8
   OR EXISTS(SELECT 1 FROM pg_catalog.unnest(p_order_ids) AS x WHERE x IS NULL)
   OR (SELECT count(DISTINCT x) FROM pg_catalog.unnest(p_order_ids) AS x)
        <> pg_catalog.cardinality(p_order_ids) THEN
    RAISE EXCEPTION 'V415_BOUNDED_UNIQUE_EXPLICIT_ORDER_SET_REQUIRED';
  END IF;
  FOREACH v_id IN ARRAY p_order_ids LOOP
    -- The only positive match is a DIRECT, non-escrow settlement candidate:
    -- exact buyer tenant, order, approved terms, USDT/BSC transfer,
    -- 12+ confirmations, bounded as-of and exact 18-decimal on-chain amount.
    -- This is NOT a withdrawal/refund-complete or bank-settled cash proof.
    SELECT count(*),max(o.price_cents) INTO v_matches,v_amount
    FROM public.fulfilment_orders AS o
    JOIN public.buyers AS b
      ON b.id=o.buyer_id AND b.org_id=v_tenant
    JOIN public.bsc_payment_requests AS r
      ON r.fulfilment_order_id=o.id AND r.buyer_id=o.buyer_id
       AND r.settlement_mode='direct' AND r.status='approved'
       AND r.approved_at IS NOT NULL AND r.approved_by IS NOT NULL
       AND r.amount_usdt*100=o.price_cents::numeric
       AND r.commercial_terms_sha256=
           lower(o.commercial_payload->>'commercial_terms_sha256')
    JOIN public.bsc_payment_evidence AS d
      ON d.request_id=r.id AND d.fulfilment_order_id=o.id
       AND d.chain_id=56
       AND d.token_contract='0x55d398326f99059ff775485246999027b3197955'
       AND d.confirmations>=12
       AND d.treasury_address=r.treasury_address
       AND d.commercial_terms_sha256=r.commercial_terms_sha256
       AND d.verified_at<=pg_catalog.statement_timestamp()
       AND d.amount_raw=o.price_cents::numeric*10000000000000000::numeric
    WHERE o.id=v_id
      AND o.state IN ('settled','outcome_captured')
      AND o.settled_at IS NOT NULL
      AND o.settled_at<=pg_catalog.statement_timestamp()
      AND o.price_cents BETWEEN 1 AND 100000000000;
    selected_order_id := v_id;
    payment_and_tenant_lineage_matches := (v_matches=1);
    evidence_status := CASE WHEN v_matches=1
      THEN 'DIRECT_USDT_BSC_TRANSFER_CANDIDATE_HELD'
      ELSE 'NO_UNAMBIGUOUS_DIRECT_BSC_EVIDENCE_HELD' END;
    selected_direct_usdt_candidate_usd_cents :=
      CASE WHEN v_matches=1 THEN v_amount ELSE NULL END;
    independent_refund_finality_verified := false;
    cash_collected_by_finance_verified := false;
    commercial_action_authorized := false;
    RETURN NEXT;
  END LOOP;
END;
$reader$;

REVOKE ALL ON FUNCTION
  public.read_predictive_direct_bsc_cash_candidate_v1(uuid,uuid[])
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  public.read_predictive_direct_bsc_cash_candidate_v1(uuid,uuid[])
  TO empire_predictive_cash_candidate_reader;
COMMENT ON FUNCTION
  public.read_predictive_direct_bsc_cash_candidate_v1(uuid,uuid[])
IS 'HELD: explicitly selected original-tenant direct BSC transfer candidates. No cohort census, escrow, refunds, bank reconciliation, fiat cash, rights, spending or revenue approval.';
COMMIT;
