-- Bounded account-level Revenue Truth projection.
--
-- Reads only canonical revenue_recognized commercial_events and returns
-- aggregate revenue/cost/gross-profit truth per entity. It cannot recognize
-- revenue, move funds, mutate fulfilment, or expose raw commercial payloads.
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_intelligence_materializer'
  ) THEN
    RAISE EXCEPTION 'empire_intelligence_materializer role missing';
  END IF;

  IF to_regclass('public.commercial_events') IS NULL THEN
    RAISE EXCEPTION 'commercial_events missing';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.empire_account_revenue_truth(
  p_entity_ids uuid[]
)
RETURNS TABLE (
  entity_id uuid,
  recognized_order_count bigint,
  recognized_revenue_cents bigint,
  actual_cost_cents bigint,
  realized_gp_cents bigint,
  latest_recognized_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF p_entity_ids IS NULL
     OR cardinality(p_entity_ids) < 1
     OR cardinality(p_entity_ids) > 100 THEN
    RAISE EXCEPTION 'entity id batch must contain 1..100 items';
  END IF;

  RETURN QUERY
  WITH ids AS (
    SELECT DISTINCT unnest(p_entity_ids) AS entity_id
  ),
  revenue AS (
    SELECT
      ce.entity_id,
      count(*)::bigint AS recognized_order_count,
      COALESCE(sum(ce.amount_cents),0)::bigint AS recognized_revenue_cents,
      COALESCE(sum(ce.cost_cents),0)::bigint AS actual_cost_cents,
      COALESCE(sum(ce.margin_cents),0)::bigint AS realized_gp_cents,
      max(ce.occurred_at) AS latest_recognized_at
    FROM public.commercial_events ce
    WHERE ce.event_type='revenue_recognized'
      AND ce.entity_id = ANY(p_entity_ids)
    GROUP BY ce.entity_id
  )
  SELECT
    i.entity_id,
    COALESCE(r.recognized_order_count,0)::bigint,
    COALESCE(r.recognized_revenue_cents,0)::bigint,
    COALESCE(r.actual_cost_cents,0)::bigint,
    COALESCE(r.realized_gp_cents,0)::bigint,
    r.latest_recognized_at
  FROM ids i
  LEFT JOIN revenue r ON r.entity_id=i.entity_id
  ORDER BY i.entity_id;
END;
$$;

REVOKE ALL ON FUNCTION public.empire_account_revenue_truth(uuid[])
FROM PUBLIC, anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.empire_account_revenue_truth(uuid[])
TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.empire_account_revenue_truth(uuid[]) IS
'Read-only account Revenue Truth projection from canonical revenue_recognized events. No revenue-recognition or accounting mutation authority.';

COMMIT;
