-- Remove the operational dependency on a dedicated catalog-verifier login.
-- Service role may invoke only a deterministic verify-only wrapper.
BEGIN;

CREATE OR REPLACE FUNCTION public.auto_verify_commercial_product_version(
  p_version_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  review jsonb;
  result jsonb;
BEGIN
  SELECT public.get_commercial_product_version_review(p_version_id)
  INTO review;

  IF review IS NULL THEN
    RAISE EXCEPTION 'catalog version not found';
  END IF;

  IF COALESCE(review->>'version_state','') <> 'PENDING' THEN
    RAISE EXCEPTION 'pending catalog version required';
  END IF;

  IF COALESCE(review->'price_basis'->>'state','UNKNOWN') <> 'VERIFIED'
     OR COALESCE(review->'acquisition_cost_basis'->>'state','UNKNOWN') <> 'VERIFIED'
     OR COALESCE(review->'fulfilment_cost_basis'->>'state','UNKNOWN') <> 'VERIFIED'
     OR COALESCE(review->'margin_policy'->>'state','UNKNOWN') <> 'VERIFIED'
     OR COALESCE(jsonb_array_length(COALESCE(review->'evidence_refs','[]'::jsonb)),0) < 1 THEN
    RAISE EXCEPTION 'verified catalog evidence required';
  END IF;

  IF COALESCE(review->'price_basis'->>'source_type','') <> 'founder_approved'
     OR COALESCE(review->'acquisition_cost_basis'->>'source_type','') <> 'founder_approved'
     OR COALESCE(review->'fulfilment_cost_basis'->>'source_type','') <> 'founder_approved'
     OR COALESCE(review->'margin_policy'->>'basis_type','') <> 'founder_policy' THEN
    RAISE EXCEPTION 'founder-approved economics required';
  END IF;

  SELECT public.decide_commercial_product_version(
    p_version_id,
    'verified',
    'commercial_catalog_auto_verifier',
    'Deterministic verification of founder-approved product economics.'
  )
  INTO result;

  RETURN result || jsonb_build_object(
    'authority','deterministic_catalog_verification_only',
    'payment_mutation',false,
    'revenue_recognition',false
  );
END;
$$;

REVOKE ALL ON FUNCTION public.auto_verify_commercial_product_version(uuid)
FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.auto_verify_commercial_product_version(uuid)
TO service_role;

COMMENT ON FUNCTION public.auto_verify_commercial_product_version(uuid)
IS 'Deterministic verify-only catalog transition for already founder-approved economics. No reject, payment, terms, or revenue authority.';

COMMIT;
