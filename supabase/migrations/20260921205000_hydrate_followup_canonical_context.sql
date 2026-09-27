-- Hydrate due follow-ups from current canonical buyer/prospect evidence.
-- Sequence timing, suppression, reply and negative-delivery gates are unchanged.

BEGIN;

CREATE OR REPLACE FUNCTION public.list_due_outbound_followups(
    p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path=''
AS $$
WITH roots AS (
    SELECT
        i.id AS root_intent_id,
        i.prospect_id,
        i.entity_id,
        i.buyer_id,
        i.opportunity_id,
        i.recipient,
        i.normalized_recipient,
        i.offer_key,
        i.subject AS root_subject,
        i.metadata,
        (
            SELECT max(e.occurred_at)
            FROM public.outbound_events e
            WHERE e.intent_id=i.id
              AND e.event_type='delivered'
        ) AS delivered_at
    FROM public.outbound_intents i
    WHERE i.channel='email'
      AND i.status='delivered'
      AND COALESCE(
        i.metadata->>'sequence_kind',
        'first_touch'
      ) <> 'followup'
      AND i.metadata ? 'buyer_candidate_review_id'
),
eligible AS (
    SELECT
        r.*,
        COALESCE((
            SELECT count(*)
            FROM public.outbound_intents f
            WHERE f.metadata->>'sequence_kind'='followup'
              AND f.metadata->>'root_intent_id'=r.root_intent_id::text
              AND f.status NOT IN ('cancelled','rejected')
        ),0)::integer AS followup_count,
        (
            SELECT max(e.occurred_at)
            FROM public.outbound_intents f
            JOIN public.outbound_events e ON e.intent_id=f.id
            WHERE f.metadata->>'sequence_kind'='followup'
              AND f.metadata->>'root_intent_id'=r.root_intent_id::text
              AND f.metadata->>'followup_step'='1'
              AND e.event_type='delivered'
        ) AS first_followup_delivered_at
    FROM roots r
    WHERE r.delivered_at IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM public.outbound_suppressions s
          WHERE s.normalized_contact=r.normalized_recipient
      )
      AND NOT EXISTS (
          SELECT 1
          FROM public.outbound_replies rep
          JOIN public.outbound_intents ri ON ri.id=rep.intent_id
          WHERE ri.normalized_recipient=r.normalized_recipient
      )
      AND NOT EXISTS (
          SELECT 1
          FROM public.outbound_events e
          JOIN public.outbound_intents ei ON ei.id=e.intent_id
          WHERE ei.normalized_recipient=r.normalized_recipient
            AND e.event_type IN (
              'bounced','complained','failed','suppressed'
            )
      )
),
due AS (
    SELECT
        e.*,
        CASE
          WHEN e.followup_count=0
               AND e.delivered_at <= now()-interval '72 hours'
            THEN 1
          WHEN e.followup_count=1
               AND e.first_followup_delivered_at IS NOT NULL
               AND e.delivered_at <= now()-interval '168 hours'
            THEN 2
          ELSE NULL
        END AS followup_step
    FROM eligible e
),
hydrated AS (
    SELECT
        d.*,
        review.id AS current_review_id,
        review.company_score AS current_company_score,
        review.decision_score AS current_decision_score,
        (
          COALESCE(d.metadata->'candidate_evidence','{}'::jsonb)
          || COALESCE(review.evidence,'{}'::jsonb)
          || jsonb_strip_nulls(jsonb_build_object(
               'contact_name',review.contact_name,
               'contact_title',review.contact_title,
               'contact_source',review.evidence->>'contact_source'
             ))
          || jsonb_strip_nulls(jsonb_build_object(
               'business_name',prospect.business_name,
               'niche',prospect.niche,
               'metro',prospect.metro,
               'website',prospect.website,
               'phone',prospect.phone,
               'rating',prospect.rating,
               'review_count',prospect.review_count,
               'buy_signal_score',prospect.buy_signal_score
             ))
        ) AS hydrated_candidate_evidence
    FROM due d
    LEFT JOIN public.buyer_candidate_reviews review
      ON review.id::text=d.metadata->>'buyer_candidate_review_id'
    LEFT JOIN public.prospects prospect
      ON prospect.id=d.prospect_id
    WHERE d.followup_step IS NOT NULL
)
SELECT COALESCE(
    jsonb_agg(
        jsonb_build_object(
            'root_intent_id',h.root_intent_id,
            'review_id',COALESCE(
              h.current_review_id::text,
              h.metadata->>'buyer_candidate_review_id'
            ),
            'recipient',h.recipient,
            'normalized_recipient',h.normalized_recipient,
            'offer_key',h.offer_key,
            'root_subject',h.root_subject,
            'delivered_at',h.delivered_at,
            'followup_step',h.followup_step,
            'candidate_evidence',h.hydrated_candidate_evidence,
            'recipient_locale',
              h.hydrated_candidate_evidence->'locale',
            'company_score',COALESCE(
              to_jsonb(h.current_company_score),
              h.metadata->'company_score'
            ),
            'decision_score',COALESCE(
              to_jsonb(h.current_decision_score),
              h.metadata->'decision_score'
            )
        )
        ORDER BY h.delivered_at,h.root_intent_id
    ),
    '[]'::jsonb
)
FROM (
    SELECT *
    FROM hydrated
    ORDER BY delivered_at,root_intent_id
    LIMIT LEAST(GREATEST(COALESCE(p_limit,25),1),100)
) h;
$$;

REVOKE ALL ON FUNCTION public.list_due_outbound_followups(integer)
FROM PUBLIC,anon,authenticated,empire_outbound_approver,
     empire_outbound_sender,empire_reply_ingest;

GRANT EXECUTE ON FUNCTION public.list_due_outbound_followups(integer)
TO service_role;

COMMENT ON FUNCTION public.list_due_outbound_followups(integer) IS
'Lists due governed no-reply follow-ups with current canonical review and prospect context.';

COMMIT;
