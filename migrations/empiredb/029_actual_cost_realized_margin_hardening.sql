-- Actual-cost truth hardening for realized margin.
-- HELD until explicit database activation.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $actual_cost_guard$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'EmpireDB required';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator'
      AND NOT rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'actual-cost hardening requires guarded migrator';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_revenue_recognizer'
      AND NOT rolcanlogin AND NOT rolsuper AND NOT rolinherit
  ) THEN
    RAISE EXCEPTION 'revenue recognizer role missing or unsafe';
  END IF;

  IF pg_catalog.pg_has_role(
      'empire_revenue_recognizer',
      'empiredb_migrator',
      'MEMBER'
  ) OR pg_catalog.pg_has_role(
      'empiredb_app',
      'empire_revenue_recognizer',
      'MEMBER'
  ) THEN
    RAISE EXCEPTION 'actual-cost authority boundary violated';
  END IF;

  IF pg_catalog.to_regclass('public.commercial_evidence_registry') IS NULL
     OR pg_catalog.to_regclass('public.fulfilment_orders') IS NULL
     OR pg_catalog.to_regclass('public.commercial_events') IS NULL THEN
    RAISE EXCEPTION 'actual-cost canonical relations missing';
  END IF;

  IF pg_catalog.has_table_privilege(
      'empire_revenue_recognizer',
      'public.commercial_evidence_registry',
      'SELECT'
  ) THEN
    RAISE EXCEPTION 'recognizer must not directly read commercial evidence registry';
  END IF;
END;
$actual_cost_guard$;

CREATE OR REPLACE FUNCTION public.get_verified_actual_cost_evidence(
  p_fulfilment_order_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path=''
AS $actual_cost$
DECLARE
  acq public.commercial_evidence_registry%ROWTYPE;
  fulfil public.commercial_evidence_registry%ROWTYPE;
BEGIN
  IF p_fulfilment_order_id IS NULL THEN
    RAISE EXCEPTION 'fulfilment order required';
  END IF;

  PERFORM 1
    FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'fulfilment order not found';
  END IF;

  SELECT * INTO acq
    FROM public.commercial_evidence_registry e
   WHERE e.fulfilment_order_id=p_fulfilment_order_id
     AND e.evidence_kind='acquisition_cost'
     AND e.status='verified'
     AND e.source_type IN ('provider_invoice','internal_actual')
     AND e.unit IN ('per_order','flat')
     AND e.observed_at<=pg_catalog.clock_timestamp()
   ORDER BY e.observed_at DESC,e.id DESC
   LIMIT 1;

  SELECT * INTO fulfil
    FROM public.commercial_evidence_registry e
   WHERE e.fulfilment_order_id=p_fulfilment_order_id
     AND e.evidence_kind='fulfilment_cost'
     AND e.status='verified'
     AND e.source_type IN ('provider_invoice','internal_actual')
     AND e.unit IN ('per_order','flat')
     AND e.observed_at<=pg_catalog.clock_timestamp()
   ORDER BY e.observed_at DESC,e.id DESC
   LIMIT 1;

  RETURN pg_catalog.jsonb_build_object(
    'fulfilment_order_id',p_fulfilment_order_id,
    'actual_cost_ready',(acq.id IS NOT NULL AND fulfil.id IS NOT NULL),
    'acquisition_cost',CASE
      WHEN acq.id IS NULL THEN NULL
      ELSE pg_catalog.jsonb_build_object(
        'evidence_id',acq.id,
        'amount_cents',acq.amount_cents,
        'source_type',acq.source_type,
        'source_reference',acq.source_reference,
        'observed_at',acq.observed_at
      )
    END,
    'fulfilment_cost',CASE
      WHEN fulfil.id IS NULL THEN NULL
      ELSE pg_catalog.jsonb_build_object(
        'evidence_id',fulfil.id,
        'amount_cents',fulfil.amount_cents,
        'source_type',fulfil.source_type,
        'source_reference',fulfil.source_reference,
        'observed_at',fulfil.observed_at
      )
    END,
    'execution_authority','none'
  );
END;
$actual_cost$;

REVOKE ALL ON FUNCTION public.get_verified_actual_cost_evidence(uuid)
  FROM PUBLIC, empiredb_app;
GRANT EXECUTE ON FUNCTION public.get_verified_actual_cost_evidence(uuid)
  TO empire_revenue_recognizer;

CREATE OR REPLACE FUNCTION public.recognize_bsc_revenue(
  p_fulfilment_order_id uuid,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  r public.bsc_payment_requests%ROWTYPE;
  d public.bsc_payment_evidence%ROWTYPE;
  a public.bsc_escrow_agreements%ROWTYPE;
  e public.bsc_escrow_evidence%ROWTYPE;
  existing public.commercial_events%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
  v_source text;
  v_evidence_id uuid;
  v_tx text;
  v_paid_at timestamptz;
  v_cost bigint;
  v_margin bigint;
  v_key text;
  v_actual_cost jsonb;
  v_acquisition_actual bigint;
  v_fulfilment_actual bigint;
BEGIN
  IF p_fulfilment_order_id IS NULL OR v_actor='' THEN
    RAISE EXCEPTION 'fulfilment order and actor required';
  END IF;

  v_key := 'revenue:'||p_fulfilment_order_id::text||':v1';

  SELECT * INTO existing
    FROM public.commercial_events
   WHERE idempotency_key=v_key;
  IF FOUND THEN
    RETURN jsonb_build_object(
      'decision','existing_revenue',
      'fulfilment_order_id',existing.fulfilment_order_id,
      'amount_cents',existing.amount_cents,
      'cost_cents',existing.cost_cents,
      'margin_cents',existing.margin_cents,
      'actual_revenue',true
    );
  END IF;

  SELECT * INTO o
    FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.buyer_id IS NULL OR o.price_cents<=0 THEN
    RAISE EXCEPTION 'priced buyer fulfilment order required';
  END IF;
  IF lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''))
     !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'approved commercial terms required';
  END IF;

  SELECT rr.* INTO r
    FROM public.bsc_payment_requests rr
    JOIN public.bsc_payment_evidence dd ON dd.request_id=rr.id
   WHERE rr.fulfilment_order_id=o.id
     AND rr.settlement_mode='direct'
     AND rr.status='approved'
     AND rr.approved_at IS NOT NULL
     AND NULLIF(trim(COALESCE(rr.approved_by,'')),'') IS NOT NULL
   ORDER BY dd.verified_at DESC
   LIMIT 1;

  IF FOUND THEN
    SELECT * INTO d
      FROM public.bsc_payment_evidence
     WHERE request_id=r.id
     ORDER BY verified_at DESC
     LIMIT 1;
    v_source := 'direct_payment';
    v_evidence_id := d.id;
    v_tx := d.transaction_hash;
    v_paid_at := d.verified_at;
  ELSE
    SELECT rr.* INTO r
      FROM public.bsc_payment_requests rr
      JOIN public.bsc_escrow_agreements aa ON aa.request_id=rr.id
      JOIN public.bsc_escrow_evidence ee
        ON ee.agreement_id=aa.id AND ee.action='released'
     WHERE rr.fulfilment_order_id=o.id
       AND rr.settlement_mode='escrow'
       AND rr.status='approved'
       AND rr.approved_at IS NOT NULL
       AND NULLIF(trim(COALESCE(rr.approved_by,'')),'') IS NOT NULL
       AND aa.status='released'
     ORDER BY ee.verified_at DESC
     LIMIT 1;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'no revenue-eligible verified BSC settlement evidence';
    END IF;

    SELECT * INTO a
      FROM public.bsc_escrow_agreements
     WHERE request_id=r.id;
    SELECT * INTO e
      FROM public.bsc_escrow_evidence
     WHERE agreement_id=a.id AND action='released'
     ORDER BY verified_at DESC
     LIMIT 1;

    v_source := 'escrow_release';
    v_evidence_id := e.id;
    v_tx := e.transaction_hash;
    v_paid_at := e.verified_at;
  END IF;

  IF r.commercial_terms_sha256 IS DISTINCT FROM
     lower(o.commercial_payload->>'commercial_terms_sha256') THEN
    RAISE EXCEPTION 'payment evidence commercial terms mismatch';
  END IF;
  IF r.amount_usdt*100 IS DISTINCT FROM o.price_cents::numeric THEN
    RAISE EXCEPTION 'settlement amount does not equal approved USD price';
  END IF;

  SELECT public.get_verified_actual_cost_evidence(o.id)
    INTO v_actual_cost;

  IF COALESCE((v_actual_cost->>'actual_cost_ready')::boolean,false) IS NOT TRUE THEN
    RAISE EXCEPTION 'verified order-bound actual acquisition and fulfilment cost evidence required';
  END IF;

  v_acquisition_actual :=
    (v_actual_cost->'acquisition_cost'->>'amount_cents')::bigint;
  v_fulfilment_actual :=
    (v_actual_cost->'fulfilment_cost'->>'amount_cents')::bigint;
  v_cost := v_acquisition_actual + v_fulfilment_actual;
  v_margin := o.price_cents-v_cost;
  IF v_cost<0 OR v_margin<=0 THEN
    RAISE EXCEPTION 'positive realized margin required';
  END IF;

  INSERT INTO public.commercial_events(
    event_type,opportunity_id,fulfilment_order_id,prospect_id,entity_id,buyer_id,
    product_id,channel,actor,amount_cents,cost_cents,margin_cents,payload,
    occurred_at,idempotency_key
  ) VALUES (
    'revenue_recognized',o.opportunity_id,o.id,o.prospect_id,o.entity_id,o.buyer_id,
    o.product_id,'bsc_usdt',v_actor,o.price_cents,v_cost,v_margin,
    jsonb_build_object(
      'settlement_source',v_source,
      'payment_request_id',r.id,
      'evidence_id',v_evidence_id,
      'transaction_hash',v_tx,
      'commercial_terms_sha256',r.commercial_terms_sha256,
      'settlement_asset','USDT','settlement_chain','BSC',
      'actual_cost_evidence',v_actual_cost,
      'actual_cost_evidence_verified',true,
      'actual_revenue',true
    ),
    v_paid_at,v_key
  );

  UPDATE public.fulfilment_orders
     SET state=CASE
           WHEN EXISTS(
             SELECT 1 FROM public.commercial_outcomes co
              WHERE co.fulfilment_order_id=o.id
           ) THEN 'outcome_captured'
           ELSE 'settled'
         END,
         actual_margin_cents=v_margin,
         paid_at=COALESCE(paid_at,v_paid_at),
         settled_at=COALESCE(settled_at,v_paid_at),
         commercial_payload=COALESCE(commercial_payload,'{}'::jsonb) ||
           jsonb_build_object(
             'recognized_revenue_cents',o.price_cents,
             'recognized_revenue_source',v_source,
             'recognized_revenue_evidence_id',v_evidence_id,
             'recognized_revenue_transaction_hash',v_tx,
             'recognized_revenue_at',v_paid_at,
             'actual_acquisition_cost_cents',v_acquisition_actual,
             'actual_fulfilment_cost_cents',v_fulfilment_actual,
             'actual_cost_evidence',v_actual_cost
           ),
         updated_at=clock_timestamp()
   WHERE id=o.id;

  RETURN jsonb_build_object(
    'decision','revenue_recognized',
    'fulfilment_order_id',o.id,
    'amount_cents',o.price_cents,
    'cost_cents',v_cost,
    'margin_cents',v_margin,
    'settlement_source',v_source,
    'evidence_id',v_evidence_id,
    'actual_revenue',true
  );
END;
$$;

REVOKE ALL ON FUNCTION public.recognize_bsc_revenue(uuid,text)
  FROM PUBLIC, empiredb_app;
GRANT EXECUTE ON FUNCTION public.recognize_bsc_revenue(uuid,text)
  TO empire_revenue_recognizer;

COMMENT ON FUNCTION public.get_verified_actual_cost_evidence(uuid)
IS 'Read-only order-bound verified actual cost projection. No payment or revenue authority.';

COMMENT ON FUNCTION public.recognize_bsc_revenue(uuid,text)
IS 'Recognizes verified BSC revenue only with verified order-bound actual cost evidence.';

COMMIT;
