-- Canonical verified commercial evidence registry.
-- Evidence can inform a proposal, but never grants pricing, acceptance,
-- settlement, fulfilment or revenue authority by itself.
BEGIN;

CREATE TABLE IF NOT EXISTS public.commercial_evidence_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  evidence_kind text NOT NULL
    CHECK (evidence_kind IN ('price','acquisition_cost','fulfilment_cost')),
  buyer_id uuid REFERENCES public.buyers(id) ON DELETE RESTRICT,
  closer_case_id uuid REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  fulfilment_order_id uuid REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  niche text,
  metro text,
  amount_cents bigint NOT NULL CHECK (amount_cents >= 0),
  currency text NOT NULL DEFAULT 'USD',
  unit text NOT NULL DEFAULT 'per_order'
    CHECK (unit IN ('per_order','per_lead','per_call','per_month','flat')),
  source_type text NOT NULL
    CHECK (
      source_type IN (
        'buyer_stated',
        'founder_approved',
        'observed_contract',
        'public_price',
        'provider_invoice',
        'internal_actual'
      )
    ),
  source_reference text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','verified','rejected')),
  observed_at timestamptz NOT NULL,
  valid_until timestamptz,
  verified_at timestamptz,
  verified_by text,
  rejected_at timestamptz,
  rejected_by text,
  rejection_reason text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (upper(currency)='USD'),
  CHECK (
    evidence_kind <> 'price'
    OR amount_cents > 0
  ),
  CHECK (
    valid_until IS NULL
    OR valid_until > observed_at
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_commercial_evidence_source
  ON public.commercial_evidence_registry(
    evidence_kind,source_type,source_reference
  );

CREATE INDEX IF NOT EXISTS idx_commercial_evidence_market
  ON public.commercial_evidence_registry(
    evidence_kind,niche,metro,status,observed_at DESC
  );

CREATE INDEX IF NOT EXISTS idx_commercial_evidence_order
  ON public.commercial_evidence_registry(
    fulfilment_order_id,evidence_kind,status,observed_at DESC
  );

ALTER TABLE public.commercial_evidence_registry ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.commercial_evidence_registry
  FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON public.commercial_evidence_registry TO service_role;

CREATE OR REPLACE FUNCTION public.propose_commercial_evidence(
  p_evidence_kind text,
  p_buyer_id uuid,
  p_closer_case_id uuid,
  p_fulfilment_order_id uuid,
  p_niche text,
  p_metro text,
  p_amount_cents bigint,
  p_unit text,
  p_source_type text,
  p_source_reference text,
  p_evidence jsonb,
  p_observed_at timestamptz,
  p_valid_until timestamptz DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  v_kind text := lower(trim(COALESCE(p_evidence_kind,'')));
  v_unit text := lower(trim(COALESCE(p_unit,'')));
  v_source text := lower(trim(COALESCE(p_source_type,'')));
  v_ref text := trim(COALESCE(p_source_reference,''));
  v_niche text := NULLIF(trim(COALESCE(p_niche,'')),'');
  v_metro text := NULLIF(trim(COALESCE(p_metro,'')),'');
BEGIN
  IF v_kind NOT IN ('price','acquisition_cost','fulfilment_cost') THEN
    RAISE EXCEPTION 'unsupported commercial evidence kind';
  END IF;
  IF v_unit NOT IN ('per_order','per_lead','per_call','per_month','flat') THEN
    RAISE EXCEPTION 'unsupported evidence unit';
  END IF;
  IF v_source NOT IN (
    'buyer_stated','founder_approved','observed_contract',
    'public_price','provider_invoice','internal_actual'
  ) THEN
    RAISE EXCEPTION 'unsupported commercial evidence source';
  END IF;
  IF v_ref='' OR p_observed_at IS NULL THEN
    RAISE EXCEPTION 'source reference and observed_at required';
  END IF;
  IF p_amount_cents IS NULL OR p_amount_cents < 0 THEN
    RAISE EXCEPTION 'nonnegative amount required';
  END IF;
  IF v_kind='price' AND p_amount_cents <= 0 THEN
    RAISE EXCEPTION 'positive price required';
  END IF;
  IF p_valid_until IS NOT NULL AND p_valid_until <= p_observed_at THEN
    RAISE EXCEPTION 'valid_until must be after observed_at';
  END IF;

  IF p_buyer_id IS NOT NULL THEN
    PERFORM 1 FROM public.buyers WHERE id=p_buyer_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer not found'; END IF;
  END IF;

  IF p_closer_case_id IS NOT NULL THEN
    PERFORM 1 FROM public.closer_cases WHERE id=p_closer_case_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  END IF;

  IF p_fulfilment_order_id IS NOT NULL THEN
    PERFORM 1 FROM public.fulfilment_orders WHERE id=p_fulfilment_order_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  END IF;

  INSERT INTO public.commercial_evidence_registry(
    evidence_kind,buyer_id,closer_case_id,fulfilment_order_id,
    niche,metro,amount_cents,currency,unit,
    source_type,source_reference,evidence,observed_at,valid_until
  ) VALUES (
    v_kind,p_buyer_id,p_closer_case_id,p_fulfilment_order_id,
    v_niche,v_metro,p_amount_cents,'USD',v_unit,
    v_source,v_ref,COALESCE(p_evidence,'{}'::jsonb),
    p_observed_at,p_valid_until
  )
  ON CONFLICT (evidence_kind,source_type,source_reference)
  DO UPDATE SET
    buyer_id=EXCLUDED.buyer_id,
    closer_case_id=EXCLUDED.closer_case_id,
    fulfilment_order_id=EXCLUDED.fulfilment_order_id,
    niche=EXCLUDED.niche,
    metro=EXCLUDED.metro,
    amount_cents=EXCLUDED.amount_cents,
    unit=EXCLUDED.unit,
    evidence=EXCLUDED.evidence,
    observed_at=EXCLUDED.observed_at,
    valid_until=EXCLUDED.valid_until,
    updated_at=clock_timestamp()
  WHERE public.commercial_evidence_registry.status='pending'
  RETURNING * INTO x;

  IF x.id IS NULL THEN
    SELECT * INTO x
      FROM public.commercial_evidence_registry
     WHERE evidence_kind=v_kind
       AND source_type=v_source
       AND source_reference=v_ref;
  END IF;

  RETURN jsonb_build_object(
    'decision',
      CASE WHEN x.status='pending' THEN 'proposed' ELSE 'existing' END,
    'evidence_id',x.id,
    'evidence_kind',x.evidence_kind,
    'status',x.status,
    'amount_cents',x.amount_cents,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.verify_commercial_evidence(
  p_evidence_id uuid,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF p_evidence_id IS NULL OR v_actor='' THEN
    RAISE EXCEPTION 'evidence id and actor required';
  END IF;

  SELECT * INTO x
    FROM public.commercial_evidence_registry
   WHERE id=p_evidence_id
   FOR UPDATE;

  IF NOT FOUND THEN RAISE EXCEPTION 'commercial evidence not found'; END IF;

  IF x.status='verified' THEN
    RETURN jsonb_build_object(
      'decision','existing_verification',
      'evidence_id',x.id,
      'status',x.status,
      'actual_revenue',false
    );
  END IF;

  IF x.status<>'pending' THEN
    RAISE EXCEPTION 'pending commercial evidence required';
  END IF;

  IF x.valid_until IS NOT NULL AND x.valid_until <= clock_timestamp() THEN
    RAISE EXCEPTION 'commercial evidence expired';
  END IF;

  IF x.source_type='buyer_stated' THEN
    IF x.closer_case_id IS NULL OR x.buyer_id IS NULL THEN
      RAISE EXCEPTION 'buyer-stated evidence requires buyer and closer case';
    END IF;
    IF COALESCE(x.evidence->>'reply_id','')='' THEN
      RAISE EXCEPTION 'buyer-stated evidence requires reply_id';
    END IF;
  ELSIF x.source_type='public_price' THEN
    IF COALESCE(x.evidence->>'source_url','')='' THEN
      RAISE EXCEPTION 'public price evidence requires source_url';
    END IF;
  ELSIF x.source_type='observed_contract' THEN
    IF COALESCE(x.evidence->>'contract_reference','')='' THEN
      RAISE EXCEPTION 'observed contract evidence requires contract_reference';
    END IF;
  ELSIF x.source_type='provider_invoice' THEN
    IF COALESCE(x.evidence->>'invoice_reference','')='' THEN
      RAISE EXCEPTION 'provider invoice evidence requires invoice_reference';
    END IF;
  ELSIF x.source_type='internal_actual' THEN
    IF COALESCE(x.evidence->>'cost_reference','')='' THEN
      RAISE EXCEPTION 'internal actual cost requires cost_reference';
    END IF;
  ELSIF x.source_type='founder_approved' THEN
    IF COALESCE(x.evidence->>'approval_reference','')='' THEN
      RAISE EXCEPTION 'founder-approved evidence requires approval_reference';
    END IF;
  END IF;

  UPDATE public.commercial_evidence_registry
     SET status='verified',
         verified_at=clock_timestamp(),
         verified_by=v_actor,
         updated_at=clock_timestamp()
   WHERE id=x.id
   RETURNING * INTO x;

  RETURN jsonb_build_object(
    'decision','verified',
    'evidence_id',x.id,
    'evidence_kind',x.evidence_kind,
    'status',x.status,
    'amount_cents',x.amount_cents,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.reject_commercial_evidence(
  p_evidence_id uuid,
  p_actor text,
  p_reason text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
  v_reason text := trim(COALESCE(p_reason,''));
BEGIN
  IF p_evidence_id IS NULL OR v_actor='' OR v_reason='' THEN
    RAISE EXCEPTION 'evidence id, actor and reason required';
  END IF;

  SELECT * INTO x
    FROM public.commercial_evidence_registry
   WHERE id=p_evidence_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'commercial evidence not found'; END IF;

  IF x.status<>'pending' THEN
    RETURN jsonb_build_object(
      'decision','existing',
      'evidence_id',x.id,
      'status',x.status,
      'actual_revenue',false
    );
  END IF;

  UPDATE public.commercial_evidence_registry
     SET status='rejected',
         rejected_at=clock_timestamp(),
         rejected_by=v_actor,
         rejection_reason=v_reason,
         updated_at=clock_timestamp()
   WHERE id=x.id
   RETURNING * INTO x;

  RETURN jsonb_build_object(
    'decision','rejected',
    'evidence_id',x.id,
    'status',x.status,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_verified_terms_evidence(
  p_fulfilment_order_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  p public.prospects%ROWTYPE;
  price public.commercial_evidence_registry%ROWTYPE;
  acq public.commercial_evidence_registry%ROWTYPE;
  fulfil public.commercial_evidence_registry%ROWTYPE;
BEGIN
  SELECT * INTO o
    FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;

  SELECT * INTO p FROM public.prospects WHERE id=o.prospect_id;

  SELECT * INTO price
    FROM public.commercial_evidence_registry e
   WHERE e.evidence_kind='price'
     AND e.status='verified'
     AND (e.valid_until IS NULL OR e.valid_until>clock_timestamp())
     AND (e.fulfilment_order_id IS NULL OR e.fulfilment_order_id=o.id)
     AND (e.buyer_id IS NULL OR e.buyer_id=o.buyer_id)
     AND (e.niche IS NULL OR e.niche=p.niche)
     AND (e.metro IS NULL OR e.metro=p.metro)
   ORDER BY
     (e.fulfilment_order_id=o.id) DESC,
     (e.buyer_id=o.buyer_id) DESC,
     e.observed_at DESC,
     e.id DESC
   LIMIT 1;

  SELECT * INTO acq
    FROM public.commercial_evidence_registry e
   WHERE e.evidence_kind='acquisition_cost'
     AND e.status='verified'
     AND (e.valid_until IS NULL OR e.valid_until>clock_timestamp())
     AND (e.fulfilment_order_id IS NULL OR e.fulfilment_order_id=o.id)
     AND (e.niche IS NULL OR e.niche=p.niche)
     AND (e.metro IS NULL OR e.metro=p.metro)
   ORDER BY
     (e.fulfilment_order_id=o.id) DESC,
     e.observed_at DESC,
     e.id DESC
   LIMIT 1;

  SELECT * INTO fulfil
    FROM public.commercial_evidence_registry e
   WHERE e.evidence_kind='fulfilment_cost'
     AND e.status='verified'
     AND (e.valid_until IS NULL OR e.valid_until>clock_timestamp())
     AND (e.fulfilment_order_id IS NULL OR e.fulfilment_order_id=o.id)
     AND (e.niche IS NULL OR e.niche=p.niche)
     AND (e.metro IS NULL OR e.metro=p.metro)
   ORDER BY
     (e.fulfilment_order_id=o.id) DESC,
     e.observed_at DESC,
     e.id DESC
   LIMIT 1;

  RETURN jsonb_build_object(
    'fulfilment_order_id',o.id,
    'buyer_id',o.buyer_id,
    'prospect_id',o.prospect_id,
    'niche',p.niche,
    'metro',p.metro,
    'price',CASE WHEN price.id IS NULL THEN NULL ELSE jsonb_build_object(
      'evidence_id',price.id,
      'amount_cents',price.amount_cents,
      'unit',price.unit,
      'source_type',price.source_type,
      'source_reference',price.source_reference,
      'observed_at',price.observed_at
    ) END,
    'acquisition_cost',CASE WHEN acq.id IS NULL THEN NULL ELSE jsonb_build_object(
      'evidence_id',acq.id,
      'amount_cents',acq.amount_cents,
      'unit',acq.unit,
      'source_type',acq.source_type,
      'source_reference',acq.source_reference,
      'observed_at',acq.observed_at
    ) END,
    'fulfilment_cost',CASE WHEN fulfil.id IS NULL THEN NULL ELSE jsonb_build_object(
      'evidence_id',fulfil.id,
      'amount_cents',fulfil.amount_cents,
      'unit',fulfil.unit,
      'source_type',fulfil.source_type,
      'source_reference',fulfil.source_reference,
      'observed_at',fulfil.observed_at
    ) END,
    'pricing_authority','none',
    'settlement_authority','none',
    'actual_revenue',false
  );
END;
$$;

REVOKE ALL ON FUNCTION public.propose_commercial_evidence(
  text,uuid,uuid,uuid,text,text,bigint,text,text,text,jsonb,timestamptz,timestamptz
) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.verify_commercial_evidence(uuid,text)
  FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.reject_commercial_evidence(uuid,text,text)
  FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.get_verified_terms_evidence(uuid)
  FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.propose_commercial_evidence(
  text,uuid,uuid,uuid,text,text,bigint,text,text,text,jsonb,timestamptz,timestamptz
) TO service_role;
GRANT EXECUTE ON FUNCTION public.verify_commercial_evidence(uuid,text)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.reject_commercial_evidence(uuid,text,text)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.get_verified_terms_evidence(uuid)
  TO service_role;

COMMIT;
