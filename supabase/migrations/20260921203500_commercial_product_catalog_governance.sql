-- Governed lifecycle for the commercial product/cost catalog.
-- Proposal may be automated. Verification is separated behind an inert,
-- dedicated verifier identity. No payment or revenue authority is granted.

BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_commercial_catalog_verifier'
  ) THEN
    CREATE ROLE empire_commercial_catalog_verifier
      NOLOGIN NOINHERIT;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_commercial_catalog_verifier_login'
  ) THEN
    CREATE ROLE empire_commercial_catalog_verifier_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_commercial_catalog_verifier_login PASSWORD NULL;
GRANT empire_commercial_catalog_verifier
TO empire_commercial_catalog_verifier_login;
GRANT USAGE ON SCHEMA public
TO empire_commercial_catalog_verifier;

-- The managed_service offer already exists in governed GTM.
-- Seed product identity only: all economics remain UNKNOWN.
INSERT INTO public.commercial_products(
  product_code,
  product_name,
  product_family,
  billing_model,
  active,
  configuration,
  currency,
  catalog_state,
  provenance
) VALUES (
  'managed_service',
  'Managed Service',
  'managed_services',
  'unknown',
  true,
  '{}'::jsonb,
  'USD',
  'UNKNOWN',
  '{"source":"canonical_offer_key","offer_key":"managed_service"}'::jsonb
)
ON CONFLICT (product_code) DO NOTHING;

INSERT INTO public.commercial_product_versions(
  product_id,
  version,
  version_state,
  billing_model,
  currency,
  price_basis,
  acquisition_cost_basis,
  fulfilment_cost_basis,
  margin_policy,
  provenance,
  evidence_refs
)
SELECT
  p.id,
  1,
  'UNKNOWN',
  'unknown',
  'USD',
  '{"state":"UNKNOWN"}'::jsonb,
  '{"state":"UNKNOWN"}'::jsonb,
  '{"state":"UNKNOWN"}'::jsonb,
  '{"state":"UNKNOWN"}'::jsonb,
  '{"source":"canonical_offer_key","offer_key":"managed_service"}'::jsonb,
  '["gtm_offer_key:managed_service"]'::jsonb
FROM public.commercial_products p
WHERE p.product_code='managed_service'
  AND NOT EXISTS (
    SELECT 1
    FROM public.commercial_product_versions v
    WHERE v.product_id=p.id
  );

CREATE OR REPLACE FUNCTION public.register_commercial_product_identity(
  p_product_code text,
  p_product_name text,
  p_product_family text,
  p_billing_model text,
  p_configuration jsonb,
  p_provenance jsonb,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $
DECLARE
  product_row public.commercial_products%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_product_code,''))=''
     OR trim(COALESCE(p_product_name,''))=''
     OR trim(COALESCE(p_product_family,''))=''
     OR trim(COALESCE(p_billing_model,''))=''
     OR trim(COALESCE(p_actor,''))='' THEN
    RAISE EXCEPTION 'complete product identity and actor required';
  END IF;

  IF jsonb_typeof(COALESCE(p_configuration,'{}'::jsonb))<>'object'
     OR jsonb_typeof(COALESCE(p_provenance,'{}'::jsonb))<>'object' THEN
    RAISE EXCEPTION 'configuration and provenance must be objects';
  END IF;

  INSERT INTO public.commercial_products(
    product_code,
    product_name,
    product_family,
    billing_model,
    active,
    configuration,
    currency,
    catalog_state,
    provenance
  ) VALUES (
    trim(p_product_code),
    trim(p_product_name),
    trim(p_product_family),
    trim(p_billing_model),
    true,
    COALESCE(p_configuration,'{}'::jsonb),
    'USD',
    'UNKNOWN',
    COALESCE(p_provenance,'{}'::jsonb)
  )
  ON CONFLICT (product_code) DO UPDATE
  SET product_name=excluded.product_name,
      product_family=excluded.product_family,
      configuration=excluded.configuration,
      provenance=public.commercial_products.provenance || excluded.provenance,
      updated_at=clock_timestamp()
  RETURNING * INTO product_row;

  INSERT INTO public.commercial_product_catalog_events(
    product_id,event_type,actor,payload
  ) VALUES (
    product_row.id,
    'identity_synchronized',
    p_actor,
    jsonb_build_object(
      'product_code',product_row.product_code,
      'catalog_state',product_row.catalog_state,
      'economics_mutated',false,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','identity_synchronized',
    'product_id',product_row.id,
    'product_code',product_row.product_code,
    'catalog_state',product_row.catalog_state,
    'economics_mutated',false,
    'actual_revenue',false
  );
END;
$;

CREATE OR REPLACE FUNCTION public.propose_commercial_product_version(
  p_product_code text,
  p_billing_model text,
  p_currency text,
  p_price_basis jsonb,
  p_acquisition_cost_basis jsonb,
  p_fulfilment_cost_basis jsonb,
  p_margin_policy jsonb,
  p_provenance jsonb,
  p_evidence_refs jsonb,
  p_effective_from timestamptz,
  p_effective_until timestamptz,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  product_row public.commercial_products%ROWTYPE;
  version_row public.commercial_product_versions%ROWTYPE;
  next_version integer;
BEGIN
  IF trim(COALESCE(p_actor,''))='' THEN
    RAISE EXCEPTION 'actor required';
  END IF;
  IF trim(COALESCE(p_billing_model,''))='' THEN
    RAISE EXCEPTION 'billing model required';
  END IF;
  IF trim(COALESCE(p_currency,''))='' THEN
    RAISE EXCEPTION 'currency required';
  END IF;

  IF jsonb_typeof(COALESCE(
       p_price_basis,'{"state":"UNKNOWN"}'::jsonb
     )) <> 'object'
     OR jsonb_typeof(COALESCE(
       p_acquisition_cost_basis,'{"state":"UNKNOWN"}'::jsonb
     )) <> 'object'
     OR jsonb_typeof(COALESCE(
       p_fulfilment_cost_basis,'{"state":"UNKNOWN"}'::jsonb
     )) <> 'object'
     OR jsonb_typeof(COALESCE(
       p_margin_policy,'{"state":"UNKNOWN"}'::jsonb
     )) <> 'object'
     OR jsonb_typeof(COALESCE(
       p_provenance,'{}'::jsonb
     )) <> 'object'
     OR jsonb_typeof(COALESCE(
       p_evidence_refs,'[]'::jsonb
     )) <> 'array' THEN
    RAISE EXCEPTION 'catalog basis/provenance/evidence shapes invalid';
  END IF;

  IF p_effective_until IS NOT NULL
     AND p_effective_from IS NOT NULL
     AND p_effective_until <= p_effective_from THEN
    RAISE EXCEPTION 'effective_until must be after effective_from';
  END IF;

  SELECT * INTO product_row
  FROM public.commercial_products
  WHERE product_code=trim(p_product_code)
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'commercial product not found';
  END IF;

  SELECT COALESCE(max(version),0)+1
  INTO next_version
  FROM public.commercial_product_versions
  WHERE product_id=product_row.id;

  INSERT INTO public.commercial_product_versions(
    product_id,
    version,
    version_state,
    billing_model,
    currency,
    price_basis,
    acquisition_cost_basis,
    fulfilment_cost_basis,
    margin_policy,
    provenance,
    evidence_refs,
    effective_from,
    effective_until
  ) VALUES (
    product_row.id,
    next_version,
    'PENDING',
    trim(p_billing_model),
    upper(trim(p_currency)),
    COALESCE(p_price_basis,'{"state":"UNKNOWN"}'::jsonb),
    COALESCE(p_acquisition_cost_basis,'{"state":"UNKNOWN"}'::jsonb),
    COALESCE(p_fulfilment_cost_basis,'{"state":"UNKNOWN"}'::jsonb),
    COALESCE(p_margin_policy,'{"state":"UNKNOWN"}'::jsonb),
    COALESCE(p_provenance,'{}'::jsonb),
    COALESCE(p_evidence_refs,'[]'::jsonb),
    p_effective_from,
    p_effective_until
  )
  RETURNING * INTO version_row;

  INSERT INTO public.commercial_product_catalog_events(
    product_id,
    product_version_id,
    event_type,
    actor,
    payload
  ) VALUES (
    product_row.id,
    version_row.id,
    'version_proposed',
    p_actor,
    jsonb_build_object(
      'version',version_row.version,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','proposed',
    'product_code',product_row.product_code,
    'version_id',version_row.id,
    'version',version_row.version,
    'version_state',version_row.version_state,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_commercial_product_version_review(
  p_version_id uuid
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
  SELECT jsonb_build_object(
    'version_id',v.id,
    'product_id',p.id,
    'product_code',p.product_code,
    'product_name',p.product_name,
    'active',p.active,
    'catalog_state',p.catalog_state,
    'version',v.version,
    'version_state',v.version_state,
    'billing_model',v.billing_model,
    'currency',v.currency,
    'price_basis',v.price_basis,
    'acquisition_cost_basis',v.acquisition_cost_basis,
    'fulfilment_cost_basis',v.fulfilment_cost_basis,
    'margin_policy',v.margin_policy,
    'provenance',v.provenance,
    'evidence_refs',v.evidence_refs,
    'effective_from',v.effective_from,
    'effective_until',v.effective_until,
    'actual_revenue',false
  )
  FROM public.commercial_product_versions v
  JOIN public.commercial_products p ON p.id=v.product_id
  WHERE v.id=p_version_id;
$$;

CREATE OR REPLACE FUNCTION public.decide_commercial_product_version(
  p_version_id uuid,
  p_decision text,
  p_actor text,
  p_reason text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  version_row public.commercial_product_versions%ROWTYPE;
  product_row public.commercial_products%ROWTYPE;
  decision text := lower(trim(COALESCE(p_decision,'')));
  price_cents bigint;
  acquisition_cents bigint;
  fulfilment_cents bigint;
  minimum_margin_bps integer;
  realized_margin_bps numeric;
BEGIN
  IF decision NOT IN ('verified','rejected') THEN
    RAISE EXCEPTION 'decision must be verified or rejected';
  END IF;
  IF trim(COALESCE(p_actor,''))='' THEN
    RAISE EXCEPTION 'actor required';
  END IF;

  SELECT * INTO version_row
  FROM public.commercial_product_versions
  WHERE id=p_version_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'catalog version not found';
  END IF;
  IF version_row.version_state<>'PENDING' THEN
    RAISE EXCEPTION 'pending catalog version required';
  END IF;

  SELECT * INTO product_row
  FROM public.commercial_products
  WHERE id=version_row.product_id
  FOR UPDATE;

  IF decision='verified' THEN
    IF COALESCE(version_row.price_basis->>'state','UNKNOWN')<>'VERIFIED'
       OR COALESCE(
         version_row.acquisition_cost_basis->>'state','UNKNOWN'
       )<>'VERIFIED'
       OR COALESCE(
         version_row.fulfilment_cost_basis->>'state','UNKNOWN'
       )<>'VERIFIED'
       OR COALESCE(
         version_row.margin_policy->>'state','UNKNOWN'
       )<>'VERIFIED'
       OR jsonb_typeof(version_row.price_basis->'amount_cents')<>'number'
       OR jsonb_typeof(
         version_row.acquisition_cost_basis->'amount_cents'
       )<>'number'
       OR jsonb_typeof(
         version_row.fulfilment_cost_basis->'amount_cents'
       )<>'number'
       OR jsonb_typeof(
         version_row.margin_policy->'minimum_margin_bps'
       )<>'number'
       OR trim(COALESCE(version_row.price_basis->>'unit',''))=''
       OR trim(COALESCE(
         version_row.acquisition_cost_basis->>'unit',''
       ))=''
       OR trim(COALESCE(
         version_row.fulfilment_cost_basis->>'unit',''
       ))=''
       OR jsonb_typeof(version_row.evidence_refs)<>'array'
       OR jsonb_array_length(version_row.evidence_refs)=0 THEN
      RAISE EXCEPTION
        'verified evidence-backed price/cost/margin basis required';
    END IF;

    price_cents := (version_row.price_basis->>'amount_cents')::bigint;
    acquisition_cents := (
      version_row.acquisition_cost_basis->>'amount_cents'
    )::bigint;
    fulfilment_cents := (
      version_row.fulfilment_cost_basis->>'amount_cents'
    )::bigint;
    minimum_margin_bps := (
      version_row.margin_policy->>'minimum_margin_bps'
    )::integer;

    IF price_cents <= 0
       OR acquisition_cents < 0
       OR fulfilment_cents < 0
       OR minimum_margin_bps < 0
       OR minimum_margin_bps > 10000 THEN
      RAISE EXCEPTION 'invalid verified product economics';
    END IF;

    IF lower(version_row.price_basis->>'unit')
       <> lower(version_row.acquisition_cost_basis->>'unit')
       OR lower(version_row.price_basis->>'unit')
       <> lower(version_row.fulfilment_cost_basis->>'unit') THEN
      RAISE EXCEPTION 'price and cost units must match';
    END IF;

    IF upper(COALESCE(version_row.price_basis->>'currency',''))
       <> upper(version_row.currency)
       OR upper(COALESCE(
         version_row.acquisition_cost_basis->>'currency',''
       )) <> upper(version_row.currency)
       OR upper(COALESCE(
         version_row.fulfilment_cost_basis->>'currency',''
       )) <> upper(version_row.currency) THEN
      RAISE EXCEPTION 'price and cost currency must match catalog currency';
    END IF;

    IF price_cents <= acquisition_cents + fulfilment_cents THEN
      RAISE EXCEPTION 'verified product economics require positive margin';
    END IF;

    realized_margin_bps := (
      (price_cents - acquisition_cents - fulfilment_cents)::numeric
      * 10000
      / price_cents::numeric
    );
    IF realized_margin_bps < minimum_margin_bps THEN
      RAISE EXCEPTION 'verified product economics miss minimum margin policy';
    END IF;

    UPDATE public.commercial_product_versions
    SET version_state='RETIRED',
        updated_at=clock_timestamp()
    WHERE product_id=product_row.id
      AND version_state='VERIFIED'
      AND id<>version_row.id;

    UPDATE public.commercial_product_versions
    SET version_state='VERIFIED',
        verified_at=clock_timestamp(),
        verified_by=p_actor,
        updated_at=clock_timestamp()
    WHERE id=version_row.id;

    UPDATE public.commercial_products
    SET billing_model=version_row.billing_model,
        currency=version_row.currency,
        catalog_state='VERIFIED',
        provenance=version_row.provenance,
        updated_at=clock_timestamp()
    WHERE id=product_row.id;
  ELSE
    UPDATE public.commercial_product_versions
    SET version_state='REJECTED',
        rejected_at=clock_timestamp(),
        rejected_by=p_actor,
        rejection_reason=COALESCE(
          NULLIF(trim(p_reason),''),
          'rejected'
        ),
        updated_at=clock_timestamp()
    WHERE id=version_row.id;
  END IF;

  INSERT INTO public.commercial_product_catalog_events(
    product_id,
    product_version_id,
    event_type,
    actor,
    payload
  ) VALUES (
    product_row.id,
    version_row.id,
    'version_'||decision,
    p_actor,
    jsonb_build_object(
      'reason',p_reason,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision',decision,
    'product_code',product_row.product_code,
    'version_id',version_row.id,
    'version',version_row.version,
    'actual_revenue',false
  );
END;
$$;

REVOKE ALL ON FUNCTION public.register_commercial_product_identity(
  text,text,text,text,jsonb,jsonb,text
) FROM PUBLIC,anon,authenticated;

REVOKE ALL ON FUNCTION public.propose_commercial_product_version(
  text,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,jsonb,
  timestamptz,timestamptz,text
) FROM PUBLIC,anon,authenticated;

REVOKE ALL ON FUNCTION public.get_commercial_product_version_review(uuid)
FROM PUBLIC,anon,authenticated,service_role;

REVOKE ALL ON FUNCTION public.decide_commercial_product_version(
  uuid,text,text,text
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.register_commercial_product_identity(
  text,text,text,text,jsonb,jsonb,text
) TO service_role;

GRANT EXECUTE ON FUNCTION public.propose_commercial_product_version(
  text,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,jsonb,
  timestamptz,timestamptz,text
) TO service_role;

GRANT EXECUTE ON FUNCTION public.get_commercial_product_version_review(uuid)
TO empire_commercial_catalog_verifier;

GRANT EXECUTE ON FUNCTION public.decide_commercial_product_version(
  uuid,text,text,text
) TO empire_commercial_catalog_verifier;

GRANT EXECUTE ON FUNCTION public.get_commercial_product_catalog(
  text,integer
) TO empire_commercial_catalog_verifier;

GRANT EXECUTE ON FUNCTION public.get_commercial_product_readiness(text)
TO empire_commercial_catalog_verifier;

ALTER ROLE empire_commercial_catalog_verifier_login
  SET statement_timeout='15s';

ALTER ROLE empire_commercial_catalog_verifier_login
  SET idle_in_transaction_session_timeout='30s';

COMMIT;
