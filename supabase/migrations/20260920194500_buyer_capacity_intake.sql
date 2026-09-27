-- Buyer-stated capacity intake for genuine closer conversations.
BEGIN;

CREATE TABLE IF NOT EXISTS public.buyer_capacity_intakes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  closer_case_id uuid NOT NULL UNIQUE REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  buyer_id uuid NOT NULL REFERENCES public.buyers(id) ON DELETE RESTRICT,
  source_reply_ids uuid[] NOT NULL DEFAULT '{}'::uuid[],
  territory text,
  daily_cap integer,
  delivery_route text,
  delivery_reference text,
  state text NOT NULL DEFAULT 'partial',
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (daily_cap IS NULL OR (daily_cap >= 1 AND daily_cap <= 10000)),
  CHECK (delivery_route IS NULL OR delivery_route IN ('email','webhook','phone','api')),
  CHECK (state IN ('partial','complete'))
);

ALTER TABLE public.buyer_capacity_intakes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.buyer_capacity_intakes
  FROM PUBLIC,anon,authenticated,service_role,
       empire_closer_observer,empire_closer_planner,empire_closer_approver;
GRANT SELECT ON public.buyer_capacity_intakes TO service_role;

CREATE OR REPLACE FUNCTION public.record_buyer_capacity_intake(
  p_case_id uuid,
  p_reply_id uuid,
  p_territory text,
  p_daily_cap integer,
  p_delivery_route text,
  p_delivery_reference text,
  p_evidence jsonb,
  p_actor text DEFAULT 'empire_closer_planner'
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
  x public.buyer_capacity_intakes%ROWTYPE;
  v_territory text := NULLIF(trim(COALESCE(p_territory,'')),'');
  v_route text := NULLIF(lower(trim(COALESCE(p_delivery_route,''))),'');
  v_ref text := NULLIF(trim(COALESCE(p_delivery_reference,'')),'');
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_actor='' THEN RAISE EXCEPTION 'actor required'; END IF;

  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost','paused') THEN RAISE EXCEPTION 'active closer case required'; END IF;
  IF c.buyer_id IS NULL THEN RAISE EXCEPTION 'buyer-bound closer case required'; END IF;

  SELECT * INTO r FROM public.outbound_replies WHERE id=p_reply_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply not found'; END IF;

  SELECT * INTO i FROM public.outbound_intents WHERE id=r.intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply intent not found'; END IF;

  IF r.id IS DISTINCT FROM c.reply_id
     AND COALESCE(i.metadata->>'closer_case_id','') IS DISTINCT FROM c.id::text THEN
    RAISE EXCEPTION 'reply does not belong to closer case';
  END IF;

  IF r.classification NOT IN ('positive','question','objection') THEN
    RAISE EXCEPTION 'commercially engaged inbound reply required';
  END IF;

  IF p_daily_cap IS NOT NULL AND (p_daily_cap < 1 OR p_daily_cap > 10000) THEN
    RAISE EXCEPTION 'daily capacity must be between 1 and 10000';
  END IF;

  IF v_route IS NOT NULL AND v_route NOT IN ('email','webhook','phone','api') THEN
    RAISE EXCEPTION 'unsupported delivery route';
  END IF;

  IF v_territory IS NULL AND p_daily_cap IS NULL AND v_route IS NULL AND v_ref IS NULL THEN
    RAISE EXCEPTION 'at least one explicit capacity field required';
  END IF;

  INSERT INTO public.buyer_capacity_intakes(
    closer_case_id,buyer_id,source_reply_ids,
    territory,daily_cap,delivery_route,delivery_reference,
    evidence,state
  ) VALUES (
    c.id,c.buyer_id,ARRAY[r.id]::uuid[],
    v_territory,p_daily_cap,v_route,v_ref,
    COALESCE(p_evidence,'{}'::jsonb),
    CASE
      WHEN v_territory IS NOT NULL AND p_daily_cap IS NOT NULL AND v_route IS NOT NULL
      THEN 'complete'
      ELSE 'partial'
    END
  )
  ON CONFLICT (closer_case_id)
  DO UPDATE SET
    buyer_id=EXCLUDED.buyer_id,
    source_reply_ids=CASE
      WHEN r.id=ANY(public.buyer_capacity_intakes.source_reply_ids)
      THEN public.buyer_capacity_intakes.source_reply_ids
      ELSE array_append(public.buyer_capacity_intakes.source_reply_ids,r.id)
    END,
    territory=COALESCE(EXCLUDED.territory,public.buyer_capacity_intakes.territory),
    daily_cap=COALESCE(EXCLUDED.daily_cap,public.buyer_capacity_intakes.daily_cap),
    delivery_route=COALESCE(EXCLUDED.delivery_route,public.buyer_capacity_intakes.delivery_route),
    delivery_reference=COALESCE(EXCLUDED.delivery_reference,public.buyer_capacity_intakes.delivery_reference),
    evidence=public.buyer_capacity_intakes.evidence
      || COALESCE(EXCLUDED.evidence,'{}'::jsonb)
      || jsonb_build_object('latest_reply_id',r.id,'latest_actor',v_actor),
    state=CASE
      WHEN COALESCE(EXCLUDED.territory,public.buyer_capacity_intakes.territory) IS NOT NULL
       AND COALESCE(EXCLUDED.daily_cap,public.buyer_capacity_intakes.daily_cap) IS NOT NULL
       AND COALESCE(EXCLUDED.delivery_route,public.buyer_capacity_intakes.delivery_route) IS NOT NULL
      THEN 'complete'
      ELSE 'partial'
    END,
    updated_at=clock_timestamp()
  RETURNING * INTO x;

  INSERT INTO public.closer_events(case_id,event_type,actor,payload)
  VALUES(
    c.id,
    'buyer_capacity_intake_updated',
    v_actor,
    jsonb_build_object(
      'capacity_intake_id',x.id,
      'reply_id',r.id,
      'state',x.state,
      'territory_present',x.territory IS NOT NULL,
      'daily_cap_present',x.daily_cap IS NOT NULL,
      'delivery_route_present',x.delivery_route IS NOT NULL,
      'buyer_stated_only',true,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','recorded',
    'capacity_intake_id',x.id,
    'case_id',c.id,
    'buyer_id',c.buyer_id,
    'state',x.state,
    'territory',x.territory,
    'daily_cap',x.daily_cap,
    'delivery_route',x.delivery_route,
    'delivery_reference',x.delivery_reference,
    'buyer_stated_only',true,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.prepare_fulfilment_order_from_capacity(
  p_case_id uuid,
  p_actor text DEFAULT 'empire_closer_planner'
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
BEGIN
  IF v_actor='' THEN RAISE EXCEPTION 'actor required'; END IF;

  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost','paused') THEN RAISE EXCEPTION 'active closer case required'; END IF;
  IF c.buyer_id IS NULL OR c.prospect_id IS NULL THEN
    RAISE EXCEPTION 'buyer and prospect binding required';
  END IF;

  IF c.fulfilment_order_id IS NOT NULL THEN
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=c.fulfilment_order_id;
    IF FOUND THEN
      RETURN jsonb_build_object(
        'decision','existing',
        'fulfilment_order_id',o.id,
        'state',o.state,
        'actual_revenue',false
      );
    END IF;
  END IF;

  SELECT * INTO x
    FROM public.buyer_capacity_intakes
   WHERE closer_case_id=c.id
   FOR UPDATE;
  IF NOT FOUND OR x.state<>'complete' THEN
    RAISE EXCEPTION 'complete buyer-stated capacity intake required';
  END IF;

  INSERT INTO public.fulfilment_orders(
    opportunity_id,
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

  INSERT INTO public.closer_events(case_id,event_type,actor,payload)
  VALUES(
    c.id,
    'fulfilment_order_prepared',
    v_actor,
    jsonb_build_object(
      'fulfilment_order_id',o.id,
      'order_state',o.state,
      'buyer_capacity_intake_id',x.id,
      'binding_commercial_terms',false,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','prepared',
    'fulfilment_order_id',o.id,
    'state',o.state,
    'buyer_capacity_intake_id',x.id,
    'binding_commercial_terms',false,
    'actual_revenue',false
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_buyer_capacity_intake(
  uuid,uuid,text,integer,text,text,jsonb,text
) FROM PUBLIC,anon,authenticated,empire_closer_observer,empire_closer_approver;

REVOKE ALL ON FUNCTION public.prepare_fulfilment_order_from_capacity(uuid,text)
  FROM PUBLIC,anon,authenticated,empire_closer_observer,empire_closer_approver;

GRANT EXECUTE ON FUNCTION public.record_buyer_capacity_intake(
  uuid,uuid,text,integer,text,text,jsonb,text
) TO service_role,empire_closer_planner;

GRANT EXECUTE ON FUNCTION public.prepare_fulfilment_order_from_capacity(uuid,text)
  TO service_role,empire_closer_planner;

COMMIT;
