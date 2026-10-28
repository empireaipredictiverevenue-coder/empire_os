-- EMPIREDB CRM EXACT HANDOFF — DESIGN CANDIDATE ONLY, HELD
-- NOT A MIGRATION. DO NOT RUN/APPLY without founder approval, CRM owner review,
-- security test fixture, rollback plan and independent production privilege audit.
--
-- The CRM reader must NEVER get direct SELECT on prospect_entity_links,
-- tenant_business_entity_bindings, commercial_events or fulfilment_orders.
-- Return only an exact matching tenant-safe UUID receipt; never customer PII.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout='8s';
SET LOCAL lock_timeout='3s';

DO $guard$
DECLARE obj text;
BEGIN
 IF current_database() NOT IN ('empiredb','crm_exact_lineage_fixture') THEN
   RAISE EXCEPTION 'CRM_LINEAGE_WRONG_DATABASE';
 END IF;
 IF pg_catalog.to_regprocedure(
      'public.empire_crm_exact_lineage(uuid,uuid,uuid,text)') IS NOT NULL THEN
   RAISE EXCEPTION 'CRM_LINEAGE_ALREADY_EXISTS_RECONCILE';
 END IF;
 IF pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
    OR pg_catalog.to_regprocedure('public.empire_crm_prospect_authorized(uuid)') IS NULL
 THEN RAISE EXCEPTION 'CRM_LINEAGE_MISSING_TRUSTED_TENANT_FUNCTION';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_revenue_crm_reader'
    AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
    AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN RAISE EXCEPTION 'CRM_LINEAGE_UNSAFE_READER_ROLE'; END IF;
 IF pg_catalog.has_table_privilege('empire_revenue_crm_reader',
         'public.prospect_entity_links','SELECT')
    OR pg_catalog.has_table_privilege('empire_revenue_crm_reader',
         'public.tenant_business_entity_bindings','SELECT')
    OR pg_catalog.has_table_privilege('empire_revenue_crm_reader',
         'public.commercial_events','SELECT')
    OR pg_catalog.has_table_privilege('empire_revenue_crm_reader',
         'public.fulfilment_orders','SELECT')
 THEN RAISE EXCEPTION 'CRM_LINEAGE_RAW_TABLE_GRANT_PROHIBITED'; END IF;
 FOREACH obj IN ARRAY ARRAY[
  'public.prospect_entity_links','public.tenant_business_entity_bindings',
  'public.business_entity_conflicts','public.gtm_opportunities',
  'public.commercial_events','public.fulfilment_orders','public.buyers'
 ] LOOP
    IF pg_catalog.to_regclass(obj) IS NULL
       OR NOT pg_catalog.has_table_privilege(current_user,obj,'SELECT')
    THEN RAISE EXCEPTION 'CRM_LINEAGE_OWNER_SOURCE_PRIVILEGE_REQUIRED: %',obj;
    END IF;
 END LOOP;
END;
$guard$;

CREATE FUNCTION public.empire_crm_exact_lineage(
  p_prospect uuid, p_opportunity uuid, p_receipt uuid, p_kind text
)
RETURNS TABLE (
  prospect_id uuid, entity_id uuid, tenant_id uuid, opportunity_id uuid,
  evidence_id uuid, evidence_kind text, buyer_id uuid
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $lineage$
WITH verified_scope AS (
  SELECT l.prospect_id, l.entity_id, b.tenant_id
  FROM public.prospect_entity_links l
  JOIN public.tenant_business_entity_bindings b ON b.entity_id=l.entity_id
  WHERE l.prospect_id=p_prospect
    AND l.active IS TRUE
    AND l.match_method IN (
      'exact_primary_domain','verified_source_identity',
      'first_party_official_match','source_and_official_registry')
    AND l.evidence ? 'source_ref'
    AND pg_catalog.length(pg_catalog.btrim(l.evidence->>'source_ref')) > 0
    AND b.tenant_id=public.empire_current_tenant_id()
    AND b.active IS TRUE
    AND b.binding_kind IN ('owned','managed','customer','prospect')
    AND b.valid_from <= CURRENT_TIMESTAMP
    AND (b.valid_until IS NULL OR b.valid_until>CURRENT_TIMESTAMP)
    AND pg_catalog.length(pg_catalog.btrim(b.evidence_ref)) > 0
    AND public.empire_crm_prospect_authorized(l.prospect_id)
    AND NOT EXISTS (
      SELECT 1 FROM public.business_entity_conflicts c
      WHERE c.prospect_id=l.prospect_id AND c.entity_id=l.entity_id
        AND c.resolution_state IS DISTINCT FROM 'resolved'
    )
    AND pg_catalog.pg_has_role(
      session_user,'empire_revenue_crm_reader'::pg_catalog.regrole,'MEMBER')
  GROUP BY l.prospect_id,l.entity_id,b.tenant_id
  HAVING count(*)=1
)
SELECT s.prospect_id,s.entity_id,s.tenant_id,g.id,p_receipt,p_kind,
  CASE WHEN p_kind='event' THEN (
    SELECT e.buyer_id FROM public.commercial_events e
    WHERE e.id=p_receipt AND e.opportunity_id=g.id
      AND e.prospect_id=s.prospect_id AND e.entity_id=s.entity_id
  ) ELSE (
    SELECT o.buyer_id FROM public.fulfilment_orders o
    WHERE o.id=p_receipt AND o.opportunity_id=g.id
      AND o.prospect_id=s.prospect_id AND o.entity_id=s.entity_id
  ) END
FROM verified_scope s
JOIN public.gtm_opportunities g ON g.id=p_opportunity
WHERE p_prospect IS NOT NULL AND p_opportunity IS NOT NULL
  AND p_receipt IS NOT NULL AND p_kind IN ('event','order')
  AND (
    (p_kind='event' AND EXISTS (
      SELECT 1 FROM public.commercial_events e
      WHERE e.id=p_receipt AND e.opportunity_id=g.id
        AND e.prospect_id=s.prospect_id AND e.entity_id=s.entity_id
        AND e.buyer_id IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM public.buyers buyer
          WHERE buyer.id=e.buyer_id AND buyer.org_id=s.tenant_id
        )
        AND (e.fulfilment_order_id IS NULL OR EXISTS (
          SELECT 1 FROM public.fulfilment_orders linked_order
          WHERE linked_order.id=e.fulfilment_order_id
            AND linked_order.opportunity_id=e.opportunity_id
            AND linked_order.prospect_id=e.prospect_id
            AND linked_order.entity_id=e.entity_id
            AND linked_order.buyer_id=e.buyer_id
        ))
    ))
    OR
    (p_kind='order' AND EXISTS (
      SELECT 1 FROM public.fulfilment_orders o
      WHERE o.id=p_receipt AND o.opportunity_id=g.id
        AND o.prospect_id=s.prospect_id AND o.entity_id=s.entity_id
        AND o.buyer_id IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM public.buyers buyer
          WHERE buyer.id=o.buyer_id AND buyer.org_id=s.tenant_id
        )
    ))
  )
$lineage$;

REVOKE ALL ON FUNCTION public.empire_crm_exact_lineage(uuid,uuid,uuid,text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_crm_exact_lineage(uuid,uuid,uuid,text)
  TO empire_revenue_crm_reader;

COMMENT ON FUNCTION public.empire_crm_exact_lineage(uuid,uuid,uuid,text) IS
  'Read-only, exact signed-tenant GTM event/order continuity, not buyer acceptance, fulfilment, price, settlement, marketing authority or realised revenue.';
COMMIT;
