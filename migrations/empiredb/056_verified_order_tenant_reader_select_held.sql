-- EmpireDB 056 — REVIEW-ONLY candidate for canonical tenant order proof.
-- PREPARED, NOT APPLIED: source owner and DBA must approve after ephemeral
-- RLS / cross-tenant / table-permission tests. NO login, tenant binding,
-- transfer, payment, order, DML, RPC, job or writer created.
--
-- The tenant is derived from public.empire_current_tenant_id() where
-- session_user maps to an active tenant binding, NEVER from SET ROLE or GUC.
-- Policies intentionally deny orphaned order/payment/escrow records.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
DECLARE item text;
BEGIN
 IF current_database() NOT IN ('empiredb','empire_order_fixture') THEN
   RAISE EXCEPTION 'ORDER056_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_tenant_reader'
    AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
    AND NOT rolcreaterole AND NOT rolcreatedb
 ) THEN RAISE EXCEPTION 'ORDER056_TENANT_ROLE_UNSAFE'; END IF;
 IF NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_proc WHERE oid=
      pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
      AND prosecdef
 ) THEN RAISE EXCEPTION 'ORDER056_AUTHENTICATED_TENANT_RESOLVER_ABSENT'; END IF;
 FOREACH item IN ARRAY ARRAY[
   'commercial_outcomes','bsc_payment_requests','bsc_payment_evidence',
   'bsc_escrow_agreements','bsc_escrow_evidence'
 ] LOOP
   IF NOT EXISTS(
      SELECT 1 FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relname=item
        AND c.relkind='r' AND c.relrowsecurity
        AND c.relowner='empiredb_migrator'::regrole
   ) THEN RAISE EXCEPTION 'ORDER056_SOURCE_RLS_OR_OWNER_UNVERIFIED:%',item; END IF;
 END LOOP;
 IF EXISTS(
   SELECT 1 FROM pg_catalog.pg_policy p
   WHERE p.polname IN (
     'order056_outcomes_tenant_select','order056_payment_requests_tenant_select',
     'order056_payment_evidence_tenant_select','order056_escrow_agreements_tenant_select',
     'order056_escrow_evidence_tenant_select'
   )
 ) THEN RAISE EXCEPTION 'ORDER056_ALREADY_PRESENT_REVIEW_REQUIRED'; END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

-- No broad GRANT to PUBLIC, empiredb_readonly or empiredb_app.
GRANT SELECT ON
  public.commercial_outcomes,
  public.bsc_payment_requests,
  public.bsc_payment_evidence,
  public.bsc_escrow_agreements,
  public.bsc_escrow_evidence
TO empiredb_tenant_reader;

CREATE POLICY order056_outcomes_tenant_select
ON public.commercial_outcomes
FOR SELECT TO empiredb_tenant_reader USING (
  EXISTS (
    SELECT 1 FROM public.fulfilment_orders o
    JOIN public.buyers b ON b.id=o.buyer_id
    WHERE o.id=commercial_outcomes.fulfilment_order_id
      AND b.org_id=public.empire_current_tenant_id()
  )
);

CREATE POLICY order056_payment_requests_tenant_select
ON public.bsc_payment_requests
FOR SELECT TO empiredb_tenant_reader USING (
  fulfilment_order_id IS NOT NULL AND buyer_id IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM public.fulfilment_orders o
    JOIN public.buyers b ON b.id=o.buyer_id
    WHERE o.id=bsc_payment_requests.fulfilment_order_id
      AND b.id=bsc_payment_requests.buyer_id
      AND b.org_id=public.empire_current_tenant_id()
  )
);

CREATE POLICY order056_payment_evidence_tenant_select
ON public.bsc_payment_evidence
FOR SELECT TO empiredb_tenant_reader USING (
  EXISTS (
    SELECT 1 FROM public.bsc_payment_requests r
    WHERE r.id=bsc_payment_evidence.request_id
      AND r.fulfilment_order_id=bsc_payment_evidence.fulfilment_order_id
  )
);

CREATE POLICY order056_escrow_agreements_tenant_select
ON public.bsc_escrow_agreements
FOR SELECT TO empiredb_tenant_reader USING (
  EXISTS (
    SELECT 1 FROM public.bsc_payment_requests r
    WHERE r.id=bsc_escrow_agreements.request_id
  )
);

CREATE POLICY order056_escrow_evidence_tenant_select
ON public.bsc_escrow_evidence
FOR SELECT TO empiredb_tenant_reader USING (
  EXISTS (
    SELECT 1 FROM public.bsc_escrow_agreements a
    WHERE a.id=bsc_escrow_evidence.agreement_id
  )
);

-- This migration ONLY prepares RLS-gated SELECT grants on already existing
-- tables. It does not activate any tenant login or verify individual orders.
COMMIT;
