-- EmpireDB 040 — Dedicated tenant-safe Revenue CRM read projections.
-- PREPARED ONLY. DO NOT APPLY without explicit founder migration approval.
-- Creates the missing NOLOGIN NOINHERIT role only from a privileged DBA
-- inside the same rollbackable transaction; no login receives membership.
-- No account login membership, send, payment, write, tenant-binding changes.
BEGIN;

-- The role bootstrap is part of this one transaction. A privileged DBA may
-- create the missing NOLOGIN role; the database login gets NO membership.
-- If not privileged, fail before touching a view/policy/function.
DO $role_bootstrap$
BEGIN
 IF current_database() <> 'empiredb'
    AND current_database() <> 'crm_release_fixture' THEN
   RAISE EXCEPTION 'invalid EmpireDB migration target';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_revenue_crm_reader'
 ) THEN
   IF NOT EXISTS (
     SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname=current_user AND rolsuper
   ) THEN
     RAISE EXCEPTION 'privileged DBA required for missing CRM reader role';
   END IF;
   CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT
     NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
 END IF;
END;
$role_bootstrap$;

SET LOCAL ROLE empiredb_migrator;

DO $guard$
DECLARE obj text;
BEGIN
 IF current_database() <> 'empiredb' AND current_database() <> 'crm_release_fixture' THEN
   RAISE EXCEPTION 'invalid database for Revenue CRM migration';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_revenue_crm_reader'
     AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
     AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolinherit
 ) THEN
   RAISE EXCEPTION 'dedicated NOLOGIN CRM reader role missing or unsafe';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_proc p
   JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
   WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
     AND p.prosecdef IS TRUE AND p.provolatile='s'
     AND owner.rolname='empiredb_migrator'
 ) THEN
   RAISE EXCEPTION 'trusted stable SECURITY DEFINER tenant resolver required';
 END IF;
 IF pg_catalog.has_table_privilege(
      'empire_revenue_crm_reader','public.prospect_entity_links','SELECT'
    ) OR pg_catalog.has_table_privilege(
      'empire_revenue_crm_reader','public.tenant_business_entity_bindings','SELECT'
    ) THEN
   RAISE EXCEPTION 'CRM reader must not read raw cross-tenant bindings';
 END IF;
 FOREACH obj IN ARRAY ARRAY[
   'public.prospects','public.buyers','public.prospect_entity_links',
   'public.tenant_business_entity_bindings'
 ] LOOP
   IF pg_catalog.to_regclass(obj) IS NULL
      OR NOT pg_catalog.has_table_privilege(current_user,obj,'SELECT') THEN
     RAISE EXCEPTION 'CRM owner-source privileges or object missing: %',obj;
   END IF;
 END LOOP;
 IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class
    WHERE oid='public.prospects'::pg_catalog.regclass AND relrowsecurity
 ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class
    WHERE oid='public.buyers'::pg_catalog.regclass AND relrowsecurity
 ) THEN
    RAISE EXCEPTION 'pre-existing prospects/buyers RLS required';
 END IF;
 IF pg_catalog.to_regclass('public.revenue_crm_prospects') IS NOT NULL
    OR pg_catalog.to_regclass('public.revenue_crm_buyers') IS NOT NULL
    OR pg_catalog.to_regprocedure('public.empire_crm_prospect_authorized(uuid)') IS NOT NULL THEN
    RAISE EXCEPTION 'CRM objects already exist: reconcile, do not overwrite';
 END IF;
END;
$guard$;

-- Runs using the guarded migrator owner's SELECT privileges.
-- Caller's trusted tenant always comes from session_user, not parameters.
-- Never grant direct access to the global cross-tenant binding table.
CREATE FUNCTION public.empire_crm_prospect_authorized(p_prospect_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $policy$
  SELECT
     public.empire_current_tenant_id() IS NOT NULL
     AND (
       SELECT count(*) = 1
       FROM public.prospect_entity_links link
       JOIN public.tenant_business_entity_bindings binding
         ON binding.entity_id=link.entity_id
       WHERE link.prospect_id=p_prospect_id
         AND link.active IS TRUE
         AND link.evidence IS NOT NULL
         AND link.evidence <> '{}'::jsonb
         AND binding.tenant_id=public.empire_current_tenant_id()
         AND binding.active IS TRUE
         AND binding.binding_kind IN ('owned','managed','customer','prospect')
         AND binding.evidence_ref IS NOT NULL
         AND length(btrim(binding.evidence_ref)) > 0
         AND binding.valid_from <= CURRENT_TIMESTAMP
         AND (binding.valid_until IS NULL OR binding.valid_until>CURRENT_TIMESTAMP)
     )
$policy$;

REVOKE ALL ON FUNCTION public.empire_crm_prospect_authorized(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_crm_prospect_authorized(uuid)
  TO empire_revenue_crm_reader;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
  TO empire_revenue_crm_reader;

-- Existing RLS for other service roles is not modified.
CREATE POLICY crm_prospect_scope_read
ON public.prospects FOR SELECT TO empire_revenue_crm_reader
USING (public.empire_crm_prospect_authorized(id));

CREATE POLICY crm_buyer_scope_read
ON public.buyers FOR SELECT TO empire_revenue_crm_reader
USING (
  org_id IS NOT NULL AND public.empire_current_tenant_id() IS NOT NULL
  AND org_id=public.empire_current_tenant_id()
);

-- Only necessary base columns; no private contact fields.
GRANT USAGE ON SCHEMA public TO empire_revenue_crm_reader;
GRANT SELECT (id,business_name,niche,metro,status)
ON public.prospects TO empire_revenue_crm_reader;
GRANT SELECT (
  id,org_id,buyer_name,niche,metro,status,is_active,commercial_activation_state,
  daily_cap,calls_today,per_lead_rate,capacity_verified_at,delivery_verified_at,
  commercial_terms_verified_at
) ON public.buyers TO empire_revenue_crm_reader;

-- Contextual prospect/closer fields remain NULL (not fabrications);
-- they require separate independently proven joins and tenant-safe grants.
CREATE VIEW public.revenue_crm_prospects
WITH (security_invoker=true, security_barrier=true) AS
SELECT
  public.empire_current_tenant_id() AS tenant_id,
  p.id AS prospect_id,
  p.business_name,p.niche,p.metro,p.status AS prospect_status,
  NULL::uuid AS conversation_id,
  NULL::text AS conversation_channel,
  NULL::text AS conversation_state,
  NULL::timestamptz AS conversation_updated_at,
  NULL::uuid AS closer_case_id,
  NULL::text AS closer_state,
  NULL::timestamptz AS closer_updated_at,
  NULL::uuid AS fulfilment_order_id,
  NULL::text AS fulfilment_state,
  NULL::timestamptz AS fulfilment_updated_at,
  NULL::bigint AS price_cents,
  NULL::uuid AS buyer_id,
  NULL::text AS buyer_activation_state,
  NULL::integer AS buyer_available_capacity,
  NULL::timestamptz AS buyer_capacity_verified_at,
  NULL::numeric AS deal_probability
FROM public.prospects p
WHERE public.empire_crm_prospect_authorized(p.id);

CREATE VIEW public.revenue_crm_buyers
WITH (security_invoker=true, security_barrier=true) AS
SELECT
  b.org_id AS tenant_id,
  b.id AS buyer_id,
  b.buyer_name,b.niche,b.metro,b.status AS buyer_status,b.is_active,
  b.commercial_activation_state,
  b.daily_cap,b.calls_today,
  NULL::integer AS available_capacity,
  b.per_lead_rate,b.capacity_verified_at,
  b.delivery_verified_at,b.commercial_terms_verified_at
FROM public.buyers b
WHERE b.org_id=public.empire_current_tenant_id()
  AND b.org_id IS NOT NULL;

REVOKE ALL ON public.revenue_crm_prospects,public.revenue_crm_buyers FROM PUBLIC;
GRANT SELECT ON public.revenue_crm_prospects,public.revenue_crm_buyers
  TO empire_revenue_crm_reader;

COMMENT ON VIEW public.revenue_crm_prospects IS
  'Read-only tenant-scoped prospect identifiers; unknown closer and fulfilment fields remain NULL.';
COMMENT ON VIEW public.revenue_crm_buyers IS
  'Read-only buyer projection, tenant bound by org_id; available capacity unverified.';

COMMIT;
