-- EmpireDB tenant reader foundation.
-- Migration: empiredb/018_tenant_context_foundation
-- Safety:
--   * candidate EmpireDB only; does not change canonical backend
--   * no existing rows are updated/backfilled
--   * NULL/unknown org ownership remains tenant-inaccessible
--   * tenant role is read-only on explicitly buyer-owned surfaces

SET ROLE empiredb_migrator;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'empiredb_tenant_reader'
  ) THEN
    RAISE EXCEPTION
      'empiredb_tenant_reader role missing; run runtime role bootstrap first';
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.empire_current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog
AS $$
  SELECT CASE
    WHEN NULLIF(
      btrim(current_setting('empire.tenant_id', true)),
      ''
    ) IS NULL
      THEN NULL
    ELSE current_setting('empire.tenant_id', true)::uuid
  END
$$;

REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
TO empiredb_tenant_reader;

-- The tenant reader receives SELECT only. Platform/runtime capability roles
-- retain their existing separate authority.
GRANT SELECT ON
  public.buyers,
  public.buyer_subscriptions,
  public.fulfilment_orders,
  public.commercial_events,
  public.commercial_evidence_registry
TO empiredb_tenant_reader;

ALTER TABLE public.buyers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.buyer_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fulfilment_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.commercial_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.commercial_evidence_registry ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS buyers_tenant_reader_select ON public.buyers;
CREATE POLICY buyers_tenant_reader_select
ON public.buyers
FOR SELECT
TO empiredb_tenant_reader
USING (
  org_id IS NOT NULL
  AND org_id = public.empire_current_tenant_id()
);

DROP POLICY IF EXISTS buyer_subscriptions_tenant_reader_select
ON public.buyer_subscriptions;
CREATE POLICY buyer_subscriptions_tenant_reader_select
ON public.buyer_subscriptions
FOR SELECT
TO empiredb_tenant_reader
USING (
  EXISTS (
    SELECT 1
    FROM public.buyers b
    WHERE b.id = buyer_subscriptions.buyer_id
      AND b.org_id IS NOT NULL
      AND b.org_id = public.empire_current_tenant_id()
  )
);

DROP POLICY IF EXISTS fulfilment_orders_tenant_reader_select
ON public.fulfilment_orders;
CREATE POLICY fulfilment_orders_tenant_reader_select
ON public.fulfilment_orders
FOR SELECT
TO empiredb_tenant_reader
USING (
  buyer_id IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM public.buyers b
    WHERE b.id = fulfilment_orders.buyer_id
      AND b.org_id IS NOT NULL
      AND b.org_id = public.empire_current_tenant_id()
  )
);

DROP POLICY IF EXISTS commercial_events_tenant_reader_select
ON public.commercial_events;
CREATE POLICY commercial_events_tenant_reader_select
ON public.commercial_events
FOR SELECT
TO empiredb_tenant_reader
USING (
  buyer_id IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM public.buyers b
    WHERE b.id = commercial_events.buyer_id
      AND b.org_id IS NOT NULL
      AND b.org_id = public.empire_current_tenant_id()
  )
);

DROP POLICY IF EXISTS commercial_evidence_registry_tenant_reader_select
ON public.commercial_evidence_registry;
CREATE POLICY commercial_evidence_registry_tenant_reader_select
ON public.commercial_evidence_registry
FOR SELECT
TO empiredb_tenant_reader
USING (
  buyer_id IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM public.buyers b
    WHERE b.id = commercial_evidence_registry.buyer_id
      AND b.org_id IS NOT NULL
      AND b.org_id = public.empire_current_tenant_id()
  )
);

COMMENT ON FUNCTION public.empire_current_tenant_id() IS
  'Trusted transaction-local tenant context used by read-only tenant RLS. Missing context returns NULL and fails closed.';

RESET ROLE;
