-- Read-only commercial evidence review surface for the dedicated verifier.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_commercial_evidence_review(
  p_evidence_id uuid
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
  SELECT jsonb_build_object(
    'evidence_id',e.id,
    'evidence_kind',e.evidence_kind,
    'status',e.status,
    'buyer_id',e.buyer_id,
    'closer_case_id',e.closer_case_id,
    'fulfilment_order_id',e.fulfilment_order_id,
    'niche',e.niche,
    'metro',e.metro,
    'amount_cents',e.amount_cents,
    'currency',e.currency,
    'unit',e.unit,
    'source_type',e.source_type,
    'source_reference',e.source_reference,
    'evidence',e.evidence,
    'observed_at',e.observed_at,
    'valid_until',e.valid_until,
    'verified_at',e.verified_at,
    'verified_by',e.verified_by,
    'rejected_at',e.rejected_at,
    'rejected_by',e.rejected_by,
    'rejection_reason',e.rejection_reason,
    'actual_revenue',false
  )
  FROM public.commercial_evidence_registry e
  WHERE e.id=p_evidence_id;
$$;

REVOKE ALL ON FUNCTION
  public.get_commercial_evidence_review(uuid)
FROM PUBLIC, anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION
  public.get_commercial_evidence_review(uuid)
TO empire_commercial_evidence_verifier;

COMMIT;
