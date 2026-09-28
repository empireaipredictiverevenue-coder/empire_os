-- EmpireDB dedicated Outbound Governor authority parity.
-- Reuses latest proven governed functions from historical migration truth.
-- Independent of migration 018.
-- SECURITY INVOKER only.
-- Generic empiredb_app receives NO sender or approval authority.

SET ROLE empiredb_migrator;

CREATE OR REPLACE FUNCTION public.get_outbound_governor_context(
    p_intent_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
    r public.outbound_intents%ROWTYPE;
    evidence jsonb;
    contact jsonb;
    contacts jsonb;
    legacy_email text;
    legacy_source text;
    legacy_bound boolean := false;
    legacy_confidence numeric := NULL;
BEGIN
    SELECT * INTO r
      FROM public.outbound_intents
     WHERE id=p_intent_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    evidence := COALESCE(r.metadata->'candidate_evidence','{}'::jsonb);
    contacts := CASE
        WHEN jsonb_typeof(evidence->'verified_contacts')='array'
        THEN evidence->'verified_contacts'
        ELSE '[]'::jsonb
    END;

    SELECT item INTO contact
      FROM jsonb_array_elements(contacts) AS items(item)
     WHERE lower(trim(COALESCE(item->>'email','')))=r.normalized_recipient
     LIMIT 1;

    legacy_email := lower(trim(COALESCE(evidence->>'contact_email','')));
    legacy_source := lower(trim(COALESCE(
        evidence->>'contact_source',
        evidence->>'source_kind',
        ''
    )));

    legacy_bound := (
        contact IS NULL
        AND legacy_email <> ''
        AND legacy_email = r.normalized_recipient
        AND COALESCE((evidence->>'direct_publication')::boolean,false)
        AND COALESCE((evidence->>'role_corroborated')::boolean,false)
        AND legacy_source
            IN ('official_site','official_site_current','public_record','press_release')
    );
    IF legacy_bound THEN
        legacy_confidence := 1.0;
    END IF;

    RETURN jsonb_build_object(
        'intent_id', r.id,
        'suppressed', EXISTS(
            SELECT 1
              FROM public.outbound_suppressions s
             WHERE s.normalized_contact=r.normalized_recipient
        ),
        'review_ready', evidence->'review_ready',
        'outreach_ready', evidence->'outreach_ready',
        'bound_to_decision_maker',
            CASE
              WHEN contact IS NOT NULL THEN contact->'bound_to_decision_maker'
              WHEN legacy_bound THEN to_jsonb(true)
              ELSE NULL
            END,
        'contact_source',
            COALESCE(
                contact->>'source',
                evidence->>'contact_source',
                evidence->>'source_kind'
            ),
        'contact_confidence',
            CASE
              WHEN contact IS NOT NULL THEN contact->'confidence'
              WHEN evidence ? 'contact_confidence'
                THEN evidence->'contact_confidence'
              WHEN legacy_confidence IS NOT NULL
                THEN to_jsonb(legacy_confidence)
              ELSE NULL
            END,
        'company_score', r.metadata->'company_score',
        'actual_revenue', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.list_outbound_governor_work(
    p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
    result jsonb;
BEGIN
    IF p_limit IS NULL OR p_limit<1 OR p_limit>100 THEN
        RAISE EXCEPTION 'governor work limit must be 1-100';
    END IF;

    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'intent_id', q.id,
            'status', q.status,
            'expires_at', q.expires_at,
            'updated_at', q.updated_at
        ) ORDER BY
            CASE WHEN q.status='approved' THEN 0 ELSE 1 END,
            q.updated_at,
            q.id
    ), '[]'::jsonb)
    INTO result
    FROM (
        SELECT id,status,expires_at,updated_at
          FROM public.outbound_intents
         WHERE status IN ('pending_approval','approved')
           AND expires_at>clock_timestamp()
         ORDER BY
            CASE WHEN status='approved' THEN 0 ELSE 1 END,
            updated_at,
            id
         LIMIT p_limit
    ) q;

    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.auto_approve_outbound_intent(
  p_intent_id uuid,
  p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
    i public.outbound_intents%ROWTYPE;
    r public.buyer_candidate_reviews%ROWTYPE;
    evidence jsonb;
    contact jsonb;
    review_id uuid;
    approved_today integer;
    result jsonb;
    business_name text;
    contact_norm text;
    business_norm text;
    contact_words integer;
BEGIN
    IF p_daily_cap IS NULL OR p_daily_cap < 1 OR p_daily_cap > 50 THEN
      RAISE EXCEPTION 'standing authority daily cap must be 1-50';
    END IF;

    SELECT * INTO i
    FROM public.outbound_intents
    WHERE id=p_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF i.status='approved' THEN
      RETURN jsonb_build_object(
        'decision','existing',
        'intent_id',i.id,
        'status',i.status,
        'actual_revenue',false
      );
    END IF;

    IF i.status<>'pending_approval' THEN
      RAISE EXCEPTION 'pending outbound intent required';
    END IF;
    IF i.expires_at IS NULL OR i.expires_at <= clock_timestamp() THEN
      RAISE EXCEPTION 'fresh outbound intent required';
    END IF;
    IF i.channel <> 'email'
       OR trim(COALESCE(i.recipient,''))=''
       OR trim(COALESCE(i.subject,''))=''
       OR trim(COALESCE(i.body_text,''))='' THEN
      RAISE EXCEPTION 'complete email intent required';
    END IF;
    IF lower(i.body_text) NOT LIKE '%opt out%'
       AND lower(i.body_text) NOT LIKE '%unsubscribe%'
       AND lower(i.body_text) NOT LIKE '%opt-out%' THEN
      RAISE EXCEPTION 'visible opt-out required';
    END IF;
    IF lower(i.body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
      RAISE EXCEPTION 'approved postal footer required';
    END IF;
    IF i.offer_key <> 'managed_service' THEN
      RAISE EXCEPTION 'offer outside standing authority';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM public.outbound_suppressions s
      WHERE s.normalized_contact=i.normalized_recipient
    ) THEN
      RAISE EXCEPTION 'recipient is suppressed';
    END IF;

    IF EXISTS (
      SELECT 1
      FROM public.outbound_intents prior
      WHERE prior.id<>i.id
        AND prior.normalized_recipient=i.normalized_recipient
        AND prior.status IN (
          'sending','sent','delivered','replied',
          'bounced','failed','suppressed'
        )
    ) THEN
      RAISE EXCEPTION 'existing outbound history requires explicit review';
    END IF;

    BEGIN
      review_id := (i.metadata->>'buyer_candidate_review_id')::uuid;
    EXCEPTION WHEN others THEN
      RAISE EXCEPTION 'buyer candidate review reference required';
    END;

    SELECT * INTO r
    FROM public.buyer_candidate_reviews
    WHERE id=review_id;

    IF NOT FOUND
       OR r.status<>'approved'
       OR r.reviewed_at IS NULL
       OR r.reviewed_at < clock_timestamp()-interval '7 days' THEN
      RAISE EXCEPTION 'fresh approved buyer candidate review required';
    END IF;

    SELECT p.business_name INTO business_name
    FROM public.prospects p
    WHERE p.id=r.prospect_id;

    IF trim(COALESCE(r.contact_name,''))=''
       OR trim(COALESCE(r.contact_title,''))=''
       OR lower(trim(COALESCE(r.contact_email,'')))<>i.normalized_recipient THEN
      RAISE EXCEPTION 'named decision-maker review required';
    END IF;

    contact_norm := trim(
      regexp_replace(lower(r.contact_name),'[^a-z]+',' ','g')
    );
    business_norm := trim(
      regexp_replace(lower(COALESCE(business_name,'')),'[^a-z]+',' ','g')
    );
    contact_words := COALESCE(
      array_length(regexp_split_to_array(contact_norm,'\s+'),1),
      0
    );

    IF contact_words < 2 OR contact_words > 5
       OR contact_norm ~
          '(^| )(your|referral|program|contact|team|company|services?|support|sales|info|office|membership|pricing|quote|estimate|booking|schedule)( |$)'
       OR business_norm = contact_norm
       OR (
         contact_norm <> ''
         AND business_norm LIKE contact_norm || ' %'
       ) THEN
      RAISE EXCEPTION 'plausible named decision-maker required';
    END IF;

    evidence := COALESCE(i.metadata->'candidate_evidence','{}'::jsonb);
    IF COALESCE(lower(evidence->>'review_ready'),'false') <> 'true'
       OR COALESCE(lower(evidence->>'outreach_ready'),'false') <> 'true' THEN
      RAISE EXCEPTION 'review and outreach readiness required';
    END IF;

    IF COALESCE((i.metadata->>'company_score')::numeric,0) < 70 THEN
      RAISE EXCEPTION 'company score below standing authority threshold';
    END IF;

    SELECT item INTO contact
    FROM jsonb_array_elements(
      CASE
        WHEN jsonb_typeof(evidence->'verified_contacts')='array'
        THEN evidence->'verified_contacts'
        ELSE '[]'::jsonb
      END
    ) items(item)
    WHERE lower(trim(COALESCE(item->>'email','')))=i.normalized_recipient
    LIMIT 1;

    IF contact IS NULL
       OR contact->'bound_to_decision_maker' IS DISTINCT FROM 'true'::jsonb
       OR contact->'has_mx' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_valid' IS DISTINCT FROM 'true'::jsonb
       OR contact->'is_disposable' IS DISTINCT FROM 'false'::jsonb
       OR contact->'is_role_address' IS DISTINCT FROM 'false'::jsonb THEN
      RAISE EXCEPTION 'verified decision-maker contact evidence required';
    END IF;

    IF jsonb_typeof(contact->'confidence') <> 'number'
       OR (contact->>'confidence')::numeric < 0.70
       OR COALESCE(contact->>'source','') NOT IN (
         'official_site','official_site_current',
         'public_record','press_release'
       ) THEN
      RAISE EXCEPTION 'contact evidence outside standing authority';
    END IF;

    SELECT count(*)::integer INTO approved_today
    FROM public.outbound_events e
    WHERE e.event_type='approved'
      AND e.actor='gtm-standing-authority'
      AND e.occurred_at >= date_trunc('day',clock_timestamp());

    IF approved_today >= p_daily_cap THEN
      RAISE EXCEPTION 'standing authority daily outbound cap reached';
    END IF;

    result := public.approve_outbound_intent(
      i.id,
      'gtm-standing-authority',
      'Approved automatically under bounded GTM standing authority.'
    );

    RETURN result || jsonb_build_object(
      'standing_authority',true,
      'personhood_revalidated',true,
      'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.auto_approve_outbound_followup(
    p_intent_id uuid,
    p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
    i public.outbound_intents%ROWTYPE;
    root public.outbound_intents%ROWTYPE;
    root_id uuid;
    step integer;
    delivered_at timestamptz;
    first_followup_delivered timestamptz;
    approved_today integer;
    result jsonb;
BEGIN
    IF p_daily_cap IS NULL OR p_daily_cap<1 OR p_daily_cap>50 THEN
        RAISE EXCEPTION 'standing authority daily cap must be 1-50';
    END IF;

    SELECT * INTO i
    FROM public.outbound_intents
    WHERE id=p_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF i.status='approved' THEN
        RETURN jsonb_build_object(
            'decision','existing',
            'intent_id',i.id,
            'status',i.status,
            'actual_revenue',false
        );
    END IF;

    IF i.status<>'pending_approval'
       OR i.expires_at<=clock_timestamp()
       OR i.channel<>'email'
       OR i.metadata->>'sequence_kind'<>'followup' THEN
        RAISE EXCEPTION 'current pending follow-up intent required';
    END IF;

    BEGIN
        root_id := (i.metadata->>'root_intent_id')::uuid;
        step := (i.metadata->>'followup_step')::integer;
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'valid follow-up metadata required';
    END;

    IF step NOT IN (1,2) THEN
        RAISE EXCEPTION 'invalid follow-up step';
    END IF;

    SELECT * INTO root
    FROM public.outbound_intents
    WHERE id=root_id;

    IF NOT FOUND OR root.status<>'delivered' THEN
        RAISE EXCEPTION 'delivered root intent required';
    END IF;

    IF i.normalized_recipient<>root.normalized_recipient THEN
        RAISE EXCEPTION 'follow-up recipient mismatch';
    END IF;

    SELECT max(e.occurred_at) INTO delivered_at
    FROM public.outbound_events e
    WHERE e.intent_id=root.id
      AND e.event_type='delivered';

    IF delivered_at IS NULL THEN
        RAISE EXCEPTION 'root delivery evidence required';
    END IF;

    IF step=1 AND delivered_at > clock_timestamp()-interval '24 hours' THEN
        RAISE EXCEPTION 'first follow-up cooldown active';
    END IF;

    IF step=2 THEN
        SELECT max(e.occurred_at) INTO first_followup_delivered
        FROM public.outbound_intents f
        JOIN public.outbound_events e ON e.intent_id=f.id
        WHERE f.metadata->>'sequence_kind'='followup'
          AND f.metadata->>'root_intent_id'=root.id::text
          AND f.metadata->>'followup_step'='1'
          AND f.id<>i.id
          AND e.event_type='delivered';

        IF first_followup_delivered IS NULL
           OR delivered_at > clock_timestamp()-interval '72 hours'
           OR first_followup_delivered > clock_timestamp()-interval '24 hours' THEN
            RAISE EXCEPTION 'final follow-up is not due';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
        WHERE s.normalized_contact=i.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_replies rep
        JOIN public.outbound_intents ri ON ri.id=rep.intent_id
        WHERE ri.normalized_recipient=i.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'reply already observed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.outbound_events e
        JOIN public.outbound_intents ei ON ei.id=e.intent_id
        WHERE ei.normalized_recipient=i.normalized_recipient
          AND ei.id<>i.id
          AND e.event_type IN ('bounced','complained','failed','suppressed')
    ) THEN
        RAISE EXCEPTION 'negative delivery evidence stops follow-up';
    END IF;

    IF lower(i.body_text) NOT LIKE '%opt out%'
       AND lower(i.body_text) NOT LIKE '%unsubscribe%'
       AND lower(i.body_text) NOT LIKE '%opt-out%' THEN
        RAISE EXCEPTION 'visible opt-out required';
    END IF;

    IF lower(i.body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
        RAISE EXCEPTION 'approved postal footer required';
    END IF;

    SELECT count(*)::integer INTO approved_today
    FROM public.outbound_events e
    WHERE e.event_type='approved'
      AND e.actor='gtm-standing-authority'
      AND e.occurred_at>=date_trunc('day',clock_timestamp());

    IF approved_today>=p_daily_cap THEN
        RAISE EXCEPTION 'standing authority daily outbound cap reached';
    END IF;

    result := public.approve_outbound_intent(
        i.id,
        'gtm-standing-authority',
        'Approved automatically under bounded no-reply follow-up authority.'
    );

    RETURN result || jsonb_build_object(
        'standing_authority',true,
        'sequence_kind','followup',
        'followup_step',step,
        'actual_revenue',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.auto_approve_closer_reply_intent(
    p_intent_id uuid,
    p_daily_cap integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
    i public.outbound_intents%ROWTYPE;
    c public.closer_cases%ROWTYPE;
    x public.outbound_replies%ROWTYPE;
    root public.outbound_intents%ROWTYPE;
    case_id uuid;
    reply_id uuid;
    root_id uuid;
    approved_today integer;
    result jsonb;
BEGIN
    IF p_daily_cap IS NULL OR p_daily_cap<1 OR p_daily_cap>50 THEN
        RAISE EXCEPTION 'standing authority daily cap must be 1-50';
    END IF;

    SELECT * INTO i
      FROM public.outbound_intents
     WHERE id=p_intent_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF i.status='approved' THEN
        RETURN jsonb_build_object(
            'decision','existing',
            'intent_id',i.id,
            'status',i.status,
            'actual_revenue',false
        );
    END IF;

    IF i.status<>'pending_approval'
       OR i.expires_at<=clock_timestamp()
       OR i.channel<>'email'
       OR i.metadata->>'sequence_kind'<>'closer_reply' THEN
        RAISE EXCEPTION 'current pending closer reply intent required';
    END IF;

    BEGIN
        case_id := (i.metadata->>'closer_case_id')::uuid;
        reply_id := (i.metadata->>'inbound_reply_id')::uuid;
        root_id := (i.metadata->>'root_intent_id')::uuid;
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'valid closer reply metadata required';
    END;

    SELECT * INTO c FROM public.closer_cases WHERE id=case_id;
    SELECT * INTO x FROM public.outbound_replies WHERE id=reply_id;
    SELECT * INTO root FROM public.outbound_intents WHERE id=root_id;

    IF c.id IS NULL OR x.id IS NULL OR root.id IS NULL THEN
        RAISE EXCEPTION 'closer reply evidence missing';
    END IF;

    IF c.state IN ('won','lost','paused')
       OR c.buyer_id IS NULL THEN
        RAISE EXCEPTION 'active buyer-bound closer case required';
    END IF;

    IF x.intent_id IS DISTINCT FROM root.id
       OR x.classification NOT IN ('positive','question','objection') THEN
        RAISE EXCEPTION 'commercially engaged inbound reply required';
    END IF;

    IF i.buyer_id IS DISTINCT FROM c.buyer_id
       OR i.prospect_id IS DISTINCT FROM c.prospect_id
       OR i.normalized_recipient IS DISTINCT FROM x.normalized_from_contact
       OR i.normalized_recipient IS DISTINCT FROM root.normalized_recipient THEN
        RAISE EXCEPTION 'closer reply identity mismatch';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.outbound_suppressions s
         WHERE s.normalized_contact=i.normalized_recipient
    ) THEN
        RAISE EXCEPTION 'recipient suppressed';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.outbound_replies newer
         WHERE newer.normalized_from_contact=i.normalized_recipient
           AND newer.received_at>x.received_at
           AND newer.classification IN ('negative','unsubscribe','bounce')
    ) THEN
        RAISE EXCEPTION 'newer negative reply stops closer response';
    END IF;

    IF lower(i.body_text) NOT LIKE '%opt out%'
       AND lower(i.body_text) NOT LIKE '%unsubscribe%'
       AND lower(i.body_text) NOT LIKE '%opt-out%' THEN
        RAISE EXCEPTION 'visible opt-out required';
    END IF;

    IF lower(i.body_text) NOT LIKE '%31 st thomas st, bolton, bl1 2qr, uk%' THEN
        RAISE EXCEPTION 'approved postal footer required';
    END IF;

    IF COALESCE((i.metadata->>'commercial_commitment')::boolean,true) IS NOT FALSE THEN
        RAISE EXCEPTION 'closer reply must not contain binding commercial commitment authority';
    END IF;

    SELECT count(*)::integer INTO approved_today
      FROM public.outbound_events e
     WHERE e.event_type='approved'
       AND e.actor='gtm-standing-authority'
       AND e.occurred_at>=date_trunc('day',clock_timestamp());

    IF approved_today>=p_daily_cap THEN
        RAISE EXCEPTION 'standing authority daily outbound cap reached';
    END IF;

    result := public.approve_outbound_intent(
        i.id,
        'gtm-standing-authority',
        'Approved automatically under bounded closer-reply authority.'
    );

    RETURN result || jsonb_build_object(
        'standing_authority',true,
        'sequence_kind','closer_reply',
        'closer_case_id',c.id,
        'actual_revenue',false
    );
END;
$$;

-- Narrow table capabilities required by SECURITY INVOKER functions.

GRANT SELECT ON
    public.outbound_intents,
    public.outbound_suppressions
TO empire_outbound_sender;

GRANT SELECT ON
    public.outbound_intents,
    public.outbound_suppressions,
    public.outbound_events,
    public.outbound_replies,
    public.buyer_candidate_reviews,
    public.closer_cases
TO empire_outbound_approver;

GRANT UPDATE ON public.outbound_intents
TO empire_outbound_approver;

GRANT INSERT ON public.outbound_events
TO empire_outbound_approver;

-- Read authority belongs only to the sender capability.
REVOKE ALL ON FUNCTION
    public.get_outbound_governor_context(uuid)
FROM PUBLIC, empiredb_app, empire_outbound_approver, empire_reply_ingest;

REVOKE ALL ON FUNCTION
    public.list_outbound_governor_work(integer)
FROM PUBLIC, empiredb_app, empire_outbound_approver, empire_reply_ingest;

GRANT EXECUTE ON FUNCTION
    public.get_outbound_governor_context(uuid)
TO empire_outbound_sender;

GRANT EXECUTE ON FUNCTION
    public.list_outbound_governor_work(integer)
TO empire_outbound_sender;

-- Standing approval remains separate from sender authority.
REVOKE ALL ON FUNCTION
    public.auto_approve_outbound_intent(uuid,integer)
FROM PUBLIC, empiredb_app, empire_outbound_sender, empire_reply_ingest;

REVOKE ALL ON FUNCTION
    public.auto_approve_outbound_followup(uuid,integer)
FROM PUBLIC, empiredb_app, empire_outbound_sender, empire_reply_ingest;

REVOKE ALL ON FUNCTION
    public.auto_approve_closer_reply_intent(uuid,integer)
FROM PUBLIC, empiredb_app, empire_outbound_sender, empire_reply_ingest;

GRANT EXECUTE ON FUNCTION
    public.auto_approve_outbound_intent(uuid,integer)
TO empire_outbound_approver;

GRANT EXECUTE ON FUNCTION
    public.auto_approve_outbound_followup(uuid,integer)
TO empire_outbound_approver;

GRANT EXECUTE ON FUNCTION
    public.auto_approve_closer_reply_intent(uuid,integer)
TO empire_outbound_approver;

RESET ROLE;
