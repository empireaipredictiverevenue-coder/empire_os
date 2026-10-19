-- EmpireDB ANALYTICS055 — HELD retention/erasure capability for ANALYTICS054.
-- PREPARED ONLY: never run on production without separate DBA approval,
-- privacy policy, canonical owner/role proof and recovery/backup checkpoint.
-- NO writer login is created, NO EXECUTE granted and NO collector enabled.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $preflight$
DECLARE tab text;
BEGIN
 IF pg_catalog.current_database() NOT IN ('empiredb','empire_analytics_fixture') THEN
  RAISE EXCEPTION 'ANALYTICS055_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
  AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
 ) THEN RAISE EXCEPTION 'ANALYTICS055_MIGRATOR_BOUNDARY_UNVERIFIED'; END IF;
 FOREACH tab IN ARRAY ARRAY[
  'empire_analytics_sessions','empire_analytics_consent_decisions',
  'empire_analytics_event_receipts'
 ] LOOP
  IF NOT EXISTS(
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
    WHERE n.nspname='public' AND c.relname=tab
    AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity
    AND r.rolname='empiredb_migrator'
  ) THEN
   RAISE EXCEPTION 'ANALYTICS055_PARENT_OWNER_OR_FORCED_RLS_UNVERIFIED:%', tab;
  END IF;
 END LOOP;
 IF NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r
  ON r.oid=p.proowner
  WHERE p.oid=pg_catalog.to_regprocedure('public.empire_analytics_immutable()')
  AND r.rolname='empiredb_migrator' AND NOT p.prosecdef
 ) THEN RAISE EXCEPTION 'ANALYTICS055_GUARD_OWNER_UNVERIFIED'; END IF;
 IF pg_catalog.to_regclass('public.empire_analytics_erasure_audit') IS NOT NULL
  OR pg_catalog.to_regprocedure(
   'public.empire_analytics_erase_session(uuid,text,text,text,text)'
  ) IS NOT NULL
 THEN RAISE EXCEPTION 'ANALYTICS055_EXISTING_ERASURE_OBJECT_REVIEW_REQUIRED'; END IF;
END;
$preflight$;

SET LOCAL ROLE empiredb_migrator;

-- Non-identifying erasure audit: NO session digest, raw path, IP, email,
-- cookie, client identifier or user agent is retained after deletion.
CREATE TABLE public.empire_analytics_erasure_audit (
 audit_id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_key text NOT NULL CHECK(property_key='empire-ai.co.uk'),
 erasure_reason text NOT NULL CHECK(
  erasure_reason IN ('EXPIRED_RETENTION','VERIFIED_ERASURE_REQUEST')),
 verification_reference_sha256 text NOT NULL CHECK(
  verification_reference_sha256 ~ '^[a-f0-9]{64}$'),
 sessions_erased integer NOT NULL CHECK(sessions_erased=1),
 decisions_erased integer NOT NULL CHECK(decisions_erased BETWEEN 0 AND 1000000),
 events_erased integer NOT NULL CHECK(events_erased BETWEEN 0 AND 5000000),
 actor_role text NOT NULL CHECK(actor_role='empire_analytics_maintenance_login'),
 recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);
COMMENT ON TABLE public.empire_analytics_erasure_audit IS
 'HELD. Bounded session erasure receipt only; contains counts and review reference, no individual session identifier. Retention duration and erasure request evidence require privacy approval.';

-- Force RLS applies to the migrator owner. Only the NOLOGIN
-- migrator may see/delete the three existing internal tables and
-- append the non-identifying audit entry. No service role gains access.
CREATE POLICY empire_analytics_maint_sessions_select
 ON public.empire_analytics_sessions FOR SELECT
 TO empiredb_migrator USING (true);
-- PostgreSQL SELECT FOR UPDATE obeys UPDATE RLS checks under forced RLS.
-- This USING grants migrator-only lock visibility, while WITH CHECK(false)
-- forbids all updated row versions; immutable triggers separately forbid UPDATE.
CREATE POLICY empire_analytics_maint_sessions_lock
 ON public.empire_analytics_sessions FOR UPDATE
 TO empiredb_migrator USING (true) WITH CHECK (false);
CREATE POLICY empire_analytics_maint_sessions_delete
 ON public.empire_analytics_sessions FOR DELETE
 TO empiredb_migrator USING (true);
CREATE POLICY empire_analytics_maint_decisions_select
 ON public.empire_analytics_consent_decisions FOR SELECT
 TO empiredb_migrator USING (true);
CREATE POLICY empire_analytics_maint_decisions_delete
 ON public.empire_analytics_consent_decisions FOR DELETE
 TO empiredb_migrator USING (true);
CREATE POLICY empire_analytics_maint_events_select
 ON public.empire_analytics_event_receipts FOR SELECT
 TO empiredb_migrator USING (true);
CREATE POLICY empire_analytics_maint_events_delete
 ON public.empire_analytics_event_receipts FOR DELETE
 TO empiredb_migrator USING (true);

-- The original append-only guard remains protective for ALL normal
-- direct operations, even by its owner. The single permitted DELETE
-- context is a purpose-bound SECURITY DEFINER call by the future
-- separately provisioned dedicated maintenance LOGIN.
-- This role is NOT created, bound, or granted in this migration.
CREATE OR REPLACE FUNCTION public.empire_analytics_immutable()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $guard$
BEGIN
 IF TG_OP='DELETE'
   AND session_user='empire_analytics_maintenance_login'
   AND current_user='empiredb_migrator'
   AND TG_TABLE_SCHEMA='public'
   AND TG_TABLE_NAME IN (
    'empire_analytics_sessions',
    'empire_analytics_consent_decisions',
    'empire_analytics_event_receipts'
   )
 THEN
   RETURN OLD;
 END IF;
 RAISE EXCEPTION 'ANALYTICS054_APPEND_ONLY_MUTATION_DENIED';
END;
$guard$;

CREATE FUNCTION public.empire_analytics_erase_session(
 p_tenant uuid,
 p_property text,
 p_session_digest text,
 p_reason text,
 p_verification_reference_sha256 text
)
RETURNS TABLE(
 erasure_audit_id uuid,
 erased_sessions integer,
 erased_consent_decisions integer,
 erased_event_receipts integer
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=''
AS $erasure$
DECLARE
 target public.empire_analytics_sessions%ROWTYPE;
 count_events integer;
 count_decisions integer;
 count_sessions integer;
 issued_audit uuid;
BEGIN
 -- No service identity, no impersonated SET ROLE, no caller-supplied
 -- tenant GUC and no public API execution. Exact independent LOGIN.
 IF session_user<>'empire_analytics_maintenance_login'
   OR current_user<>'empiredb_migrator'
 THEN RAISE EXCEPTION 'ANALYTICS055_TRUSTED_MAINTENANCE_LOGIN_REQUIRED'; END IF;
 IF p_tenant IS NULL OR p_property IS DISTINCT FROM 'empire-ai.co.uk'
   OR p_session_digest IS NULL OR
   p_session_digest !~ '^[a-f0-9]{64}$'
   OR p_reason NOT IN ('EXPIRED_RETENTION','VERIFIED_ERASURE_REQUEST')
   OR p_verification_reference_sha256 IS NULL
   OR p_verification_reference_sha256 !~ '^[a-f0-9]{64}$'
 THEN RAISE EXCEPTION 'ANALYTICS055_INVALID_BOUNDED_ERASURE_REQUEST'; END IF;
 IF p_verification_reference_sha256=p_session_digest THEN
   RAISE EXCEPTION 'ANALYTICS055_ERASURE_REFERENCE_MUST_NOT_BE_SESSION_DIGEST';
 END IF;

 SELECT * INTO target FROM public.empire_analytics_sessions
 WHERE tenant_id=p_tenant AND property_key=p_property
 AND session_digest=p_session_digest FOR UPDATE;
 IF NOT FOUND THEN
   RAISE EXCEPTION 'ANALYTICS055_SESSION_NOT_PRESENT_IN_TENANT_SCOPE';
 END IF;
 -- Proposed example expiry threshold only. Legal/policy approval
 -- is still REQUIRED before activation.
 IF p_reason='EXPIRED_RETENTION'
   AND target.expires_at>pg_catalog.clock_timestamp()-interval '7 days'
 THEN RAISE EXCEPTION 'ANALYTICS055_RETENTION_INTERVAL_NOT_REACHED'; END IF;
 -- VERIFIED_ERASURE_REQUEST means ONLY that the future restricted
 -- actor has verified a request independently; arbitrary SHA cannot
 -- substitute for that verification. No execution grant exists yet.

 DELETE FROM public.empire_analytics_event_receipts
 WHERE tenant_id=p_tenant AND property_key=p_property
 AND session_digest=p_session_digest;
 GET DIAGNOSTICS count_events=ROW_COUNT;

 DELETE FROM public.empire_analytics_consent_decisions
 WHERE tenant_id=p_tenant AND property_key=p_property
 AND session_digest=p_session_digest;
 GET DIAGNOSTICS count_decisions=ROW_COUNT;

 DELETE FROM public.empire_analytics_sessions
 WHERE tenant_id=p_tenant AND property_key=p_property
 AND session_digest=p_session_digest;
 GET DIAGNOSTICS count_sessions=ROW_COUNT;
 IF count_sessions<>1 THEN
  RAISE EXCEPTION 'ANALYTICS055_ERASURE_ATOMICITY_UNVERIFIED';
 END IF;

 INSERT INTO public.empire_analytics_erasure_audit(
  tenant_id,property_key,erasure_reason,verification_reference_sha256,
  sessions_erased,decisions_erased,events_erased,actor_role
 ) VALUES(
  p_tenant,p_property,p_reason,p_verification_reference_sha256,
  count_sessions,count_decisions,count_events,session_user
 ) RETURNING audit_id INTO issued_audit;

 RETURN QUERY SELECT issued_audit,count_sessions,count_decisions,count_events;
END;
$erasure$;

-- Audit is append-only, with one internally scoped owner-only insert policy.
CREATE TRIGGER empire_analytics_erasure_audit_immutable
 BEFORE UPDATE OR DELETE ON public.empire_analytics_erasure_audit
 FOR EACH ROW EXECUTE FUNCTION public.empire_analytics_immutable();
ALTER TABLE public.empire_analytics_erasure_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_analytics_erasure_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY empire_analytics_maint_audit_insert
 ON public.empire_analytics_erasure_audit FOR INSERT
 TO empiredb_migrator WITH CHECK (
  actor_role='empire_analytics_maintenance_login'
  AND sessions_erased=1
 );
CREATE POLICY empire_analytics_maint_audit_select
 ON public.empire_analytics_erasure_audit FOR SELECT
 TO empiredb_migrator USING (true);

REVOKE ALL ON TABLE public.empire_analytics_erasure_audit FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_analytics_erase_session(
 uuid,text,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_analytics_immutable() FROM PUBLIC;

-- Important: function still NOT executable by the future maintenance
-- LOGIN until a separate founder-approved identity/role migration.
DO $postcheck$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relname='empire_analytics_erasure_audit'
  AND c.relrowsecurity AND c.relforcerowsecurity
 ) THEN RAISE EXCEPTION 'ANALYTICS055_AUDIT_RLS_UNVERIFIED'; END IF;
 IF EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_analytics_maintenance_login'
 ) AND pg_catalog.has_function_privilege(
  'empire_analytics_maintenance_login',
  'public.empire_analytics_erase_session(uuid,text,text,text,text)',
  'EXECUTE'
 ) THEN RAISE EXCEPTION 'ANALYTICS055_UNAPPROVED_RUNTIME_GRANT_DETECTED'; END IF;
END;
$postcheck$;
COMMIT;
