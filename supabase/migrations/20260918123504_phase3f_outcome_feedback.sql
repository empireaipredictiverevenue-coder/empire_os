-- Phase 3F: immutable commercial outcomes and evidence-derived revenue recognition.
-- No payment movement occurs here. Revenue is recognized only from previously
-- verified BSC evidence that exactly matches approved USD commercial terms.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_outcome_recorder') THEN
    CREATE ROLE empire_outcome_recorder NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_revenue_recognizer') THEN
    CREATE ROLE empire_revenue_recognizer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_outcome_recorder, empire_revenue_recognizer;
REVOKE empire_outcome_recorder, empire_revenue_recognizer FROM service_role;

ALTER TABLE public.commercial_events
  ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS uq_commercial_events_idempotency_key
  ON public.commercial_events(idempotency_key)
  WHERE idempotency_key IS NOT NULL;

CREATE TABLE public.commercial_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  delivery_outcome text NOT NULL CHECK (
    delivery_outcome IN ('delivered','confirmed','rejected','failed','refunded','unknown')
  ),
  conversion_outcome text NOT NULL CHECK (
    conversion_outcome IN ('unknown','qualified','booked','won','lost','no_response')
  ),
  buyer_satisfaction numeric(3,2) CHECK (
    buyer_satisfaction IS NULL OR buyer_satisfaction BETWEEN 1 AND 5
  ),
  evidence_kind text NOT NULL CHECK (
    evidence_kind IN (
      'outbound_reply','buyer_feedback','delivery_receipt',
      'crm','provider_event','manual_verified'
    )
  ),
  evidence_reference text NOT NULL CHECK (length(trim(evidence_reference)) > 0),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  idempotency_key text NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) BETWEEN 8 AND 160),
  actor text NOT NULL CHECK (length(trim(actor)) BETWEEN 1 AND 200),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX commercial_outcomes_order_idx
  ON public.commercial_outcomes(fulfilment_order_id, recorded_at DESC);
ALTER TABLE public.commercial_outcomes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.commercial_outcomes
  FROM PUBLIC,anon,authenticated,service_role,empire_outcome_recorder,empire_revenue_recognizer;
GRANT SELECT ON public.commercial_outcomes TO service_role;


CREATE FUNCTION public.guard_commercial_outcomes_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'commercial outcomes are append-only';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER guard_commercial_outcomes_append_only
BEFORE UPDATE OR DELETE ON public.commercial_outcomes
FOR EACH ROW EXECUTE FUNCTION public.guard_commercial_outcomes_append_only();

CREATE OR REPLACE FUNCTION public.guard_commercial_events_integrity()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
  v_role text := COALESCE(NULLIF(current_setting('role',true),'none'),session_user);
  v_amount bigint;
  v_cost bigint;
  v_margin bigint;
BEGIN
  IF TG_OP IN ('UPDATE','DELETE') THEN
    RAISE EXCEPTION 'commercial events are append-only';
  END IF;

  v_amount := COALESCE(NEW.amount_cents,0);
  v_cost := COALESCE(NEW.cost_cents,0);
  v_margin := COALESCE(NEW.margin_cents,0);

  IF (
    NEW.event_type='revenue_recognized'
    OR v_amount<>0 OR v_cost<>0 OR v_margin<>0
  ) AND v_role<>'empire_revenue_recognizer' THEN
    RAISE EXCEPTION 'financial commercial events require revenue recognizer role';
  END IF;

  IF NEW.event_type='outcome_recorded'
     AND v_role<>'empire_outcome_recorder' THEN
    RAISE EXCEPTION 'outcome commercial events require outcome recorder role';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_commercial_events_integrity ON public.commercial_events;
CREATE TRIGGER guard_commercial_events_integrity
BEFORE INSERT OR UPDATE OR DELETE ON public.commercial_events
FOR EACH ROW EXECUTE FUNCTION public.guard_commercial_events_integrity();


CREATE FUNCTION public.record_commercial_outcome(
  p_fulfilment_order_id uuid,
  p_delivery_outcome text,
  p_conversion_outcome text,
  p_buyer_satisfaction numeric,
  p_evidence_kind text,
  p_evidence_reference text,
  p_evidence jsonb,
  p_idempotency_key text,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  x public.commercial_outcomes%ROWTYPE;
  v_delivery text := lower(trim(COALESCE(p_delivery_outcome,'')));
  v_conversion text := lower(trim(COALESCE(p_conversion_outcome,'')));
  v_kind text := lower(trim(COALESCE(p_evidence_kind,'')));
  v_ref text := trim(COALESCE(p_evidence_reference,''));
  v_key text := trim(COALESCE(p_idempotency_key,''));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'fulfilment order required'; END IF;
  IF v_delivery NOT IN ('delivered','confirmed','rejected','failed','refunded','unknown') THEN
    RAISE EXCEPTION 'unsupported delivery outcome';
  END IF;
  IF v_conversion NOT IN ('unknown','qualified','booked','won','lost','no_response') THEN
    RAISE EXCEPTION 'unsupported conversion outcome';
  END IF;
  IF p_buyer_satisfaction IS NOT NULL
     AND (p_buyer_satisfaction < 1 OR p_buyer_satisfaction > 5) THEN
    RAISE EXCEPTION 'buyer satisfaction must be 1-5';
  END IF;
  IF v_kind NOT IN (
    'outbound_reply','buyer_feedback','delivery_receipt',
    'crm','provider_event','manual_verified'
  ) THEN RAISE EXCEPTION 'supported outcome evidence required'; END IF;
  IF v_ref='' OR length(v_key)<8 OR length(v_key)>160 OR v_actor='' THEN
    RAISE EXCEPTION 'evidence reference, idempotency key and actor required';
  END IF;
  IF jsonb_typeof(COALESCE(p_evidence,'{}'::jsonb)) <> 'object' THEN
    RAISE EXCEPTION 'outcome evidence object required';
  END IF;

  SELECT * INTO o FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.state NOT IN (
    'delivered','confirmed','invoiced','paid','settled','outcome_captured'
  ) THEN RAISE EXCEPTION 'post-delivery fulfilment order required'; END IF;

  SELECT * INTO x FROM public.commercial_outcomes WHERE idempotency_key=v_key;
  IF FOUND THEN
    IF x.fulfilment_order_id IS DISTINCT FROM o.id
       OR x.delivery_outcome IS DISTINCT FROM v_delivery
       OR x.conversion_outcome IS DISTINCT FROM v_conversion
       OR x.evidence_kind IS DISTINCT FROM v_kind
       OR x.evidence_reference IS DISTINCT FROM v_ref THEN
      RAISE EXCEPTION 'idempotency key belongs to different outcome';
    END IF;
    RETURN jsonb_build_object(
      'decision','existing_outcome','outcome_id',x.id,
      'fulfilment_order_id',o.id,'actual_revenue',false
    );
  END IF;

  INSERT INTO public.commercial_outcomes(
    fulfilment_order_id,delivery_outcome,conversion_outcome,buyer_satisfaction,
    evidence_kind,evidence_reference,evidence,idempotency_key,actor
  ) VALUES (
    o.id,v_delivery,v_conversion,p_buyer_satisfaction,v_kind,v_ref,
    COALESCE(p_evidence,'{}'::jsonb),v_key,v_actor
  ) RETURNING * INTO x;

  UPDATE public.fulfilment_orders
     SET outcome_at=COALESCE(outcome_at,x.recorded_at),
         state=CASE WHEN state='settled' THEN 'outcome_captured' ELSE state END,
         updated_at=clock_timestamp()
   WHERE id=o.id;

  INSERT INTO public.commercial_events(
    event_type,opportunity_id,fulfilment_order_id,prospect_id,entity_id,buyer_id,
    product_id,channel,actor,amount_cents,cost_cents,margin_cents,payload,
    occurred_at,idempotency_key
  ) VALUES (
    'outcome_recorded',o.opportunity_id,o.id,o.prospect_id,o.entity_id,o.buyer_id,
    o.product_id,'outcome_feedback',v_actor,0,0,0,
    jsonb_build_object(
      'outcome_id',x.id,'delivery_outcome',x.delivery_outcome,
      'conversion_outcome',x.conversion_outcome,
      'buyer_satisfaction',x.buyer_satisfaction,
      'evidence_kind',x.evidence_kind,'evidence_reference',x.evidence_reference,
      'actual_revenue',false
    ),
    x.recorded_at,'outcome:'||x.id::text
  );

  RETURN jsonb_build_object(
    'decision','recorded_outcome','outcome_id',x.id,
    'fulfilment_order_id',o.id,'actual_revenue',false
  );
END;
$$;


CREATE FUNCTION public.recognize_bsc_revenue(
  p_fulfilment_order_id uuid,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
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

  v_cost := COALESCE(o.acquisition_cost_cents,0)
          + COALESCE(o.fulfilment_cost_cents,0);
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
             'recognized_revenue_at',v_paid_at
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


CREATE FUNCTION public.list_revenue_recognition_work(
  p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE
  result jsonb;
BEGIN
  IF p_limit IS NULL OR p_limit<1 OR p_limit>100 THEN
    RAISE EXCEPTION 'revenue recognition work limit must be 1-100';
  END IF;

  WITH candidates AS (
    SELECT
      o.id AS fulfilment_order_id,
      o.price_cents,
      EXISTS(
        SELECT 1
          FROM public.bsc_payment_requests r
          JOIN public.bsc_payment_evidence d ON d.request_id=r.id
         WHERE r.fulfilment_order_id=o.id
           AND r.settlement_mode='direct'
           AND r.status='approved'
      ) AS direct_evidence,
      EXISTS(
        SELECT 1
          FROM public.bsc_payment_requests r
          JOIN public.bsc_escrow_agreements a ON a.request_id=r.id
          JOIN public.bsc_escrow_evidence e
            ON e.agreement_id=a.id AND e.action='released'
         WHERE r.fulfilment_order_id=o.id
           AND r.settlement_mode='escrow'
           AND r.status='approved'
           AND a.status='released'
      ) AS escrow_release,
      EXISTS(
        SELECT 1
          FROM public.bsc_payment_requests r
          LEFT JOIN public.bsc_payment_evidence d
            ON d.request_id=r.id AND r.settlement_mode='direct'
          LEFT JOIN public.bsc_escrow_agreements a
            ON a.request_id=r.id AND r.settlement_mode='escrow'
          LEFT JOIN public.bsc_escrow_evidence e
            ON e.agreement_id=a.id AND e.action='released'
         WHERE r.fulfilment_order_id=o.id
           AND r.status='approved'
           AND r.amount_usdt*100=o.price_cents::numeric
           AND (
             (r.settlement_mode='direct' AND d.id IS NOT NULL)
             OR
             (r.settlement_mode='escrow' AND a.status='released' AND e.id IS NOT NULL)
           )
      ) AS amount_matches
    FROM public.fulfilment_orders o
    WHERE o.price_cents>0
      AND NOT EXISTS(
        SELECT 1 FROM public.commercial_events ce
         WHERE ce.idempotency_key='revenue:'||o.id::text||':v1'
      )
      AND (
        EXISTS(
          SELECT 1 FROM public.bsc_payment_requests r
          JOIN public.bsc_payment_evidence d ON d.request_id=r.id
          WHERE r.fulfilment_order_id=o.id AND r.settlement_mode='direct'
        )
        OR EXISTS(
          SELECT 1 FROM public.bsc_payment_requests r
          JOIN public.bsc_escrow_agreements a ON a.request_id=r.id
          JOIN public.bsc_escrow_evidence e
            ON e.agreement_id=a.id AND e.action='released'
          WHERE r.fulfilment_order_id=o.id AND r.settlement_mode='escrow'
        )
      )
    ORDER BY o.updated_at,o.id
    LIMIT p_limit
  )
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'fulfilment_order_id',fulfilment_order_id,
    'price_cents',price_cents,
    'direct_evidence',direct_evidence,
    'escrow_release',escrow_release,
    'amount_matches',amount_matches
  )), '[]'::jsonb)
  INTO result
  FROM candidates;

  RETURN result;
END;
$$;

CREATE FUNCTION public.get_commercial_outcome_feedback(
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


REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON public.commercial_events
  FROM anon,authenticated;
REVOKE UPDATE,DELETE,TRUNCATE ON public.commercial_events
  FROM service_role;

REVOKE ALL ON FUNCTION public.guard_commercial_outcomes_append_only()
  FROM PUBLIC,anon,authenticated,service_role,empire_outcome_recorder,empire_revenue_recognizer;
REVOKE ALL ON FUNCTION public.guard_commercial_events_integrity()
  FROM PUBLIC,anon,authenticated,service_role,empire_outcome_recorder,empire_revenue_recognizer;

REVOKE ALL ON FUNCTION public.record_commercial_outcome(
  uuid,text,text,numeric,text,text,jsonb,text,text
) FROM PUBLIC,anon,authenticated,service_role,empire_revenue_recognizer;
GRANT EXECUTE ON FUNCTION public.record_commercial_outcome(
  uuid,text,text,numeric,text,text,jsonb,text,text
) TO empire_outcome_recorder;

REVOKE ALL ON FUNCTION public.recognize_bsc_revenue(uuid,text)
  FROM PUBLIC,anon,authenticated,service_role,empire_outcome_recorder;
GRANT EXECUTE ON FUNCTION public.recognize_bsc_revenue(uuid,text)
  TO empire_revenue_recognizer;

REVOKE ALL ON FUNCTION public.list_revenue_recognition_work(integer)
  FROM PUBLIC,anon,authenticated,service_role,empire_outcome_recorder;
GRANT EXECUTE ON FUNCTION public.list_revenue_recognition_work(integer)
  TO empire_revenue_recognizer;

REVOKE ALL ON FUNCTION public.get_commercial_outcome_feedback(integer)
  FROM PUBLIC,anon,authenticated,empire_outcome_recorder,empire_revenue_recognizer;
GRANT EXECUTE ON FUNCTION public.get_commercial_outcome_feedback(integer)
  TO service_role;

COMMENT ON TABLE public.commercial_outcomes IS
'Phase 3F append-only non-financial outcome evidence for learning and buyer quality feedback.';
COMMENT ON FUNCTION public.recognize_bsc_revenue(uuid,text) IS
'Recognize actual revenue only from verified direct BSC payment evidence or released BSC escrow evidence matching approved USD price exactly.';
COMMENT ON FUNCTION public.get_commercial_outcome_feedback(integer) IS
'Canonical Phase 3F read model for Omega/Astra outcome learning.';

COMMIT;
