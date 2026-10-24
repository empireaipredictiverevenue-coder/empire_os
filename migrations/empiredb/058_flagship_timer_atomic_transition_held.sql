-- EmpireOS / EmpireDB 058 - HELD ATOMIC CLAIM AND CANCEL PREVIEW.
-- NOT APPLIED TO PRODUCTION. Requires original DBA, Security, Voice,
-- Privacy and ASTRA review; intended for disposable fixture validation only.
-- Adds ZERO runtime login/grants, schedulers, notification systems or sends.
-- The SECURITY DEFINER has NO EXECUTE permission for PUBLIC or app users.
-- Use only with original 057 ledger, canonical EmpireDB and owner approval.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';
DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb','empire_timer_fixture') THEN
    RAISE EXCEPTION 'TIMER058_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator'
      AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
      AND NOT rolcreatedb AND NOT rolcreaterole
  ) THEN
    RAISE EXCEPTION 'TIMER058_RESTRICTED_MIGRATOR_UNVERIFIED';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members
    WHERE roleid = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
  ) THEN
    RAISE EXCEPTION 'TIMER058_MIGRATOR_MEMBERSHIP_REQUIRES_SECURITY_REVIEW';
  END IF;
  IF pg_catalog.to_regclass('public.empire_prime_voice_timer_requests') IS NULL
     OR pg_catalog.to_regclass('public.empire_prime_voice_timer_events') IS NULL
  THEN
    RAISE EXCEPTION 'TIMER058_PREVIOUS_LEDGER_REQUIRED';
  END IF;
  IF pg_catalog.to_regprocedure(
    'public.empire_prime_voice_timer_transition_held(uuid,text,text,text,text)'
  ) IS NOT NULL THEN
    RAISE EXCEPTION 'TIMER058_EXISTING_TRANSITION_NEEDS_OWNER_REVIEW';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_policies
    WHERE schemaname='public' AND tablename IN (
       'empire_prime_voice_timer_requests','empire_prime_voice_timer_events')
  ) THEN
    RAISE EXCEPTION 'TIMER058_EXISTING_RLS_POLICIES_REQUIRE_OWNER_REVIEW';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public'
      AND c.relname IN ('empire_prime_voice_timer_requests',
                        'empire_prime_voice_timer_events')
      AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
  ) THEN
    RAISE EXCEPTION 'TIMER058_FORCE_RLS_REQUIRED';
  END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

-- With FORCE RLS even the NOLOGIN table owner requires an explicit policy.
-- ONLY the migration OWNER is admitted. No application role is added.
-- POLICY does not grant SQL table privileges or LOGIN/membership.
CREATE POLICY empire_prime_timer_held_owner_requests
  ON public.empire_prime_voice_timer_requests
  FOR ALL TO empiredb_migrator USING (true) WITH CHECK (true);
CREATE POLICY empire_prime_timer_held_owner_events
  ON public.empire_prime_voice_timer_events
  FOR ALL TO empiredb_migrator USING (true) WITH CHECK (true);

-- A trusted append-only trigger is the actual transition boundary, even
-- for a privileged user issuing a direct INSERT instead of the held RPC.
-- No trigger can constrain an adversarial superuser who disables it; no
-- provider report counts as cryptographically verified delivery.
CREATE FUNCTION public.empire_prime_voice_timer_insert_guard_held()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = '' SET row_security = on
AS $guard_body$
DECLARE
  v_due timestamptz;
  v_created timestamptz;
  v_source text;
  v_last text;
  v_seq integer;
  v_count integer;
  v_clock timestamptz;
BEGIN
  SELECT r.due_at, r.created_at, r.source_attestation_digest
    INTO v_due,v_created,v_source
  FROM public.empire_prime_voice_timer_requests r
  WHERE r.tenant_id=NEW.tenant_id AND r.timer_digest=NEW.timer_digest
  FOR UPDATE;
  IF NOT FOUND OR NEW.source_attestation_digest IS DISTINCT FROM v_source THEN
    RAISE EXCEPTION 'TIMER058_INSERT_UNKNOWN_TENANT_OR_SOURCE';
  END IF;
  SELECT count(*), max(seq) INTO v_count,v_seq
    FROM public.empire_prime_voice_timer_events e
    WHERE e.tenant_id=NEW.tenant_id AND e.timer_digest=NEW.timer_digest;
  IF v_count=0 THEN
    IF NEW.seq<>1 OR NEW.event_kind<>'TIMER_CREATED'
       OR NEW.occurred_at<>v_created OR NEW.provider_receipt_digest IS NOT NULL THEN
      RAISE EXCEPTION 'TIMER058_CREATE_EVENT_REQUIRED_FIRST';
    END IF;
    RETURN NEW;
  END IF;
  IF v_count<>v_seq OR NEW.seq<>v_seq+1 THEN
    RAISE EXCEPTION 'TIMER058_ATOMIC_EVENT_SEQUENCE_REQUIRED';
  END IF;
  SELECT e.event_kind INTO v_last
  FROM public.empire_prime_voice_timer_events e
  WHERE e.tenant_id=NEW.tenant_id AND e.timer_digest=NEW.timer_digest
  ORDER BY e.seq DESC LIMIT 1;
  v_clock := pg_catalog.clock_timestamp();
  IF NEW.occurred_at>v_clock + interval '1 minute'
     OR NEW.occurred_at<v_created THEN
    RAISE EXCEPTION 'TIMER058_UNTRUSTED_EVENT_CLOCK';
  END IF;
  IF v_last='TIMER_CREATED' AND v_seq=1 THEN
    IF NEW.event_kind='TIMER_CANCELLED' AND v_clock<v_due THEN
      RETURN NEW;
    ELSIF NEW.event_kind='DISPATCH_CLAIMED' AND v_clock>=v_due THEN
      RETURN NEW;
    END IF;
  ELSIF v_last='DISPATCH_CLAIMED' THEN
    IF NEW.event_kind IN ('PROVIDER_ACCEPTED_REPORTED',
                          'PROVIDER_FAILED_REPORTED') THEN
      RETURN NEW;
    END IF;
  ELSIF v_last='PROVIDER_ACCEPTED_REPORTED' THEN
    IF NEW.event_kind IN ('PROVIDER_DELIVERED_REPORTED',
                          'PROVIDER_FAILED_REPORTED') THEN
      RETURN NEW;
    END IF;
  END IF;
  RAISE EXCEPTION 'TIMER058_ILLEGAL_OR_UNDUE_TRANSITION';
END;
$guard_body$;
CREATE TRIGGER empire_prime_timer_event_transition_held
  BEFORE INSERT ON public.empire_prime_voice_timer_events
  FOR EACH ROW EXECUTE FUNCTION public.empire_prime_voice_timer_insert_guard_held();

CREATE FUNCTION public.empire_prime_voice_timer_transition_held(
  p_tenant uuid, p_timer_digest text, p_action text,
  p_event_digest text, p_source_digest text
) RETURNS TABLE(seq smallint, state_code text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $function$
DECLARE
  v_due timestamptz;
  v_source text;
  v_clock timestamptz;
  v_kind text;
  v_seq integer;
  v_initial text;
  v_count integer;
BEGIN
  -- No raw audio/recipient/input commands; only bounded digest metadata.
  -- Real auth/consent NOT independently verified by digest equality.
  IF p_tenant IS NULL
     OR p_timer_digest IS NULL
     OR p_timer_digest !~ '^[a-f0-9]{64}$'
     OR p_event_digest IS NULL
     OR p_event_digest !~ '^[a-f0-9]{64}$'
     OR p_source_digest IS NULL
     OR p_source_digest !~ '^[a-f0-9]{64}$'
     OR p_action IS NULL OR p_action NOT IN ('TIMER_CANCELLED','DISPATCH_CLAIMED')
  THEN
    RAISE EXCEPTION 'TIMER058_RESTRICTED_SYNTHETIC_ARGUMENTS_REQUIRED';
  END IF;

  -- The same request row is the lock root for both cancellation and claim.
  -- The competing worker blocks; after release it must re-evaluate state.
  SELECT r.due_at, r.source_attestation_digest
    INTO v_due, v_source
  FROM public.empire_prime_voice_timer_requests AS r
  WHERE r.tenant_id=p_tenant AND r.timer_digest=p_timer_digest
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'TIMER058_UNKNOWN_OR_WRONG_TENANT_TIMER';
  END IF;
  IF v_source <> p_source_digest THEN
    RAISE EXCEPTION 'TIMER058_SOURCE_DIGEST_MISMATCH';
  END IF;

  SELECT count(*), min(e.event_kind) FILTER (WHERE e.seq=1), max(e.seq)
    INTO v_count, v_initial, v_seq
  FROM public.empire_prime_voice_timer_events AS e
  WHERE e.tenant_id=p_tenant AND e.timer_digest=p_timer_digest;
  IF v_count < 1 OR v_count <> v_seq
     OR v_initial IS DISTINCT FROM 'TIMER_CREATED'
     OR v_seq >= 32 THEN
    RAISE EXCEPTION 'TIMER058_MALFORMED_OR_EXHAUSTED_EVENT_STREAM';
  END IF;

  SELECT e.event_kind INTO v_kind
  FROM public.empire_prime_voice_timer_events AS e
  WHERE e.tenant_id=p_tenant AND e.timer_digest=p_timer_digest
  ORDER BY e.seq DESC LIMIT 1;
  IF v_kind <> 'TIMER_CREATED' OR v_seq <> 1 THEN
    RAISE EXCEPTION 'TIMER058_ALREADY_TRANSITIONED_OR_CLOSED';
  END IF;

  v_clock := pg_catalog.clock_timestamp();
  IF p_action='DISPATCH_CLAIMED' AND v_clock < v_due THEN
    RAISE EXCEPTION 'TIMER058_CLAIM_NOT_YET_DUE';
  END IF;
  IF p_action='TIMER_CANCELLED' AND v_clock >= v_due THEN
    RAISE EXCEPTION 'TIMER058_CANCELLATION_AFTER_DUE_REFUSED';
  END IF;

  INSERT INTO public.empire_prime_voice_timer_events(
    tenant_id,timer_digest,seq,event_digest,event_kind,occurred_at,
    source_attestation_digest
  ) VALUES (
    p_tenant,p_timer_digest,(v_seq+1)::smallint,p_event_digest,
    p_action,v_clock,p_source_digest
  );
  RETURN QUERY SELECT (v_seq+1)::smallint,
    CASE WHEN p_action='DISPATCH_CLAIMED'
      THEN 'HELD_CLAIM_NO_EXTERNAL_DISPATCH'
      ELSE 'HELD_CANCEL_NO_EXTERNAL_DISPATCH'
    END::text;
END;
$function$;

-- PostgreSQL defaults EXECUTE to PUBLIC: revoke within the same DDL
-- transaction so no visible committed interval permits public calls.
REVOKE ALL ON FUNCTION public.empire_prime_voice_timer_transition_held(
  uuid,text,text,text,text
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_prime_voice_timer_insert_guard_held() FROM PUBLIC;

COMMENT ON FUNCTION public.empire_prime_voice_timer_transition_held(
  uuid,text,text,text,text
) IS 'HELD, NO EXECUTE GRANTS: atomic claim/cancel for original EmpireDB fixture only. Digest does not prove consent, provider receipt or actual delivery.';

COMMIT;
