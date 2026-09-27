-- Canonical bounded Revenue Pulse window reader.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_revenue_pulse_window(
  p_start timestamptz,
  p_end timestamptz
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  v_acquisitions bigint;
  v_qualified bigint;
  v_reviews bigint;
  v_delivered bigint;
  v_replies bigint;
  v_terms bigint;
  v_payments bigint;
  v_fulfilments bigint;
  v_revenue bigint;
  v_gp bigint;
BEGIN
  IF p_start IS NULL OR p_end IS NULL OR p_end <= p_start THEN
    RAISE EXCEPTION 'valid pulse window required';
  END IF;
  IF p_end - p_start > interval '31 days' THEN
    RAISE EXCEPTION 'pulse window exceeds 31 days';
  END IF;

  SELECT count(*) INTO v_acquisitions
  FROM public.prospect_acquisitions
  WHERE created_at >= p_start AND created_at < p_end;

  SELECT count(*) INTO v_qualified
  FROM public.prospect_qualifications
  WHERE status='scored'
    AND scored_at >= p_start AND scored_at < p_end;

  SELECT count(*) INTO v_reviews
  FROM public.buyer_candidate_reviews r
  WHERE r.status='approved'
    AND r.reviewed_at >= p_start AND r.reviewed_at < p_end
    AND COALESCE(lower(r.evidence->>'outreach_ready'),'false')='true'
    AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(
        CASE
          WHEN jsonb_typeof(r.evidence->'verified_contacts')='array'
          THEN r.evidence->'verified_contacts'
          ELSE '[]'::jsonb
        END
      ) c(item)
      WHERE c.item->'bound_to_decision_maker'='true'::jsonb
        AND c.item->'is_valid'='true'::jsonb
        AND trim(COALESCE(c.item->>'email',''))<>''
    );

  SELECT count(DISTINCT intent_id) INTO v_delivered
  FROM public.outbound_events
  WHERE event_type='delivered'
    AND occurred_at >= p_start AND occurred_at < p_end;

  SELECT count(*) INTO v_replies
  FROM public.outbound_replies
  WHERE classification IN ('positive','question','objection')
    AND received_at >= p_start AND received_at < p_end;

  SELECT count(*) INTO v_terms
  FROM public.commercial_terms_reviews
  WHERE proposed_at >= p_start AND proposed_at < p_end;

  SELECT count(*) INTO v_payments
  FROM public.bsc_payment_evidence
  WHERE verified_at >= p_start AND verified_at < p_end;

  SELECT count(*) INTO v_fulfilments
  FROM public.fulfilment_orders
  WHERE delivered_at IS NOT NULL
    AND delivered_at >= p_start AND delivered_at < p_end;

  SELECT
    COALESCE(sum(COALESCE(amount_cents,0)),0),
    COALESCE(sum(COALESCE(margin_cents,0)),0)
  INTO v_revenue,v_gp
  FROM public.commercial_events
  WHERE event_type='revenue_recognized'
    AND occurred_at >= p_start AND occurred_at < p_end;

  RETURN jsonb_build_object(
    'start_at',p_start,
    'end_at',p_end,
    'acquisitions',v_acquisitions,
    'qualified',v_qualified,
    'buyer_reviews',v_reviews,
    'delivered_outreach',v_delivered,
    'commercial_replies',v_replies,
    'commercial_terms',v_terms,
    'verified_payments',v_payments,
    'fulfilments',v_fulfilments,
    'recognized_revenue_cents',v_revenue,
    'realized_gp_cents',v_gp,
    'actual_revenue',v_revenue>0,
    'execution_authority','none'
  );
END;
$$;

REVOKE ALL ON FUNCTION public.get_revenue_pulse_window(
  timestamptz,timestamptz
) FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.get_revenue_pulse_window(
  timestamptz,timestamptz
) TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.get_revenue_pulse_window(timestamptz,timestamptz)
IS 'Bounded read-only canonical Revenue Pulse window; no payment, revenue, accounting or execution mutation.';

COMMIT;
