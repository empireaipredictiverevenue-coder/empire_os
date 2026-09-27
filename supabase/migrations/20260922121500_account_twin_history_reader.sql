-- Bounded account-twin commercial history reader.
--
-- Exposes only non-message-body, non-recipient commercial lifecycle metadata
-- through a SECURITY DEFINER function. Raw commercial tables remain ungranted
-- to empire_intelligence_materializer.
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_intelligence_materializer'
  ) THEN
    RAISE EXCEPTION 'empire_intelligence_materializer role missing';
  END IF;

  IF to_regclass('public.outbound_intents') IS NULL
     OR to_regclass('public.outbound_replies') IS NULL
     OR to_regclass('public.fulfilment_orders') IS NULL
     OR to_regclass('public.commercial_terms_reviews') IS NULL
     OR to_regclass('public.bsc_payment_requests') IS NULL
     OR to_regclass('public.bsc_payment_evidence') IS NULL
     OR to_regclass('public.commercial_outcomes') IS NULL THEN
    RAISE EXCEPTION 'account twin commercial history dependency missing';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.empire_account_twin_history(
  p_entity_ids uuid[]
)
RETURNS TABLE (
  entity_id uuid,
  history jsonb
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
  )
  SELECT
    i.entity_id,
    jsonb_build_object(
      'outbound_intents',
      COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', oi.id,
            'prospect_id', oi.prospect_id,
            'buyer_id', oi.buyer_id,
            'opportunity_id', oi.opportunity_id,
            'channel', oi.channel,
            'offer_key', oi.offer_key,
            'status', oi.status,
            'approved_at', oi.approved_at,
            'created_at', oi.created_at,
            'updated_at', oi.updated_at
          )
          ORDER BY oi.created_at, oi.id
        )
        FROM public.outbound_intents oi
        WHERE oi.entity_id=i.entity_id
      ), '[]'::jsonb),

      'outbound_replies',
      COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', r.id,
            'intent_id', r.intent_id,
            'classification', r.classification,
            'confidence', r.confidence,
            'received_at', r.received_at,
            'classified_at', r.classified_at
          )
          ORDER BY r.received_at, r.id
        )
        FROM public.outbound_replies r
        JOIN public.outbound_intents oi
          ON oi.id=r.intent_id
        WHERE oi.entity_id=i.entity_id
      ), '[]'::jsonb),

      'fulfilment_orders',
      COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', fo.id,
            'opportunity_id', fo.opportunity_id,
            'product_id', fo.product_id,
            'prospect_id', fo.prospect_id,
            'buyer_id', fo.buyer_id,
            'state', fo.state,
            'quantity', fo.quantity,
            'price_cents', fo.price_cents,
            'acquisition_cost_cents', fo.acquisition_cost_cents,
            'fulfilment_cost_cents', fo.fulfilment_cost_cents,
            'expected_margin_cents', fo.expected_margin_cents,
            'actual_margin_cents', fo.actual_margin_cents,
            'created_at', fo.created_at,
            'updated_at', fo.updated_at,
            'delivered_at', fo.delivered_at,
            'confirmed_at', fo.confirmed_at,
            'paid_at', fo.paid_at,
            'settled_at', fo.settled_at,
            'outcome_at', fo.outcome_at
          )
          ORDER BY fo.created_at, fo.id
        )
        FROM public.fulfilment_orders fo
        WHERE fo.entity_id=i.entity_id
      ), '[]'::jsonb),

      'terms_reviews',
      COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', tr.id,
            'fulfilment_order_id', tr.fulfilment_order_id,
            'status', tr.status,
            'price_cents', tr.price_cents,
            'acquisition_cost_cents', tr.acquisition_cost_cents,
            'fulfilment_cost_cents', tr.fulfilment_cost_cents,
            'expected_margin_cents', tr.expected_margin_cents,
            'commercial_terms_sha256', tr.commercial_terms_sha256,
            'proposed_at', tr.proposed_at,
            'decided_at', tr.decided_at
          )
          ORDER BY tr.proposed_at, tr.id
        )
        FROM public.commercial_terms_reviews tr
        JOIN public.fulfilment_orders fo
          ON fo.id=tr.fulfilment_order_id
        WHERE fo.entity_id=i.entity_id
      ), '[]'::jsonb),

      'payment_requests',
      COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', pr.id,
            'buyer_id', pr.buyer_id,
            'fulfilment_order_id', pr.fulfilment_order_id,
            'amount_usdt', pr.amount_usdt,
            'status', pr.status,
            'approved_at', pr.approved_at,
            'expires_at', pr.expires_at,
            'created_at', pr.created_at,
            'settlement_mode', pr.settlement_mode
          )
          ORDER BY pr.created_at, pr.id
        )
        FROM public.bsc_payment_requests pr
        JOIN public.fulfilment_orders fo
          ON fo.id=pr.fulfilment_order_id
        WHERE fo.entity_id=i.entity_id
      ), '[]'::jsonb),

      'payment_evidence',
      COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', pe.id,
            'request_id', pe.request_id,
            'fulfilment_order_id', pe.fulfilment_order_id,
            'chain_id', pe.chain_id,
            'transaction_hash', pe.transaction_hash,
            'amount_raw', pe.amount_raw,
            'confirmations', pe.confirmations,
            'verified_at', pe.verified_at,
            'recorded_at', pe.recorded_at
          )
          ORDER BY pe.verified_at, pe.id
        )
        FROM public.bsc_payment_evidence pe
        JOIN public.fulfilment_orders fo
          ON fo.id=pe.fulfilment_order_id
        WHERE fo.entity_id=i.entity_id
      ), '[]'::jsonb),

      'commercial_outcomes',
      COALESCE((
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', co.id,
            'fulfilment_order_id', co.fulfilment_order_id,
            'delivery_outcome', co.delivery_outcome,
            'conversion_outcome', co.conversion_outcome,
            'buyer_satisfaction', co.buyer_satisfaction,
            'evidence_kind', co.evidence_kind,
            'evidence_reference', co.evidence_reference,
            'recorded_at', co.recorded_at
          )
          ORDER BY co.recorded_at, co.id
        )
        FROM public.commercial_outcomes co
        JOIN public.fulfilment_orders fo
          ON fo.id=co.fulfilment_order_id
        WHERE fo.entity_id=i.entity_id
      ), '[]'::jsonb)
    ) AS history
  FROM ids i;
END;
$$;

REVOKE ALL ON FUNCTION public.empire_account_twin_history(uuid[])
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.empire_account_twin_history(uuid[])
TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.empire_account_twin_history(uuid[]) IS
'Bounded read-only commercial lifecycle projection for Account/Buyer Digital Twin. Excludes recipients and message bodies; grants no raw-table access or mutation authority.';

COMMIT;
