-- STAGED, NOT APPLIED.
-- Extend the canonical commercial outcome feedback contract with the
-- fulfilment-order creation timestamp required by Predictive Intelligence.
-- This migration does not create revenue, mutate commercial facts, send
-- outreach, move funds or widen execution authority.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_commercial_outcome_feedback(
  p_limit integer DEFAULT 100
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE
  result jsonb;
BEGIN
  IF p_limit IS NULL OR p_limit<1 OR p_limit>1000 THEN
    RAISE EXCEPTION 'feedback limit must be 1-1000';
  END IF;

  SELECT COALESCE(jsonb_agg(row_data ORDER BY updated_at DESC), '[]'::jsonb)
  INTO result
  FROM (
    SELECT
      o.updated_at,
      jsonb_build_object(
        'fulfilment_order_id',o.id,
        'opportunity_id',o.opportunity_id,
        'prospect_id',o.prospect_id,
        'entity_id',o.entity_id,
        'buyer_id',o.buyer_id,
        'product_id',o.product_id,
        'state',o.state,
        'price_cents',o.price_cents,
        'acquisition_cost_cents',o.acquisition_cost_cents,
        'fulfilment_cost_cents',o.fulfilment_cost_cents,
        'actual_margin_cents',o.actual_margin_cents,
        'fulfilment_created_at',o.created_at,
        'delivery_outcome',co.delivery_outcome,
        'conversion_outcome',co.conversion_outcome,
        'buyer_satisfaction',co.buyer_satisfaction,
        'outcome_recorded_at',co.recorded_at,
        'actual_revenue',ce.id IS NOT NULL,
        'actual_revenue_cents',COALESCE(ce.amount_cents,0),
        'actual_cost_cents',COALESCE(ce.cost_cents,0),
        'gross_profit_cents',COALESCE(ce.margin_cents,0),
        'revenue_recognized_at',ce.occurred_at,
        'previous_purchase',(ce.id IS NOT NULL),
        'booked',(co.conversion_outcome IN ('booked','won')),
        'converted',(co.conversion_outcome='won')
      ) AS row_data
    FROM public.fulfilment_orders o
    LEFT JOIN LATERAL (
      SELECT x.*
        FROM public.commercial_outcomes x
       WHERE x.fulfilment_order_id=o.id
       ORDER BY x.recorded_at DESC,x.id DESC
       LIMIT 1
    ) co ON true
    LEFT JOIN LATERAL (
      SELECT x.*
        FROM public.commercial_events x
       WHERE x.idempotency_key='revenue:'||o.id::text||':v1'
       LIMIT 1
    ) ce ON true
    WHERE co.id IS NOT NULL OR ce.id IS NOT NULL
    ORDER BY o.updated_at DESC
    LIMIT p_limit
  ) q;

  RETURN result;
END;
$$;

REVOKE ALL ON FUNCTION public.get_commercial_outcome_feedback(integer)
  FROM PUBLIC,anon,authenticated,empire_outcome_recorder,empire_revenue_recognizer;
GRANT EXECUTE ON FUNCTION public.get_commercial_outcome_feedback(integer)
  TO service_role;

COMMENT ON FUNCTION public.get_commercial_outcome_feedback(integer) IS
'Canonical Phase 3F read model for outcome learning, including fulfilment creation time for verified time-to-revenue cohorts.';

COMMIT;
