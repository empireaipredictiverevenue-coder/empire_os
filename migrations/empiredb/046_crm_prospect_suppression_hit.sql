-- EmpireDB 046 — exact-tenant prospect suppression HIT (no contact disclosure).
-- Founder approval received 2026-10-10. Apply only using vetted release script.
-- No direct global suppression grants, no CRM reader role changes or sends.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $preflight$
BEGIN
 IF current_database() NOT IN ('empiredb','crm_suppression_fixture') THEN
   RAISE EXCEPTION 'CRM046_WRONG_DATABASE';
 END IF;
 IF pg_catalog.to_regprocedure('public.empire_crm_prospect_suppression_hit(uuid,text)') IS NOT NULL THEN
   RAISE EXCEPTION 'CRM046_ALREADY_EXISTS_RECONCILE';
 END IF;
 IF pg_catalog.to_regprocedure('public.empire_crm_prospect_authorized(uuid)') IS NULL
    OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
 THEN
   RAISE EXCEPTION 'CRM046_MISSING_TENANT_AUTHORITY';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_revenue_crm_reader'
     AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
     AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN
   RAISE EXCEPTION 'CRM046_UNSAFE_READER_ROLE';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_proc p
   JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
   WHERE p.oid=pg_catalog.to_regprocedure('public.empire_crm_prospect_authorized(uuid)')
     AND p.prosecdef AND p.provolatile='s'
     AND owner.rolname='empiredb_migrator'
 ) OR NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_proc p
   JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
   WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
     AND p.prosecdef AND p.provolatile='s'
     AND owner.rolname='empiredb_migrator'
 ) THEN
   RAISE EXCEPTION 'CRM046_UNVERIFIED_TENANT_FUNCTION_PROVENANCE';
 END IF;
 IF pg_catalog.to_regclass('public.prospects') IS NULL
    OR pg_catalog.to_regclass('public.outbound_suppressions') IS NULL
    OR NOT pg_catalog.has_column_privilege(current_user,'public.prospects','phone','SELECT')
    OR NOT pg_catalog.has_table_privilege(current_user,'public.outbound_suppressions','SELECT')
 THEN
   RAISE EXCEPTION 'CRM046_CANONICAL_SOURCES_UNAVAILABLE';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_class
   WHERE oid='public.prospects'::pg_catalog.regclass AND relrowsecurity
 ) THEN
   RAISE EXCEPTION 'CRM046_PROSPECT_RLS_MISSING';
 END IF;
END;
$preflight$;

CREATE FUNCTION public.empire_crm_prospect_suppression_hit(
    p_prospect_id uuid, p_channel text
)
RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = ''
AS $body$
DECLARE
    v_phone text;
BEGIN
    IF p_prospect_id IS NULL
      OR p_channel IS DISTINCT FROM 'sms'
      OR public.empire_current_tenant_id() IS NULL
      OR NOT pg_catalog.pg_has_role(
        session_user, 'empire_revenue_crm_reader'::pg_catalog.regrole, 'MEMBER'
      )
      OR NOT public.empire_crm_prospect_authorized(p_prospect_id)
    THEN
        RETURN 'UNKNOWN';
    END IF;

    SELECT p.phone INTO v_phone
    FROM public.prospects p
    WHERE p.id = p_prospect_id;

    -- Exact, unambiguous international number only.
    IF v_phone IS NULL OR v_phone !~ '^[+][1-9][0-9]{7,14}$' THEN
        RETURN 'UNKNOWN';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_suppressions s
        WHERE s.normalized_contact = v_phone
          AND s.contact_type = 'phone'
    ) THEN
        RETURN 'SUPPRESSED';
    END IF;
    -- An absent hit is NEVER a positive contact/sending clearance.
    RETURN 'UNKNOWN';
END;
$body$;

REVOKE ALL ON FUNCTION public.empire_crm_prospect_suppression_hit(uuid,text)
 FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_crm_prospect_suppression_hit(uuid,text)
 TO empire_revenue_crm_reader;
COMMENT ON FUNCTION public.empire_crm_prospect_suppression_hit(uuid,text) IS
 'OBSERVE only; tenant-authenticated exact-prospect SMS suppression HIT or UNKNOWN; never contact, opt-in, subscription, marketing/sending clearance.';
COMMIT;
