-- Read-only canonical commercial funnel projection for Founder Console.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_founder_commercial_funnel()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
SELECT jsonb_build_object(
  'schema_version','empire.founder_commercial_funnel.v1',
  'generated_at',clock_timestamp(),
  'counts',jsonb_build_object(
    'prospect_acquisitions',(
      SELECT count(*) FROM public.prospect_acquisitions
    ),
    'buyer_reviews',(
      SELECT count(*) FROM public.buyer_candidate_reviews
    ),
    'buyer_reviews_approved',(
      SELECT count(*) FROM public.buyer_candidate_reviews
      WHERE status='approved'
    ),
    'outbound_intents',(
      SELECT count(*) FROM public.outbound_intents
    ),
    'outbound_delivered',(
      SELECT count(*) FROM public.outbound_intents
      WHERE status='delivered'
    ),
    'commercial_replies',(
      SELECT count(*) FROM public.outbound_replies
      WHERE classification IN ('positive','question','objection')
    ),
    'unsubscribe_replies',(
      SELECT count(*) FROM public.outbound_replies
      WHERE classification='unsubscribe'
    ),
    'closer_cases',(
      SELECT count(*) FROM public.closer_cases
    ),
    'commercial_terms_reviews',(
      SELECT count(*) FROM public.commercial_terms_reviews
    ),
    'commercial_terms_approved',(
      SELECT count(*) FROM public.commercial_terms_reviews
      WHERE status='approved'
    ),
    'payment_requests',(
      SELECT count(*) FROM public.bsc_payment_requests
    ),
    'verified_payment_evidence',(
      SELECT count(*) FROM public.bsc_payment_evidence
    ),
    'fulfilment_orders',(
      SELECT count(*) FROM public.fulfilment_orders
    ),
    'fulfilled_orders',(
      SELECT count(*) FROM public.fulfilment_orders
      WHERE state IN (
        'delivered','confirmed','invoiced','paid','settled','outcome_captured'
      )
    ),
    'commercial_outcomes',(
      SELECT count(*) FROM public.commercial_outcomes
    ),
    'recognized_revenue_events',(
      SELECT count(*) FROM public.commercial_events
      WHERE event_type='revenue_recognized'
    )
  ),
  'reply_classification_counts',COALESCE((
    SELECT jsonb_object_agg(classification,n)
    FROM (
      SELECT classification,count(*)::bigint AS n
      FROM public.outbound_replies
      GROUP BY classification
    ) q
  ),'{}'::jsonb),
  'outbound_status_counts',COALESCE((
    SELECT jsonb_object_agg(status,n)
    FROM (
      SELECT status,count(*)::bigint AS n
      FROM public.outbound_intents
      GROUP BY status
    ) q
  ),'{}'::jsonb),
  'recognized_revenue_cents',COALESCE((
    SELECT sum(COALESCE(amount_cents,0))
    FROM public.commercial_events
    WHERE event_type='revenue_recognized'
  ),0),
  'realized_margin_cents',COALESCE((
    SELECT sum(COALESCE(margin_cents,0))
    FROM public.commercial_events
    WHERE event_type='revenue_recognized'
  ),0),
  'actual_revenue',(
    SELECT EXISTS(
      SELECT 1
      FROM public.commercial_events
      WHERE event_type='revenue_recognized'
    )
  ),
  'execution_authority','none'
);
$$;

REVOKE ALL ON FUNCTION public.get_founder_commercial_funnel()
FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.get_founder_commercial_funnel()
TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.get_founder_commercial_funnel()
IS 'Read-only aggregate commercial funnel for Founder Console. No PII, writes, payment authority, or revenue mutation.';

COMMIT;
