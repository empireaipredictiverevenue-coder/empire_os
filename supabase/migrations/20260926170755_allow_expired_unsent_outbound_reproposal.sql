-- Allow safe reproposal after an outbound intent expires without a send.
-- Reviews remain blocked by suppression, live pending/approved intents, or any
-- real send/delivery/failure/suppression history.
BEGIN;

CREATE OR REPLACE FUNCTION public.list_buyer_reviews_for_outbound(
    p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path=''
AS $function$
  SELECT COALESCE(
    jsonb_agg(to_jsonb(q) ORDER BY q.reviewed_at, q.id),
    '[]'::jsonb
  )
  FROM (
    SELECT
      r.id,
      r.prospect_id,
      r.entity_id,
      r.contact_name,
      r.contact_title,
      r.contact_email,
      r.offer_key,
      r.company_score,
      r.decision_score,
      r.evidence,
      r.reviewed_at
    FROM public.buyer_candidate_reviews r
    WHERE r.status='approved'
      AND r.reviewed_at >= clock_timestamp()-interval '7 days'
      AND COALESCE(lower(r.evidence->>'outreach_ready'),'false')='true'
      AND NOT EXISTS (
        SELECT 1
        FROM public.outbound_suppressions s
        WHERE s.normalized_contact=lower(trim(r.contact_email))
      )
      AND NOT EXISTS (
        SELECT 1
        FROM public.outbound_intents i
        WHERE i.normalized_recipient=lower(trim(r.contact_email))
          AND (
            i.status IN (
              'sending','sent','delivered','replied',
              'bounced','failed','suppressed'
            )
            OR (
              i.status IN ('pending_approval','approved')
              AND i.expires_at > clock_timestamp()
            )
          )
      )
    ORDER BY r.reviewed_at,r.id
    LIMIT LEAST(GREATEST(COALESCE(p_limit,25),1),100)
  ) q;
$function$;

COMMENT ON FUNCTION public.list_buyer_reviews_for_outbound(integer) IS
'Lists fresh approved outreach-ready buyer reviews with no suppression, no actual outbound history, and no still-live pending/approved intent. Expired unsent intents do not permanently block safe reproposal.';

COMMIT;
