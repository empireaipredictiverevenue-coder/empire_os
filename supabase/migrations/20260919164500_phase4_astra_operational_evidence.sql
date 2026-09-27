-- Phase 4 canonical operational evidence for Astra.
-- Staged only: no production application or credential activation.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_astra_operational_evidence()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
WITH latest_qualification AS (
  SELECT DISTINCT ON (q.prospect_id)
    q.prospect_id,
    q.score,
    q.tier,
    q.status,
    q.scoring_version,
    q.evidence_confidence,
    q.scored_at,
    q.id
  FROM public.prospect_qualifications q
  ORDER BY
    q.prospect_id,
    CASE WHEN q.scoring_version='v2' THEN 0 ELSE 1 END,
    q.scored_at DESC,
    q.id DESC
),
owned AS (
  SELECT count(*)::bigint AS value
  FROM public.prospect_entity_links l
  WHERE l.active=true
    AND NOT EXISTS (
      SELECT 1
      FROM public.fulfilment_orders f
      WHERE f.prospect_id=l.prospect_id
        AND f.state NOT IN ('rejected','cancelled','outcome_captured')
    )
),
qualified AS (
  SELECT count(*)::bigint AS value
  FROM latest_qualification q
  JOIN public.prospect_entity_links l
    ON l.prospect_id=q.prospect_id
   AND l.active=true
  WHERE q.status='scored'
    AND lower(q.tier) IN ('hot','warm')
    AND q.score >= 50
    AND (
      q.scoring_version='v1'
      OR (
        q.scoring_version='v2'
        AND q.evidence_confidence >= 0.50
      )
    )
    AND NOT EXISTS (
      SELECT 1
      FROM public.fulfilment_orders f
      WHERE f.prospect_id=q.prospect_id
        AND f.state NOT IN ('rejected','cancelled','outcome_captured')
    )
),
capacity AS (
  SELECT coalesce(sum(
    greatest(coalesce(b.daily_cap,0)-coalesce(b.calls_today,0),0)
  ),0)::bigint AS value
  FROM public.buyers b
  WHERE coalesce(b.is_active,false)=true
    AND lower(trim(coalesce(b.status,''))) NOT IN ('inactive','disabled')
    AND lower(trim(coalesce(b.commercial_activation_state,'')))='activated'
),
reply_backlog AS (
  SELECT count(*)::bigint AS value
  FROM public.outbound_replies r
  WHERE r.classification='unclassified'
),
failed AS (
  SELECT count(*)::bigint AS value
  FROM public.gtm_jobs j
  WHERE j.status='failed'
),
buyer_due AS (
  SELECT count(*)::bigint AS value
  FROM public.buyer_candidate_reviews r
  WHERE r.status='pending'
)
SELECT jsonb_build_object(
  'replies_waiting', reply_backlog.value,
  'failed_jobs', failed.value,
  'owned_inventory_count', owned.value,
  'qualified_unallocated_count', qualified.value,
  'active_buyer_capacity', capacity.value,
  'buyer_candidates_due', buyer_due.value,
  'observed_at', clock_timestamp()
)
FROM owned,qualified,capacity,reply_backlog,failed,buyer_due;
$$;

REVOKE ALL ON FUNCTION public.get_astra_operational_evidence()
  FROM PUBLIC,anon,authenticated,
       empire_outcome_recorder,empire_revenue_recognizer,
       empire_outcome_reader;
GRANT EXECUTE ON FUNCTION public.get_astra_operational_evidence()
  TO empire_astra_observer,service_role;

COMMENT ON FUNCTION public.get_astra_operational_evidence() IS
'Phase 4 read-only canonical operational evidence for Astra; no policy bindings or inferred zeros.';

COMMIT;
