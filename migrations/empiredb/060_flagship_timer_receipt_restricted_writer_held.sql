-- EMPIRE AI / ORIGINAL EMPIREDB 060: HELD ATOMIC RECEIPT WRITER.
-- REVIEW ONLY. Runs in disposable original EmpireDB fixture, NOT production.
-- Depends on approved 057/058/059, owner-managed signed callback/consent.
-- NO service LOGIN, EXECUTE grant, INSERT grant, sender, provider, callback
-- listener or notification scheduler is created.
--
-- SECURITY WARNING: this function protects SQL privilege/atomicity only.
-- It CANNOT validate a real provider's Ed25519 signature or live user
-- consent. No runtime role may be granted EXECUTE until original Identity,
-- Security, Notification and EmpireDB owners implement a trustworthy
-- authenticated gateway and independently approve the privilege boundary.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb','empire_timer_fixture') THEN
    RAISE EXCEPTION 'TIMER060_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
     AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
     AND NOT rolcreatedb AND NOT rolcreaterole
  ) THEN
    RAISE EXCEPTION 'TIMER060_NO_RESTRICTED_MIGRATOR';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members WHERE roleid = (
       SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
    )
  ) THEN
    RAISE EXCEPTION 'TIMER060_UNREVIEWED_MIGRATOR_MEMBERS';
  END IF;
  IF pg_catalog.to_regclass('public.empire_prime_voice_timer_requests') IS NULL
    OR pg_catalog.to_regclass('public.empire_prime_voice_timer_events') IS NULL
    OR pg_catalog.to_regclass('public.empire_prime_timer_provider_receipts') IS NULL
    OR pg_catalog.to_regprocedure('public.empire_prime_voice_timer_transition_held(uuid,text,text,text,text)') IS NULL
    OR pg_catalog.to_regprocedure('public.empire_prime_timer_provider_receipt_guard_held()') IS NULL
  THEN
    RAISE EXCEPTION 'TIMER060_PREDECESSORS_057_058_059_REQUIRED';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname IN (
       'empire_prime_voice_timer_requests',
       'empire_prime_voice_timer_events',
       'empire_prime_timer_provider_receipts'
    ) AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
  ) THEN
    RAISE EXCEPTION 'TIMER060_FORCE_RLS_REQUIRED';
  END IF;
  IF pg_catalog.to_regprocedure(
    'public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz)'
  ) IS NOT NULL THEN
    RAISE EXCEPTION 'TIMER060_ALREADY_PRESENT_REQUIRE_OWNER_REVIEW';
  END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

-- Limited custody transition: locks the ORIGINAL request row, derives
-- callback_seq server-side, compares source to the original request, requires
-- the exact original claimed event and delegates ordering/replay constraints
-- to 059 trigger and unique indexes. No supplied callback stage implies
-- genuine provider delivery. No outbound device operation can occur.
CREATE FUNCTION public.empire_prime_timer_receipt_record_held(
    p_tenant uuid,
    p_timer_digest text,
    p_provider_code text,
    p_callback_nonce_digest text,
    p_receipt_digest text,
    p_claim_event_digest text,
    p_delivery_reference_digest text,
    p_source_attestation_digest text,
    p_callback_stage text,
    p_provider_reported_at timestamptz
)
RETURNS TABLE(held_receipt_seq smallint, held_status text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
SET row_security=on
AS $safe_custody$
DECLARE
  v_original_source text;
  v_previous_count integer;
  v_clock timestamptz;
BEGIN
  IF p_tenant IS NULL OR p_timer_digest IS NULL
    OR p_timer_digest !~ '^[0-9a-f]{64}$'
    OR p_provider_code IS NULL OR
      p_provider_code !~ '^[a-z][a-z0-9_]{2,47}$'
    OR p_callback_nonce_digest IS NULL OR
      p_callback_nonce_digest !~ '^[0-9a-f]{64}$'
    OR p_receipt_digest IS NULL OR p_receipt_digest !~ '^[0-9a-f]{64}$'
    OR p_claim_event_digest IS NULL OR p_claim_event_digest !~ '^[0-9a-f]{64}$'
    OR p_delivery_reference_digest IS NULL OR
      p_delivery_reference_digest !~ '^[0-9a-f]{64}$'
    OR p_source_attestation_digest IS NULL OR
      p_source_attestation_digest !~ '^[0-9a-f]{64}$'
    OR p_callback_stage IS NULL OR
      p_callback_stage NOT IN ('ACCEPTED','DELIVERED','FAILED')
    OR p_provider_reported_at IS NULL
  THEN
    RAISE EXCEPTION 'TIMER060_BOUNDED_ORIGINAL_CUSTODY_ARGUMENTS_REQUIRED';
  END IF;

  v_clock:=pg_catalog.clock_timestamp();
  IF p_provider_reported_at>v_clock + interval '1 minute'
     OR p_provider_reported_at<v_clock - interval '24 hours' THEN
    RAISE EXCEPTION 'TIMER060_OUT_OF_BOUNDS_PROVIDER_REPORT_TIME';
  END IF;
  -- Serializes callbacks for the SAME timer and ensures cancellation/claim
  -- changes are visible before assigning a callback sequence.
  SELECT r.source_attestation_digest INTO v_original_source
  FROM public.empire_prime_voice_timer_requests r
  WHERE r.tenant_id=p_tenant AND r.timer_digest=p_timer_digest
  FOR UPDATE;
  IF NOT FOUND OR v_original_source IS DISTINCT FROM p_source_attestation_digest THEN
    RAISE EXCEPTION 'TIMER060_ORIGINAL_TENANT_OR_SOURCE_MISMATCH';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.empire_prime_voice_timer_events e
    WHERE e.tenant_id=p_tenant AND e.timer_digest=p_timer_digest
      AND e.seq=2 AND e.event_kind='DISPATCH_CLAIMED'
      AND e.event_digest=p_claim_event_digest
  ) THEN
    RAISE EXCEPTION 'TIMER060_MISSING_ORIGINAL_ATOMIC_CLAIM';
  END IF;

  SELECT count(*) INTO v_previous_count
  FROM public.empire_prime_timer_provider_receipts p
  WHERE p.tenant_id=p_tenant AND p.timer_digest=p_timer_digest;
  IF v_previous_count>=2 THEN
    RAISE EXCEPTION 'TIMER060_TERMINAL_CUSTODY_STREAM';
  END IF;

  INSERT INTO public.empire_prime_timer_provider_receipts(
    tenant_id,timer_digest,provider_code,callback_nonce_digest,
    receipt_digest,claim_event_digest,delivery_reference_digest,
    source_attestation_digest,callback_stage,callback_seq,
    provider_reported_at
  ) VALUES (
    p_tenant,p_timer_digest,p_provider_code,p_callback_nonce_digest,
    p_receipt_digest,p_claim_event_digest,p_delivery_reference_digest,
    p_source_attestation_digest,p_callback_stage,(v_previous_count+1)::smallint,
    p_provider_reported_at
  );

  RETURN QUERY SELECT (v_previous_count+1)::smallint,
    'HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED'::text;
END;
$safe_custody$;

-- PostgreSQL functions grant EXECUTE to PUBLIC by default. The REVOKE is
-- in the SAME transaction, so there is no committed PUBLIC-executable gap.
REVOKE ALL ON FUNCTION public.empire_prime_timer_receipt_record_held(
    uuid,text,text,text,text,text,text,text,text,timestamptz
) FROM PUBLIC;

COMMENT ON FUNCTION public.empire_prime_timer_receipt_record_held(
    uuid,text,text,text,text,text,text,text,text,timestamptz
) IS 'HELD. Locked original-tenant metadata custody only. NO runtime EXECUTE grants and NO authentic real-world provider/device/consent validation.';

COMMIT;
