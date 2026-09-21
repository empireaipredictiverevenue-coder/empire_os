-- Bind prepared fulfilment orders to the exact governed commercial product.
--
-- offer_key is required to equal an active commercial_products.product_code.
-- This migration does not approve terms, set economics, move funds, fulfil an
-- order or recognize revenue.

CREATE OR REPLACE FUNCTION public.prepare_fulfilment_order_from_capacity(
  p_case_id uuid,
  p_actor text DEFAULT 'empire_closer_planner'::text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  x public.buyer_capacity_intakes%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
  v_offer_key text;
  v_product_id uuid;
BEGIN
  IF v_actor='' THEN
    RAISE EXCEPTION 'actor required';
  END IF;

  SELECT *
    INTO c
    FROM public.closer_cases
   WHERE id=p_case_id
   FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'closer case not found';
  END IF;

  IF c.state IN ('won','lost','paused') THEN
    RAISE EXCEPTION 'active closer case required';
  END IF;

  IF c.buyer_id IS NULL OR c.prospect_id IS NULL THEN
    RAISE EXCEPTION 'buyer and prospect binding required';
  END IF;

  IF c.fulfilment_order_id IS NOT NULL THEN
    SELECT *
      INTO o
      FROM public.fulfilment_orders
     WHERE id=c.fulfilment_order_id;

    IF FOUND THEN
      RETURN jsonb_build_object(
        'decision','existing',
        'fulfilment_order_id',o.id,
        'product_id',o.product_id,
        'state',o.state,
        'actual_revenue',false
      );
    END IF;
  END IF;

  SELECT trim(COALESCE(i.offer_key,''))
    INTO v_offer_key
    FROM public.outbound_intents i
   WHERE i.id=c.outbound_intent_id;

  IF COALESCE(v_offer_key,'')='' THEN
    RAISE EXCEPTION 'closer case requires canonical outbound offer_key';
  END IF;

  SELECT p.id
    INTO v_product_id
    FROM public.commercial_products p
   WHERE p.product_code=v_offer_key
     AND p.active IS TRUE
   LIMIT 1;

  IF v_product_id IS NULL THEN
    RAISE EXCEPTION
      'active commercial product not found for offer_key %',
      v_offer_key;
  END IF;

  SELECT *
    INTO x
    FROM public.buyer_capacity_intakes
   WHERE closer_case_id=c.id
   FOR UPDATE;

  IF NOT FOUND OR x.state<>'complete' THEN
    RAISE EXCEPTION 'complete buyer-stated capacity intake required';
  END IF;

  INSERT INTO public.fulfilment_orders(
    opportunity_id,
    product_id,
    prospect_id,
    entity_id,
    buyer_id,
    state,
    quantity,
    price_cents,
    acquisition_cost_cents,
    fulfilment_cost_cents,
    expected_margin_cents,
    delivery_payload,
    commercial_payload
  ) VALUES (
    c.opportunity_id,
    v_product_id,
    c.prospect_id,
    c.entity_id,
    c.buyer_id,
    'qualified',
    1,
    0,
    0,
    0,
    0,
    jsonb_build_object(
      'territory',x.territory,
      'daily_cap',x.daily_cap,
      'delivery_route',x.delivery_route,
      'delivery_reference',x.delivery_reference,
      'capacity_source','buyer_stated'
    ),
    jsonb_build_object(
      'buyer_capacity_intake_id',x.id,
      'offer_key',v_offer_key,
      'product_id',v_product_id,
      'product_code',v_offer_key,
      'capacity_evidence_state','buyer_stated_unverified',
      'binding_commercial_terms',false,
      'actual_revenue',false
    )
  )
  RETURNING * INTO o;

  UPDATE public.closer_cases
     SET fulfilment_order_id=o.id,
         updated_at=clock_timestamp()
   WHERE id=c.id;

  INSERT INTO public.closer_events(
    case_id,
    event_type,
    actor,
    payload
  ) VALUES (
    c.id,
    'fulfilment_order_prepared',
    v_actor,
    jsonb_build_object(
      'fulfilment_order_id',o.id,
      'product_id',v_product_id,
      'product_code',v_offer_key,
      'order_state',o.state,
      'buyer_capacity_intake_id',x.id,
      'binding_commercial_terms',false,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','prepared',
    'fulfilment_order_id',o.id,
    'product_id',v_product_id,
    'product_code',v_offer_key,
    'state',o.state,
    'buyer_capacity_intake_id',x.id,
    'binding_commercial_terms',false,
    'actual_revenue',false
  );
END;
$$;
