-- EmpireOS original EmpireDB 061: consent required at the database INSERT boundary.
-- HELD FOR ORIGINAL SECURITY/IDENTITY/PRIVACY/EMPIREDB OWNER REVIEW ONLY.
-- DOES NOT establish real-world consent or install an Identity authority.
-- This candidate DENIES ALL new callback records until a separately approved,
-- authenticated, revocable owner authority replaces the DENY function.
-- No runtime permission, LOGIN, provider, key, transport or scheduler.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $preflight$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_timer_fixture') THEN
   RAISE EXCEPTION 'TIMER061_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
     AND NOT rolsuper AND NOT rolbypassrls
     AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN
   RAISE EXCEPTION 'TIMER061_RESTRICTED_MIGRATOR_REQUIRED';
 END IF;
 IF EXISTS (
   SELECT 1 FROM pg_catalog.pg_auth_members
   WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles
                 WHERE rolname='empiredb_migrator')
 ) THEN
   RAISE EXCEPTION 'TIMER061_UNREVIEWED_MIGRATOR_MEMBERS';
 END IF;
 IF pg_catalog.to_regclass('public.empire_prime_voice_timer_requests') IS NULL
   OR pg_catalog.to_regclass('public.empire_prime_timer_provider_receipts') IS NULL
   OR pg_catalog.to_regprocedure(
      'public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz)'
   ) IS NULL
 THEN
   RAISE EXCEPTION 'TIMER061_REQUIRES_ORIGINAL_057_TO_060';
 END IF;
 IF pg_catalog.to_regprocedure(
      'public.empire_prime_timer_consent_authority_held(uuid,text,text)'
   ) IS NOT NULL OR EXISTS (
     SELECT 1 FROM pg_catalog.pg_trigger
     WHERE tgname='empire_prime_timer_consent_insert_hold_061'
       AND NOT tgisinternal
   ) THEN
   RAISE EXCEPTION 'TIMER061_ALREADY_PRESENT_OWNER_REVIEW_REQUIRED';
 END IF;
 IF EXISTS (
   SELECT 1 FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public'
     AND c.relname IN (
        'empire_prime_voice_timer_requests',
        'empire_prime_timer_provider_receipts'
     )
     AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
 ) THEN
   RAISE EXCEPTION 'TIMER061_FORCE_RLS_REQUIRED';
 END IF;
END;
$preflight$;

SET LOCAL ROLE empiredb_migrator;

-- Intentionally false. No SQL caller, including the held 060 writer,
-- can supply a synthetic "consent = true" parameter to bypass this.
-- The real original Identity/Privacy owner must independently approve a
-- revocable source; an unreviewed replacement would be unsafe.
CREATE FUNCTION public.empire_prime_timer_consent_authority_held(
 p_tenant uuid, p_timer_digest text, p_source_attestation_digest text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path='' SET row_security=on
AS $deny_unverified_authority$
BEGIN
  RETURN FALSE;
END;
$deny_unverified_authority$;

CREATE FUNCTION public.empire_prime_timer_consent_insert_guard_held()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path='' SET row_security=on
AS $insert_guard$
DECLARE
  v_authorised boolean;
BEGIN
  -- This is a second independent gate on the original 059 table, so even
  -- a direct privileged INSERT (unless DB owner disables triggers) cannot
  -- bypass the owner consent decision.
  SELECT public.empire_prime_timer_consent_authority_held(
    NEW.tenant_id,NEW.timer_digest,NEW.source_attestation_digest
  ) INTO v_authorised;
  IF v_authorised IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION 'TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED';
  END IF;
  RETURN NEW;
END;
$insert_guard$;

CREATE TRIGGER empire_prime_timer_consent_insert_hold_061
  BEFORE INSERT ON public.empire_prime_timer_provider_receipts
  FOR EACH ROW
  EXECUTE FUNCTION public.empire_prime_timer_consent_insert_guard_held();

REVOKE ALL ON FUNCTION public.empire_prime_timer_consent_authority_held(
 uuid,text,text
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_prime_timer_consent_insert_guard_held()
 FROM PUBLIC;

COMMENT ON FUNCTION public.empire_prime_timer_consent_authority_held(
 uuid,text,text
) IS 'HELD ORIGINAL PRIME GATE: DENY by default, not a real connected consent authority. No runtime grant or provider.';
COMMENT ON TRIGGER empire_prime_timer_consent_insert_hold_061
 ON public.empire_prime_timer_provider_receipts IS
 'HELD: callback metadata denied without original independently approved current consent, including direct table INSERT. No real consent integration.';

COMMIT;
