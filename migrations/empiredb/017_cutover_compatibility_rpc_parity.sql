-- EmpireDB compatibility RPC parity for remaining active runtime paths.
-- Generated from current canonical Supabase pg_get_functiondef() output on
-- 2026-09-27, then converted to SECURITY INVOKER.
-- ingest_prospect_atomic already exists natively in migration 003.
-- auto_approve_voice_intent is role-bound and is NOT granted to empiredb_app.

SET ROLE empiredb_migrator;

CREATE OR REPLACE FUNCTION public.auto_approve_voice_intent(p_intent_id uuid, p_daily_cap integer DEFAULT 5)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
  i public.outbound_intents%ROWTYPE;
  p public.prospects%ROWTYPE;
  approved_today integer;
  result jsonb;
BEGIN
  IF p_daily_cap IS NULL OR p_daily_cap<1 OR p_daily_cap>20 THEN
    RAISE EXCEPTION 'voice daily cap must be 1-20';
  END IF;

  SELECT * INTO i FROM public.outbound_intents
  WHERE id=p_intent_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'voice intent not found'; END IF;
  IF i.status='approved' THEN
    RETURN jsonb_build_object(
      'decision','existing','intent_id',i.id,'status',i.status,
      'actual_revenue',false
    );
  END IF;
  IF i.status<>'pending_approval' OR i.expires_at<=clock_timestamp() THEN
    RAISE EXCEPTION 'fresh pending voice intent required';
  END IF;
  IF i.channel<>'voice' OR i.offer_key<>'managed_service' THEN
    RAISE EXCEPTION 'managed-service voice intent required';
  END IF;
  IF COALESCE((i.metadata->>'call_ready')::boolean,false) IS NOT TRUE THEN
    RAISE EXCEPTION 'call-ready evidence required';
  END IF;
  IF COALESCE(i.metadata->>'voice_legal_basis','') NOT IN (
    'prior_express_written_consent',
    'verified_business_landline_b2b'
  ) THEN
    RAISE EXCEPTION 'verified voice legal basis required';
  END IF;
  IF COALESCE(i.metadata->>'voice_legal_basis','')
      ='verified_business_landline_b2b'
     AND COALESCE(i.metadata->>'line_type','')
         NOT IN ('landline','landline_tollfree') THEN
    RAISE EXCEPTION 'verified business landline evidence required';
  END IF;
  IF i.prospect_id IS NULL THEN
    RAISE EXCEPTION 'canonical prospect required';
  END IF;

  SELECT * INTO p FROM public.prospects WHERE id=i.prospect_id;
  IF NOT FOUND OR COALESCE(p.buy_signal_score,0)<70 THEN
    RAISE EXCEPTION 'eligible canonical prospect required';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.outbound_suppressions s
    WHERE s.contact_type='phone'
      AND regexp_replace(s.normalized_contact,'[^0-9]','','g')
          =regexp_replace(i.normalized_recipient,'[^0-9]','','g')
  ) THEN
    RAISE EXCEPTION 'phone suppressed';
  END IF;

  SELECT count(*)::integer INTO approved_today
  FROM public.outbound_events e
  JOIN public.outbound_intents x ON x.id=e.intent_id
  WHERE e.event_type='approved'
    AND e.actor='voice-standing-authority'
    AND x.channel='voice'
    AND e.occurred_at>=date_trunc('day',clock_timestamp());

  IF approved_today>=p_daily_cap THEN
    RAISE EXCEPTION 'voice standing-authority daily cap reached';
  END IF;

  result := public.approve_outbound_intent(
    i.id,
    'voice-standing-authority',
    'Approved under bounded call-ready business-phone authority.'
  );
  RETURN result || jsonb_build_object(
    'standing_authority',true,
    'voice_daily_cap',p_daily_cap,
    'actual_revenue',false
  );
END;
$function$;


CREATE OR REPLACE FUNCTION public.auto_review_buyer_candidate(p_review_id uuid, p_daily_cap integer DEFAULT 10)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    r public.buyer_candidate_reviews%ROWTYPE;
    contact jsonb;
    approved_today integer;
BEGIN
    IF p_daily_cap IS NULL OR p_daily_cap < 1 OR p_daily_cap > 50 THEN
      RAISE EXCEPTION 'standing authority daily cap must be 1-50';
    END IF;

    SELECT * INTO r
    FROM public.buyer_candidate_reviews
    WHERE id=p_review_id
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'buyer candidate review not found';
    END IF;

    IF COALESCE(lower(r.evidence->>'contact_personhood_valid'),'false') <> 'true'
       OR COALESCE(lower(r.evidence->>'has_named_contact'),'false') <> 'true' THEN
      RAISE EXCEPTION 'verified contact personhood required';
    END IF;

    IF r.status='approved' THEN
      RETURN jsonb_build_object(
        'decision','existing',
        'review_id',r.id,
        'status',r.status,
        'actual_revenue',false
      );
    END IF;

    IF r.status<>'pending' THEN
      RAISE EXCEPTION 'pending buyer candidate review required';
    END IF;
    IF r.proposed_at < clock_timestamp()-interval '7 days' THEN
      RAISE EXCEPTION 'buyer candidate review expired';
    END IF;
    IF r.offer_key <> 'managed_service' THEN
      RAISE EXCEPTION 'offer outside standing authority';
    END IF;
    IF COALESCE(lower(r.evidence->>'review_ready'),'false') <> 'true'
       OR COALESCE(lower(r.evidence->>'outreach_ready'),'false') <> 'true' THEN
      RAISE EXCEPTION 'review and outreach readiness required';
    END IF;
    IF COALESCE(r.company_score,0) < 70
       OR COALESCE(r.decision_score,0) < 0.70 THEN
      RAISE EXCEPTION 'candidate score below standing authority threshold';
    END IF;
    IF COALESCE(r.evidence->>'contact_source','') NOT IN (
      'official_site','official_site_current','public_record','press_release'
    ) THEN
      RAISE EXCEPTION 'contact source outside standing authority';
    END IF;

    SELECT item INTO contact
    FROM jsonb_array_elements(
      CASE
        WHEN jsonb_typeof(r.evidence->'verified_contacts')='array'
        THEN r.evidence->'verified_contacts'
        ELSE '[]'::jsonb
      END
    ) items(item)
    WHERE lower(trim(COALESCE(item->>'email',''))) =
          lower(trim(COALESCE(r.contact_email,'')))
    LIMIT 1;

    IF contact IS NULL THEN
      RAISE EXCEPTION 'verified contact evidence required';
    END IF;
    IF contact->'bound_to_decision_maker' IS DISTINCT FROM 'true'::jsonb
       OR contact->'has_mx' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_valid' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_disposable' IS DISTINCT FROM 'false'::jsonb
       OR contact->'is_role_address' IS DISTINCT FROM 'false'::jsonb THEN
      RAISE EXCEPTION 'verified decision-maker contact evidence required';
    END IF;
    IF jsonb_typeof(contact->'confidence') <> 'number'
       OR (contact->>'confidence')::numeric < 0.70 THEN
      RAISE EXCEPTION 'contact confidence below standing authority threshold';
    END IF;
    IF COALESCE(contact->>'source','') NOT IN (
      'official_site','official_site_current','public_record','press_release'
    ) THEN
      RAISE EXCEPTION 'verified contact source outside standing authority';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM public.outbound_suppressions s
      WHERE s.normalized_contact=lower(trim(r.contact_email))
    ) THEN
      RAISE EXCEPTION 'recipient is suppressed';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM public.outbound_intents i
      WHERE i.normalized_recipient=lower(trim(r.contact_email))
        AND i.status IN (
          'sending','sent','delivered','replied','bounced','failed','suppressed'
        )
    ) THEN
      RAISE EXCEPTION 'existing outbound history requires explicit review';
    END IF;

    SELECT count(*)::integer INTO approved_today
    FROM public.buyer_candidate_review_events e
    WHERE e.event_type='approved'
      AND e.actor='gtm-standing-authority'
      AND e.occurred_at >= date_trunc('day', clock_timestamp());

    IF approved_today >= p_daily_cap THEN
      RAISE EXCEPTION 'standing authority daily candidate cap reached';
    END IF;

    UPDATE public.buyer_candidate_reviews
    SET status='approved',
        reviewed_at=clock_timestamp(),
        reviewed_by='gtm-standing-authority',
        review_note='Approved automatically under bounded GTM standing authority.'
    WHERE id=r.id
    RETURNING * INTO r;

    INSERT INTO public.buyer_candidate_review_events(
      review_id,event_type,actor,payload
    )
    VALUES(
      r.id,
      'approved',
      'gtm-standing-authority',
      jsonb_build_object(
        'standing_authority',true,
        'daily_cap',p_daily_cap,
        'actual_revenue',false
      )
    );

    RETURN jsonb_build_object(
      'decision','approved',
      'review_id',r.id,
      'status',r.status,
      'standing_authority',true,
      'actual_revenue',false
    );
END;
$function$;


CREATE OR REPLACE FUNCTION public.auto_verify_buyer_stated_commercial_evidence(p_evidence_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
  v_reply_id uuid;
  v_phrase text;
  v_match text[];
  v_amount_cents bigint;
  v_unit text;
BEGIN
  SELECT * INTO x
  FROM public.commercial_evidence_registry
  WHERE id=p_evidence_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'commercial evidence not found';
  END IF;
  IF x.status='verified' THEN
    RETURN jsonb_build_object(
      'decision','existing_verification',
      'evidence_id',x.id,
      'status',x.status,
      'actual_revenue',false
    );
  END IF;
  IF x.status<>'pending'
     OR x.evidence_kind<>'price'
     OR x.source_type<>'buyer_stated' THEN
    RAISE EXCEPTION 'pending buyer-stated price evidence required';
  END IF;
  IF x.valid_until IS NOT NULL
     AND x.valid_until<=clock_timestamp() THEN
    RAISE EXCEPTION 'commercial evidence expired';
  END IF;
  IF x.buyer_id IS NULL OR x.closer_case_id IS NULL THEN
    RAISE EXCEPTION 'buyer and closer case binding required';
  END IF;

  BEGIN
    v_reply_id := (x.evidence->>'reply_id')::uuid;
  EXCEPTION WHEN others THEN
    RAISE EXCEPTION 'valid reply_id evidence required';
  END;
  IF x.source_reference <> 'reply:' || v_reply_id::text || ':price' THEN
    RAISE EXCEPTION 'reply source reference mismatch';
  END IF;

  SELECT * INTO c
  FROM public.closer_cases
  WHERE id=x.closer_case_id;
  IF NOT FOUND OR c.buyer_id IS DISTINCT FROM x.buyer_id THEN
    RAISE EXCEPTION 'closer case buyer binding mismatch';
  END IF;

  SELECT * INTO r
  FROM public.outbound_replies
  WHERE id=v_reply_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'reply evidence not found';
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
  IF abs(extract(epoch FROM (x.observed_at-r.received_at))) > 1 THEN
    RAISE EXCEPTION 'reply observation timestamp mismatch';
  END IF;

  v_phrase := trim(COALESCE(x.evidence->>'price_match',''));
  IF v_phrase='' OR position(lower(v_phrase) in lower(COALESCE(r.body_text,'')))=0 THEN
    RAISE EXCEPTION 'literal price phrase not present in reply';
  END IF;

  v_match := regexp_match(
    lower(v_phrase),
    '.*\$[[:space:]]*([0-9]{1,6}([.][0-9]{1,2})?)[[:space:]]*(/|per[[:space:]]+|a[[:space:]]+)(lead|call)s?[[:space:]]*$',
    'i'
  );
  IF v_match IS NULL THEN
    RAISE EXCEPTION 'buyer-stated price phrase is not deterministic';
  END IF;

  v_amount_cents := round((v_match[1])::numeric * 100)::bigint;
  v_unit := CASE v_match[4]
    WHEN 'lead' THEN 'per_lead'
    WHEN 'call' THEN 'per_call'
    ELSE NULL
  END;
  IF v_amount_cents IS DISTINCT FROM x.amount_cents
     OR v_unit IS DISTINCT FROM x.unit
     OR upper(x.currency)<>'USD' THEN
    RAISE EXCEPTION 'buyer-stated price amount or unit mismatch';
  END IF;

  RETURN public.verify_commercial_evidence(
    x.id,
    'commercial-evidence-standing-authority'
  );
END;
$function$;


CREATE OR REPLACE FUNCTION public.auto_verify_commercial_product_version(p_version_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
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
$function$;


CREATE OR REPLACE FUNCTION public.list_auto_verifiable_commercial_evidence(p_limit integer DEFAULT 25)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY INVOKER
 SET search_path TO ''
AS $function$
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'evidence_id',e.id,
        'buyer_id',e.buyer_id,
        'closer_case_id',e.closer_case_id,
        'source_reference',e.source_reference,
        'observed_at',e.observed_at
      )
      ORDER BY e.created_at,e.id
    ),
    '[]'::jsonb
  )
  FROM (
    SELECT *
    FROM public.commercial_evidence_registry
    WHERE status='pending'
      AND evidence_kind='price'
      AND source_type='buyer_stated'
    ORDER BY created_at,id
    LIMIT LEAST(GREATEST(COALESCE(p_limit,25),1),100)
  ) e;
$function$;


CREATE OR REPLACE FUNCTION public.list_buyer_reviews_for_outbound(p_limit integer DEFAULT 25)
 RETURNS jsonb
 LANGUAGE sql
 SECURITY INVOKER
 SET search_path TO ''
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
      AND COALESCE(lower(r.evidence->>'contact_personhood_valid'),'false')='true'
      AND COALESCE(lower(r.evidence->>'has_named_contact'),'false')='true'
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


CREATE OR REPLACE FUNCTION public.list_due_outbound_followups(p_limit integer DEFAULT 25)
 RETURNS jsonb
 LANGUAGE sql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
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
               AND e.delivered_at <= now()-interval '24 hours'
            THEN 1
          WHEN e.followup_count=1
               AND e.first_followup_delivered_at IS NOT NULL
               AND e.delivered_at <= now()-interval '72 hours'
               AND e.first_followup_delivered_at <= now()-interval '24 hours'
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
$function$;


CREATE OR REPLACE FUNCTION public.propose_buyer_candidate_review(p_prospect_id uuid, p_entity_id uuid, p_contact_name text, p_contact_title text, p_contact_email text, p_offer_key text, p_company_score numeric, p_decision_score numeric, p_evidence jsonb, p_idempotency_key text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$ DECLARE r public.buyer_candidate_reviews%ROWTYPE; v_email text:=lower(trim(COALESCE(p_contact_email,''))); BEGIN IF NOT EXISTS (SELECT 1 FROM public.prospects WHERE id=p_prospect_id) THEN RAISE EXCEPTION 'canonical prospect required'; END IF; IF p_entity_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.business_entities WHERE id=p_entity_id) THEN RAISE EXCEPTION 'canonical entity required'; END IF; IF length(trim(COALESCE(p_contact_name,'')))<3 OR length(trim(COALESCE(p_contact_title,'')))<2 THEN RAISE EXCEPTION 'verified decision maker required'; END IF; IF v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' THEN RAISE EXCEPTION 'verified contact email required'; END IF; IF p_company_score IS NULL OR p_company_score<0 OR p_company_score>100 OR p_decision_score IS NULL OR p_decision_score<0.5 OR p_decision_score>1 THEN RAISE EXCEPTION 'candidate score threshold not met'; END IF; IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN RAISE EXCEPTION 'candidate evidence required'; END IF; SELECT * INTO r FROM public.buyer_candidate_reviews WHERE idempotency_key=trim(p_idempotency_key); IF FOUND THEN RETURN jsonb_build_object('decision','existing','review_id',r.id,'status',r.status,'actual_revenue',false); END IF; INSERT INTO public.buyer_candidate_reviews(prospect_id,entity_id,contact_name,contact_title,contact_email,offer_key,company_score,decision_score,evidence,idempotency_key) VALUES(p_prospect_id,p_entity_id,trim(p_contact_name),trim(p_contact_title),v_email,trim(p_offer_key),p_company_score,p_decision_score,p_evidence,trim(p_idempotency_key)) RETURNING * INTO r; INSERT INTO public.buyer_candidate_review_events(review_id,event_type,actor,payload) VALUES(r.id,'proposed','buyer-discovery',jsonb_build_object('prospect_id',r.prospect_id,'offer_key',r.offer_key)); RETURN jsonb_build_object('decision','proposed','review_id',r.id,'status',r.status,'actual_revenue',false); END; $function$;


CREATE OR REPLACE FUNCTION public.propose_buyer_scout_candidate(p_domain text, p_business_name text, p_website text, p_description text, p_buyer_type text, p_direct_buyer_score integer, p_explicit_direct_buyer_evidence boolean, p_target_buyer_pools jsonb, p_target_product_codes jsonb, p_target_corridor_keys jsonb, p_query_evidence jsonb, p_site_evidence jsonb, p_provenance jsonb, p_actor text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
  candidate public.buyer_scout_candidates%ROWTYPE;
  normalized_domain text := lower(trim(COALESCE(p_domain,'')));
BEGIN
  IF normalized_domain=''
     OR trim(COALESCE(p_website,''))=''
     OR trim(COALESCE(p_actor,''))='' THEN
    RAISE EXCEPTION 'domain, website and actor required';
  END IF;

  IF p_direct_buyer_score < 0 OR p_direct_buyer_score > 100 THEN
    RAISE EXCEPTION 'direct buyer score out of bounds';
  END IF;

  IF jsonb_typeof(COALESCE(p_target_buyer_pools,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_target_product_codes,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_target_corridor_keys,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_query_evidence,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_site_evidence,'{}'::jsonb))<>'object'
     OR jsonb_typeof(COALESCE(p_provenance,'{}'::jsonb))<>'object' THEN
    RAISE EXCEPTION 'invalid buyer scout evidence shape';
  END IF;

  INSERT INTO public.buyer_scout_candidates(
    domain,
    business_name,
    website,
    description,
    buyer_type,
    direct_buyer_score,
    explicit_direct_buyer_evidence,
    target_buyer_pools,
    target_product_codes,
    target_corridor_keys,
    query_evidence,
    site_evidence,
    provenance
  ) VALUES (
    normalized_domain,
    NULLIF(trim(COALESCE(p_business_name,'')),''),
    trim(p_website),
    NULLIF(trim(COALESCE(p_description,'')),''),
    COALESCE(NULLIF(trim(COALESCE(p_buyer_type,'')),''),'unknown'),
    p_direct_buyer_score,
    COALESCE(p_explicit_direct_buyer_evidence,false),
    COALESCE(p_target_buyer_pools,'[]'::jsonb),
    COALESCE(p_target_product_codes,'[]'::jsonb),
    COALESCE(p_target_corridor_keys,'[]'::jsonb),
    COALESCE(p_query_evidence,'[]'::jsonb),
    COALESCE(p_site_evidence,'{}'::jsonb),
    COALESCE(p_provenance,'{}'::jsonb)
  )
  ON CONFLICT (domain) DO UPDATE
  SET business_name=COALESCE(
        excluded.business_name,
        public.buyer_scout_candidates.business_name
      ),
      website=excluded.website,
      description=COALESCE(
        excluded.description,
        public.buyer_scout_candidates.description
      ),
      buyer_type=excluded.buyer_type,
      direct_buyer_score=GREATEST(
        public.buyer_scout_candidates.direct_buyer_score,
        excluded.direct_buyer_score
      ),
      explicit_direct_buyer_evidence=(
        public.buyer_scout_candidates.explicit_direct_buyer_evidence
        OR excluded.explicit_direct_buyer_evidence
      ),
      target_buyer_pools=excluded.target_buyer_pools,
      target_product_codes=excluded.target_product_codes,
      target_corridor_keys=excluded.target_corridor_keys,
      query_evidence=excluded.query_evidence,
      site_evidence=excluded.site_evidence,
      provenance=(
        public.buyer_scout_candidates.provenance
        || excluded.provenance
      ),
      last_seen_at=clock_timestamp(),
      updated_at=clock_timestamp()
  RETURNING * INTO candidate;

  RETURN jsonb_build_object(
    'decision','candidate_recorded',
    'candidate_id',candidate.id,
    'domain',candidate.domain,
    'review_state',candidate.review_state,
    'reconciliation_state',candidate.reconciliation_state,
    'canonical_buyer_id',candidate.canonical_buyer_id,
    'canonical_prospect_id',candidate.canonical_prospect_id,
    'outreach_authorized',false,
    'commercial_terms_verified',false,
    'actual_revenue',false
  );
END;
$function$;


CREATE OR REPLACE FUNCTION public.propose_call_ready_voice_intent(p_prospect_id uuid, p_recipient text, p_idempotency_key text, p_metadata jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
  p public.prospects%ROWTYPE;
  v_recipient text := trim(COALESCE(p_recipient,''));
  v_digits text;
  p_digits text;
  result jsonb;
BEGIN
  SELECT * INTO p FROM public.prospects WHERE id=p_prospect_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'canonical prospect required'; END IF;

  v_digits := regexp_replace(v_recipient,'[^0-9]','','g');
  p_digits := regexp_replace(COALESCE(p.phone,''),'[^0-9]','','g');
  IF length(v_digits)<10 OR right(v_digits,10)<>right(p_digits,10) THEN
    RAISE EXCEPTION 'canonical business phone mismatch';
  END IF;
  IF COALESCE(p.buy_signal_score,0)<70 THEN
    RAISE EXCEPTION 'buy signal below voice standing-authority floor';
  END IF;
  IF trim(COALESCE(p.website,''))='' THEN
    RAISE EXCEPTION 'first-party business website required';
  END IF;
  IF lower(COALESCE(p.niche,'')) !~ '(roof|hvac|plumb|solar|contractor|restoration)' THEN
    RAISE EXCEPTION 'prospect niche outside managed-service voice scope';
  END IF;
  IF COALESCE((p_metadata->>'call_ready')::boolean,false) IS NOT TRUE THEN
    RAISE EXCEPTION 'call-ready evidence required';
  END IF;
  IF COALESCE(p_metadata->>'voice_legal_basis','') NOT IN (
    'prior_express_written_consent',
    'verified_business_landline_b2b'
  ) THEN
    RAISE EXCEPTION 'verified voice legal basis required';
  END IF;
  IF COALESCE(p_metadata->>'voice_legal_basis','')
      ='verified_business_landline_b2b'
     AND COALESCE(p_metadata->>'line_type','')
         NOT IN ('landline','landline_tollfree') THEN
    RAISE EXCEPTION 'verified business landline evidence required';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.outbound_suppressions s
    WHERE s.contact_type='phone'
      AND regexp_replace(s.normalized_contact,'[^0-9]','','g')=v_digits
  ) THEN
    RAISE EXCEPTION 'phone suppressed';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.outbound_intents i
    WHERE i.channel='voice'
      AND regexp_replace(i.normalized_recipient,'[^0-9]','','g')=v_digits
      AND i.status IN ('sent','delivered','replied','sending')
      AND i.created_at >= clock_timestamp()-interval '7 days'
  ) THEN
    RAISE EXCEPTION 'recent voice attempt already exists';
  END IF;

  result := public.propose_outbound_intent(
    NULL,p.id,NULL,NULL,'voice',v_recipient,NULL,
    'Governed Empire AI business call: identify or reach the decision maker, '
      || 'test relevance, and request permission for follow-up.',
    NULL,'managed_service',trim(p_idempotency_key),
    'voice-standing-authority',
    clock_timestamp()+interval '2 hours',
    COALESCE(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'call_ready',true,
      'buy_signal_score',p.buy_signal_score,
      'business_name',p.business_name,
      'niche',p.niche,
      'metro',p.metro,
      'website',p.website,
      'actual_revenue',false,
      'terms_authority',false,
      'payment_authority',false
    )
  );
  RETURN result;
END;
$function$;


CREATE OR REPLACE FUNCTION public.decide_commercial_product_version(p_version_id uuid, p_decision text, p_actor text, p_reason text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
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
$function$;


CREATE OR REPLACE FUNCTION public.get_commercial_product_version_review(p_version_id uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY INVOKER
 SET search_path TO ''
AS $function$
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
$function$;


CREATE OR REPLACE FUNCTION public.propose_commercial_product_version(p_product_code text, p_billing_model text, p_currency text, p_price_basis jsonb, p_acquisition_cost_basis jsonb, p_fulfilment_cost_basis jsonb, p_margin_policy jsonb, p_provenance jsonb, p_evidence_refs jsonb, p_effective_from timestamp with time zone, p_effective_until timestamp with time zone, p_actor text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
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
$function$;


CREATE OR REPLACE FUNCTION public.propose_outbound_followup(p_root_intent_id uuid, p_step integer, p_subject text, p_body_text text, p_idempotency_key text, p_proposed_by text, p_expires_at timestamp with time zone)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    root public.outbound_intents%ROWTYPE;
    review public.buyer_candidate_reviews%ROWTYPE;
    delivered_at timestamptz;
    existing_count integer;
    first_followup_delivered timestamptz;
    review_id uuid;
    result jsonb;
    merged jsonb;
BEGIN
    IF p_step NOT IN (1,2) THEN
        RAISE EXCEPTION 'follow-up step must be 1 or 2';
    END IF;

    SELECT * INTO root
    FROM public.outbound_intents
    WHERE id=p_root_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'root outbound intent not found';
    END IF;

    IF root.channel<>'email'
       OR root.status<>'delivered'
       OR COALESCE(root.metadata->>'sequence_kind','first_touch')='followup' THEN
        RAISE EXCEPTION 'delivered first-touch email required';
    END IF;

    BEGIN
        review_id := (root.metadata->>'buyer_candidate_review_id')::uuid;
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'buyer candidate review reference required';
    END;

    SELECT * INTO review
    FROM public.buyer_candidate_reviews
    WHERE id=review_id;

    IF NOT FOUND
       OR review.status<>'approved'
       OR COALESCE(lower(review.evidence->>'outreach_ready'),'false')<>'true' THEN
        RAISE EXCEPTION 'approved outreach-ready buyer review required';
    END IF;

    SELECT max(e.occurred_at) INTO delivered_at
    FROM public.outbound_events e
    WHERE e.intent_id=root.id
      AND e.event_type='delivered';

    IF delivered_at IS NULL THEN
        RAISE EXCEPTION 'root delivery evidence required';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
        WHERE s.normalized_contact=root.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_replies rep
        JOIN public.outbound_intents ri ON ri.id=rep.intent_id
        WHERE ri.normalized_recipient=root.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'reply already observed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_events e
        JOIN public.outbound_intents ei ON ei.id=e.intent_id
        WHERE ei.normalized_recipient=root.normalized_recipient
          AND e.event_type IN ('bounced','complained','failed','suppressed')
    ) THEN
        RAISE EXCEPTION 'negative delivery evidence stops follow-up';
    END IF;

    SELECT count(*)::integer INTO existing_count
    FROM public.outbound_intents f
    WHERE f.metadata->>'sequence_kind'='followup'
      AND f.metadata->>'root_intent_id'=root.id::text
      AND f.status NOT IN ('cancelled','rejected');

    IF existing_count <> p_step-1 THEN
        RAISE EXCEPTION 'follow-up sequence state mismatch';
    END IF;

    IF p_step=1 AND delivered_at > clock_timestamp()-interval '24 hours' THEN
        RAISE EXCEPTION 'first follow-up cooldown active';
    END IF;

    IF p_step=2 THEN
        SELECT max(e.occurred_at) INTO first_followup_delivered
        FROM public.outbound_intents f
        JOIN public.outbound_events e ON e.intent_id=f.id
        WHERE f.metadata->>'sequence_kind'='followup'
          AND f.metadata->>'root_intent_id'=root.id::text
          AND f.metadata->>'followup_step'='1'
          AND e.event_type='delivered';

        IF first_followup_delivered IS NULL THEN
            RAISE EXCEPTION 'first follow-up delivery required';
        END IF;
        IF delivered_at > clock_timestamp()-interval '72 hours' THEN
            RAISE EXCEPTION 'final follow-up root cooldown active';
        END IF;
        IF first_followup_delivered > clock_timestamp()-interval '24 hours' THEN
            RAISE EXCEPTION 'final follow-up step cooldown active';
        END IF;
    END IF;

    IF trim(COALESCE(p_subject,''))=''
       OR trim(COALESCE(p_body_text,''))='' THEN
        RAISE EXCEPTION 'follow-up subject and body required';
    END IF;

    IF lower(p_body_text) NOT LIKE '%opt out%'
       AND lower(p_body_text) NOT LIKE '%unsubscribe%'
       AND lower(p_body_text) NOT LIKE '%opt-out%' THEN
        RAISE EXCEPTION 'visible opt-out required';
    END IF;

    IF lower(p_body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
        RAISE EXCEPTION 'approved postal footer required';
    END IF;

    merged := COALESCE(root.metadata,'{}'::jsonb)
      || jsonb_build_object(
        'sequence_kind','followup',
        'root_intent_id',root.id,
        'followup_step',p_step,
        'buyer_candidate_review_id',review.id,
        'candidate_evidence',review.evidence,
        'company_score',review.company_score,
        'decision_score',review.decision_score
      );

    result := public.propose_outbound_intent(
        root.entity_id,
        root.prospect_id,
        root.buyer_id,
        root.opportunity_id,
        'email',
        root.recipient,
        p_subject,
        p_body_text,
        NULL,
        root.offer_key,
        p_idempotency_key,
        p_proposed_by,
        p_expires_at,
        merged
    );

    RETURN result || jsonb_build_object(
        'root_intent_id',root.id,
        'followup_step',p_step,
        'sequence_kind','followup'
    );
END;
$function$;


CREATE OR REPLACE FUNCTION public.propose_reviewed_outbound_intent(p_review_id uuid, p_subject text, p_body_text text, p_body_html text, p_idempotency_key text, p_proposed_by text, p_expires_at timestamp with time zone, p_metadata jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
    r public.buyer_candidate_reviews%ROWTYPE;
    result jsonb;
    merged jsonb;
BEGIN
    SELECT * INTO r
    FROM public.buyer_candidate_reviews
    WHERE id=p_review_id
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'buyer candidate review not found';
    END IF;
    IF r.status<>'approved' THEN
      RAISE EXCEPTION 'approved buyer candidate review required';
    END IF;
    IF r.reviewed_at IS NULL
       OR r.reviewed_at < clock_timestamp()-interval '7 days' THEN
      RAISE EXCEPTION 'fresh buyer candidate approval required';
    END IF;
    IF COALESCE(lower(r.evidence->>'outreach_ready'),'false') <> 'true' THEN
      RAISE EXCEPTION 'outreach-ready evidence required';
    END IF;
    IF COALESCE(lower(r.evidence->>'contact_personhood_valid'),'false') <> 'true'
       OR COALESCE(lower(r.evidence->>'has_named_contact'),'false') <> 'true' THEN
      RAISE EXCEPTION 'verified contact personhood required';
    END IF;

    merged := COALESCE(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'buyer_candidate_review_id',r.id,
      'decision_score',r.decision_score,
      'company_score',r.company_score,
      'candidate_evidence',r.evidence
    );

    result := public.propose_outbound_intent(
      r.entity_id,
      r.prospect_id,
      NULL,
      NULL,
      'email',
      r.contact_email,
      p_subject,
      p_body_text,
      p_body_html,
      r.offer_key,
      p_idempotency_key,
      p_proposed_by,
      p_expires_at,
      merged
    );

    INSERT INTO public.buyer_candidate_review_events(
      review_id,event_type,actor,payload
    )
    VALUES(
      r.id,
      'outbound_proposed',
      trim(p_proposed_by),
      jsonb_build_object('intent_id',result->>'intent_id')
    );

    RETURN result || jsonb_build_object(
      'buyer_candidate_review_id',r.id
    );
END;
$function$;


CREATE OR REPLACE FUNCTION public.record_voice_provider_event(p_intent_id uuid, p_external_call_id text, p_event_type text, p_payload jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
  i public.outbound_intents%ROWTYPE;
  c public.empire_conversations%ROWTYPE;
  v_type text := lower(trim(COALESCE(p_event_type,'')));
  v_call text := trim(COALESCE(p_external_call_id,''));
BEGIN
  IF v_type NOT IN (
    'call_ringing','call_answered','call_completed','call_busy',
    'call_unanswered','call_rejected','call_failed'
  ) THEN RAISE EXCEPTION 'unsupported voice provider event'; END IF;
  IF v_call='' THEN RAISE EXCEPTION 'external call id required'; END IF;

  SELECT * INTO i FROM public.outbound_intents
  WHERE id=p_intent_id FOR UPDATE;
  IF NOT FOUND OR i.channel<>'voice' THEN
    RAISE EXCEPTION 'canonical voice intent required';
  END IF;

  SELECT * INTO c FROM public.empire_conversations
  WHERE outbound_intent_id=i.id
  ORDER BY opened_at DESC LIMIT 1;

  IF NOT FOUND THEN
    INSERT INTO public.empire_conversations(
      channel,state,prospect_id,entity_id,buyer_id,opportunity_id,
      outbound_intent_id,external_conversation_id,provider
    ) VALUES(
      'voice','open',i.prospect_id,i.entity_id,i.buyer_id,i.opportunity_id,
      i.id,v_call,'vonage'
    ) RETURNING * INTO c;
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.outbound_events e
    WHERE e.intent_id=i.id
      AND e.event_type=v_type
      AND e.provider_message_id=v_call
  ) THEN
    RETURN jsonb_build_object(
      'decision','existing','intent_id',i.id,
      'conversation_id',c.id,'event_type',v_type,'actual_revenue',false
    );
  END IF;

  IF v_type='call_answered' AND i.status IN ('sent','failed') THEN
    UPDATE public.outbound_intents
    SET status='delivered',updated_at=clock_timestamp()
    WHERE id=i.id RETURNING * INTO i;
    UPDATE public.empire_conversations
    SET state='engaged',updated_at=clock_timestamp()
    WHERE id=c.id RETURNING * INTO c;
  ELSIF v_type IN (
    'call_busy','call_unanswered','call_rejected','call_failed'
  ) AND i.status IN ('sent','approved') THEN
    UPDATE public.outbound_intents
    SET status='failed',updated_at=clock_timestamp()
    WHERE id=i.id RETURNING * INTO i;
  ELSIF v_type='call_completed' THEN
    UPDATE public.empire_conversations
    SET state='closed',updated_at=clock_timestamp()
    WHERE id=c.id RETURNING * INTO c;
  END IF;

  INSERT INTO public.outbound_events(
    intent_id,event_type,actor,provider_message_id,payload
  ) VALUES(
    i.id,v_type,'vonage_webhook',v_call,COALESCE(p_payload,'{}'::jsonb)
  );

  INSERT INTO public.empire_conversation_events(
    conversation_id,event_type,direction,actor,provider_event_id,
    evidence,occurred_at
  ) VALUES(
    c.id,v_type,'internal','vonage_webhook',
    'vonage:'||v_call||':'||v_type,
    COALESCE(p_payload,'{}'::jsonb) || jsonb_build_object(
      'provider','vonage','external_conversation_id',v_call
    ),
    clock_timestamp()
  )
  ON CONFLICT(conversation_id,provider_event_id) DO NOTHING;

  RETURN jsonb_build_object(
    'decision','recorded','intent_id',i.id,'status',i.status,
    'conversation_id',c.id,'event_type',v_type,'actual_revenue',false
  );
END;
$function$;


CREATE OR REPLACE FUNCTION public.record_voice_turn(p_intent_id uuid, p_external_call_id text, p_turn_index integer, p_direction text, p_body_text text, p_evidence jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
DECLARE
  i public.outbound_intents%ROWTYPE;
  c public.empire_conversations%ROWTYPE;
  event_id text;
  event_type text;
BEGIN
  IF p_turn_index<0 OR p_turn_index>10000 THEN
    RAISE EXCEPTION 'invalid turn index';
  END IF;
  IF p_direction NOT IN ('inbound','outbound') THEN
    RAISE EXCEPTION 'voice turn direction required';
  END IF;
  IF trim(COALESCE(p_body_text,''))='' THEN
    RAISE EXCEPTION 'voice turn text required';
  END IF;

  SELECT * INTO i FROM public.outbound_intents WHERE id=p_intent_id;
  IF NOT FOUND OR i.channel<>'voice' THEN
    RAISE EXCEPTION 'canonical voice intent required';
  END IF;
  SELECT * INTO c FROM public.empire_conversations
  WHERE outbound_intent_id=i.id
  ORDER BY opened_at DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'voice conversation not initialized'; END IF;

  event_type := CASE
    WHEN p_direction='inbound' THEN 'transcript'
    ELSE 'agent_response'
  END;
  event_id := 'voice-turn:'||p_turn_index::text||':'||p_direction;

  INSERT INTO public.empire_conversation_events(
    conversation_id,event_type,direction,actor,body_text,
    provider_event_id,evidence,occurred_at
  ) VALUES(
    c.id,event_type,p_direction,
    CASE WHEN p_direction='inbound' THEN 'buyer' ELSE 'empire_voice_lab' END,
    p_body_text,event_id,
    COALESCE(p_evidence,'{}'::jsonb) || jsonb_build_object(
      'provider','vonage',
      'external_conversation_id',trim(p_external_call_id),
      'speech_vendor',NULL,
      'voice_engine','empire_voice_lab'
    ),
    clock_timestamp()
  )
  ON CONFLICT(conversation_id,provider_event_id) DO NOTHING;

  IF p_direction='inbound'
     AND lower(p_body_text) ~
       '(do not call|don''t call|stop calling|opt out|remove me|take me off)' THEN
    INSERT INTO public.outbound_suppressions(
      normalized_contact,contact_type,reason,source
    ) VALUES(
      i.normalized_recipient,'phone','voice_opt_out','empire_voice_lab'
    )
    ON CONFLICT(normalized_contact) DO NOTHING;

    UPDATE public.outbound_intents
    SET status='suppressed',updated_at=clock_timestamp()
    WHERE id=i.id;

    INSERT INTO public.outbound_events(
      intent_id,event_type,actor,provider_message_id,payload
    ) VALUES(
      i.id,'suppressed','empire_voice_lab',
      trim(p_external_call_id),
      jsonb_build_object(
        'reason','voice_opt_out',
        'turn_index',p_turn_index
      )
    );
  END IF;

  RETURN jsonb_build_object(
    'decision','recorded','conversation_id',c.id,
    'turn_index',p_turn_index,'direction',p_direction,
    'actual_revenue',false
  );
END;
$function$;


CREATE OR REPLACE FUNCTION public.refresh_pending_buyer_candidate_review(p_review_id uuid, p_contact_name text, p_contact_title text, p_contact_email text, p_decision_score numeric, p_evidence jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
declare
  r public.buyer_candidate_reviews%rowtype;
  v_email text := lower(trim(coalesce(p_contact_email,'')));
  v_name text := trim(coalesce(p_contact_name,''));
  v_title text := trim(coalesce(p_contact_title,''));
begin
  if p_review_id is null then
    raise exception 'review id required';
  end if;

  if length(v_name) < 3 or length(v_title) < 2 then
    raise exception 'verified decision maker required';
  end if;

  if v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then
    raise exception 'verified contact email required';
  end if;

  if p_decision_score is null
     or p_decision_score < 0.5
     or p_decision_score > 1 then
    raise exception 'decision score threshold not met';
  end if;

  if coalesce(p_evidence,'{}'::jsonb) = '{}'::jsonb then
    raise exception 'candidate evidence required';
  end if;

  select * into r
  from public.buyer_candidate_reviews
  where id = p_review_id
  for update;

  if not found then
    raise exception 'buyer candidate review not found';
  end if;

  if r.status <> 'pending' then
    return jsonb_build_object(
      'decision','not_pending',
      'review_id',r.id,
      'status',r.status,
      'actual_revenue',false
    );
  end if;

  if r.contact_name = v_name
     and r.contact_title = v_title
     and lower(r.contact_email) = v_email
     and r.decision_score = p_decision_score
     and r.evidence = p_evidence then
    return jsonb_build_object(
      'decision','no_change',
      'review_id',r.id,
      'status',r.status,
      'actual_revenue',false
    );
  end if;

  update public.buyer_candidate_reviews
  set contact_name = v_name,
      contact_title = v_title,
      contact_email = v_email,
      decision_score = p_decision_score,
      evidence = p_evidence
  where id = r.id
    and status = 'pending'
  returning * into r;

  if not found then
    raise exception 'pending review changed concurrently';
  end if;

  return jsonb_build_object(
    'decision','updated',
    'review_id',r.id,
    'status',r.status,
    'actual_revenue',false
  );
end;
$function$;


CREATE OR REPLACE FUNCTION public.register_commercial_product_identity(p_product_code text, p_product_name text, p_product_family text, p_billing_model text, p_configuration jsonb, p_provenance jsonb, p_actor text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY INVOKER
 SET search_path TO ''
AS $function$
declare
  product_row public.commercial_products%rowtype;
  resolved_currency text;
begin
  if trim(coalesce(p_product_code,''))=''
     or trim(coalesce(p_product_name,''))=''
     or trim(coalesce(p_product_family,''))=''
     or trim(coalesce(p_billing_model,''))=''
     or trim(coalesce(p_actor,''))='' then
    raise exception 'complete product identity and actor required';
  end if;

  if jsonb_typeof(coalesce(p_configuration,'{}'::jsonb))<>'object'
     or jsonb_typeof(coalesce(p_provenance,'{}'::jsonb))<>'object' then
    raise exception 'configuration and provenance must be objects';
  end if;

  resolved_currency := upper(
    coalesce(
      nullif(trim(coalesce(p_configuration->>'currency','')),''),
      'USD'
    )
  );

  if resolved_currency !~ '^[A-Z]{3}$' then
    raise exception 'invalid product currency';
  end if;

  insert into public.commercial_products(
    product_code,
    product_name,
    product_family,
    billing_model,
    active,
    configuration,
    currency,
    catalog_state,
    provenance
  ) values (
    trim(p_product_code),
    trim(p_product_name),
    trim(p_product_family),
    trim(p_billing_model),
    true,
    coalesce(p_configuration,'{}'::jsonb),
    resolved_currency,
    'UNKNOWN',
    coalesce(p_provenance,'{}'::jsonb)
  )
  on conflict (product_code) do update
  set product_name=excluded.product_name,
      product_family=excluded.product_family,
      configuration=excluded.configuration,
      currency=excluded.currency,
      provenance=public.commercial_products.provenance || excluded.provenance,
      updated_at=clock_timestamp()
  returning * into product_row;

  insert into public.commercial_product_catalog_events(
    product_id,event_type,actor,payload
  ) values (
    product_row.id,
    'identity_synchronized',
    p_actor,
    jsonb_build_object(
      'product_code',product_row.product_code,
      'catalog_state',product_row.catalog_state,
      'currency',product_row.currency,
      'economics_mutated',false,
      'actual_revenue',false
    )
  );

  return jsonb_build_object(
    'decision','identity_synchronized',
    'product_id',product_row.id,
    'product_code',product_row.product_code,
    'catalog_state',product_row.catalog_state,
    'currency',product_row.currency,
    'economics_mutated',false,
    'actual_revenue',false
  );
end;
$function$;


-- PostgreSQL grants EXECUTE to PUBLIC by default. Remove it from every imported
-- compatibility/helper function before adding explicit capability grants.
DO $empire_compat$
DECLARE v_name text; v_proc record;
BEGIN
  FOREACH v_name IN ARRAY ARRAY[
    'auto_approve_voice_intent',
    'auto_review_buyer_candidate',
    'auto_verify_buyer_stated_commercial_evidence',
    'auto_verify_commercial_product_version',
    'list_auto_verifiable_commercial_evidence',
    'list_buyer_reviews_for_outbound',
    'list_due_outbound_followups',
    'propose_buyer_candidate_review',
    'propose_buyer_scout_candidate',
    'propose_call_ready_voice_intent',
    'decide_commercial_product_version',
    'get_commercial_product_version_review',
    'propose_commercial_product_version',
    'propose_outbound_followup',
    'propose_reviewed_outbound_intent',
    'record_voice_provider_event',
    'record_voice_turn',
    'refresh_pending_buyer_candidate_review',
    'register_commercial_product_identity'
  ] LOOP
    FOR v_proc IN
      SELECT p.oid::regprocedure AS signature
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.proname=v_name
    LOOP
      EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',v_proc.signature);
    END LOOP;
  END LOOP;
END;
$empire_compat$;

-- Guarded compatibility surface: read/proposal/deterministic-verification and
-- provider-event recording only. Live voice approval remains dedicated.
DO $empire_compat$
DECLARE v_name text; v_proc record;
BEGIN
  FOREACH v_name IN ARRAY ARRAY[
    'auto_review_buyer_candidate',
    'auto_verify_buyer_stated_commercial_evidence',
    'auto_verify_commercial_product_version',
    'list_auto_verifiable_commercial_evidence',
    'list_buyer_reviews_for_outbound',
    'list_due_outbound_followups',
    'propose_buyer_candidate_review',
    'propose_buyer_scout_candidate',
    'propose_call_ready_voice_intent',
    'propose_commercial_product_version',
    'propose_outbound_followup',
    'propose_reviewed_outbound_intent',
    'record_voice_provider_event',
    'record_voice_turn',
    'refresh_pending_buyer_candidate_review',
    'register_commercial_product_identity'
  ] LOOP
    FOR v_proc IN
      SELECT p.oid::regprocedure AS signature
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.proname=v_name
    LOOP
      EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO empiredb_app',v_proc.signature);
    END LOOP;
  END LOOP;
END;
$empire_compat$;

-- Catalog helpers are internal dependencies of the guarded verifier.
DO $empire_compat$
DECLARE v_name text; v_proc record;
BEGIN
  FOREACH v_name IN ARRAY ARRAY[
    'get_commercial_product_version_review',
    'decide_commercial_product_version'
  ] LOOP
    FOR v_proc IN
      SELECT p.oid::regprocedure AS signature
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.proname=v_name
    LOOP
      EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO empiredb_app',v_proc.signature);
    END LOOP;
  END LOOP;
END;
$empire_compat$;

-- Voice approval is explicitly bound to outbound approval capability.
DO $empire_compat$
DECLARE v_proc record;
BEGIN
  FOR v_proc IN
    SELECT p.oid::regprocedure AS signature
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND p.proname='auto_approve_voice_intent'
  LOOP
    EXECUTE format(
      'GRANT EXECUTE ON FUNCTION %s TO empire_outbound_approver',
      v_proc.signature
    );
  END LOOP;
END;
$empire_compat$;

-- SECURITY INVOKER underlying table capability required by voice standing
-- authority. No send authority is added here.
GRANT SELECT ON public.prospects,public.outbound_suppressions,public.outbound_events
TO empire_outbound_approver;
GRANT SELECT,UPDATE ON public.outbound_intents TO empire_outbound_approver;

-- Re-materialize RLS policies only where an existing SQL grant permits access.
DO $empire_compat$
DECLARE v_table text; v_rel text; v_policy text;
BEGIN
  FOR v_table IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity
  LOOP
    v_rel := format('public.%I',v_table);
    IF has_table_privilege('empire_outbound_approver',v_rel,'SELECT') THEN
      v_policy := left(v_table||'_voice_approver_select',63);
      EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',v_policy,v_table);
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR SELECT TO empire_outbound_approver USING (true)',
        v_policy,v_table
      );
    END IF;
    IF has_table_privilege('empire_outbound_approver',v_rel,'UPDATE') THEN
      v_policy := left(v_table||'_voice_approver_update',63);
      EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',v_policy,v_table);
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR UPDATE TO empire_outbound_approver USING (true) WITH CHECK (true)',
        v_policy,v_table
      );
    END IF;
  END LOOP;
END;
$empire_compat$;

RESET ROLE;
