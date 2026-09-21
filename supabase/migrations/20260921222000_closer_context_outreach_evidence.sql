-- Add evidence from the original outreach into the read-only closer context.
-- This changes no authority, terms, payment, fulfilment or revenue state.

CREATE OR REPLACE FUNCTION public.get_closer_reply_context(
  p_case_id uuid,
  p_reply_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
  root_i public.outbound_intents%ROWTYPE;
BEGIN
  SELECT * INTO c
    FROM public.closer_cases
   WHERE id=p_case_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'closer case not found';
  END IF;

  SELECT * INTO r
    FROM public.outbound_replies
   WHERE id=p_reply_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'reply not found';
  END IF;

  SELECT * INTO i
    FROM public.outbound_intents
   WHERE id=r.intent_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'reply intent not found';
  END IF;

  IF r.id IS DISTINCT FROM c.reply_id
     AND COALESCE(i.metadata->>'closer_case_id','')
         IS DISTINCT FROM c.id::text THEN
    RAISE EXCEPTION 'reply does not belong to closer case';
  END IF;

  SELECT * INTO root_i
    FROM public.outbound_intents
   WHERE id=c.outbound_intent_id;

  RETURN jsonb_build_object(
    'case_id',c.id,
    'case_state',c.state,
    'reply_id',r.id,
    'classification',r.classification,
    'confidence',r.confidence,
    'received_at',r.received_at,
    'reply_subject',r.subject,
    'reply_body_text',r.body_text,
    'from_contact',r.from_contact,
    'root_intent_id',c.outbound_intent_id,
    'source_intent_id',i.id,
    'root_subject',COALESCE(root_i.subject,i.subject),
    'offer_key',COALESCE(root_i.offer_key,i.offer_key),
    'specific_proof',COALESCE(
      root_i.metadata->>'specific_proof',
      i.metadata->>'specific_proof'
    ),
    'why_now_summary',COALESCE(
      root_i.metadata->>'why_now_summary',
      i.metadata->>'why_now_summary'
    ),
    'why_now_evidence_ref',COALESCE(
      root_i.metadata->>'why_now_evidence_ref',
      i.metadata->>'why_now_evidence_ref'
    ),
    'prospect_id',c.prospect_id,
    'entity_id',c.entity_id,
    'buyer_id',c.buyer_id,
    'opportunity_id',c.opportunity_id,
    'fulfilment_order_id',c.fulfilment_order_id,
    'business_name',COALESCE(
      root_i.metadata->'candidate_evidence'->>'business_name',
      i.metadata->'candidate_evidence'->>'business_name'
    ),
    'niche',COALESCE(
      root_i.metadata->'candidate_evidence'->>'niche',
      i.metadata->'candidate_evidence'->>'niche'
    ),
    'metro',COALESCE(
      root_i.metadata->'candidate_evidence'->>'metro',
      i.metadata->'candidate_evidence'->>'metro'
    ),
    'contact_name',(
      SELECT br.contact_name
        FROM public.buyer_candidate_reviews br
       WHERE br.id=CASE
         WHEN COALESCE(
           root_i.metadata->>'buyer_candidate_review_id',
           i.metadata->>'buyer_candidate_review_id',
           ''
         ) ~
         '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
         THEN COALESCE(
           root_i.metadata->>'buyer_candidate_review_id',
           i.metadata->>'buyer_candidate_review_id'
         )::uuid
         ELSE NULL
       END
       LIMIT 1
    ),
    'actual_revenue',false
  );
END;
$$;
