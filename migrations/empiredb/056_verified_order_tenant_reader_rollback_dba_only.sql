-- DBA-controlled rollback for order056 only. NOT automatically executed.
-- Apply only after assessing the dedicated login and live clients.
-- For revocation of an individual login first revoke membership/binding,
-- then retire the login's SCRAM credential.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';
SET LOCAL ROLE empiredb_migrator;
DROP POLICY IF EXISTS order056_escrow_evidence_tenant_select ON public.bsc_escrow_evidence;
DROP POLICY IF EXISTS order056_escrow_agreements_tenant_select ON public.bsc_escrow_agreements;
DROP POLICY IF EXISTS order056_payment_evidence_tenant_select ON public.bsc_payment_evidence;
DROP POLICY IF EXISTS order056_payment_requests_tenant_select ON public.bsc_payment_requests;
DROP POLICY IF EXISTS order056_outcomes_tenant_select ON public.commercial_outcomes;
REVOKE SELECT ON
  public.bsc_escrow_evidence, public.bsc_escrow_agreements,
  public.bsc_payment_evidence, public.bsc_payment_requests,
  public.commercial_outcomes FROM empiredb_tenant_reader;
COMMIT;
