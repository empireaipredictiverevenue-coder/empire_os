-- Provision a non-active buyer record from a genuine closer case.
-- This does NOT activate capacity, accept terms, allocate inventory, move funds,
-- confirm payment, fulfil work, or recognize revenue.
BEGIN;

CREATE OR REPLACE FUNCTION public.provision_buyer_from_closer_case(
    p_case_id uuid,
    p_actor text DEFAULT 'empire_closer_planner'
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
    c public.closer_cases%ROWTYPE;
    i public.outbound_intents%ROWTYPE;
    p public.prospects%ROWTYPE;
    r public.buyer_candidate_reviews%ROWTYPE;
    b public.buyers%ROWTYPE;
    review_id uuid;
    v_buyer_name text;
    v_buyer_niche text;
    v_buyer_metro text;
    v_buyer_email text;
    v_buyer_contact text;
    actor text := trim(COALESCE(p_actor,''));
BEGIN
    IF p_case_id IS NULL THEN
        RAISE EXCEPTION 'closer case id required';
    END IF;
    IF actor='' THEN
        RAISE EXCEPTION 'actor required';
    END IF;

    SELECT * INTO c
      FROM public.closer_cases
     WHERE id=p_case_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'closer case not found';
    END IF;

    IF c.state NOT IN ('engaged','qualified') THEN
        RAISE EXCEPTION 'engaged or qualified closer case required';
    END IF;

    IF c.buyer_id IS NOT NULL THEN
        SELECT * INTO b FROM public.buyers WHERE id=c.buyer_id;
        IF FOUND THEN
            RETURN jsonb_build_object(
                'decision','existing',
                'case_id',c.id,
                'buyer_id',b.id,
                'commercial_activation_state',b.commercial_activation_state,
                'actual_revenue',false
            );
        END IF;
    END IF;

    SELECT * INTO i
      FROM public.outbound_intents
     WHERE id=c.outbound_intent_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbound intent not found';
    END IF;

    IF c.prospect_id IS NULL OR i.prospect_id IS DISTINCT FROM c.prospect_id THEN
        RAISE EXCEPTION 'canonical prospect binding required';
    END IF;

    SELECT * INTO p
      FROM public.prospects
     WHERE id=c.prospect_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'prospect not found';
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
       OR COALESCE(lower(r.evidence->>'outreach_ready'),'false')<>'true' THEN
        RAISE EXCEPTION 'approved outreach-ready buyer review required';
    END IF;

    IF r.prospect_id IS DISTINCT FROM p.id THEN
        RAISE EXCEPTION 'buyer review prospect mismatch';
    END IF;

    v_buyer_name := trim(COALESCE(r.evidence->>'business_name',p.business_name,''));
    v_buyer_niche := trim(COALESCE(r.evidence->>'niche',p.niche,''));
    v_buyer_metro := trim(COALESCE(r.evidence->>'metro',p.metro,''));
    v_buyer_email := lower(trim(COALESCE(r.contact_email,i.recipient,'')));
    v_buyer_contact := trim(COALESCE(r.contact_name,p.contact_name,''));

    IF v_buyer_name='' OR v_buyer_niche='' OR v_buyer_email='' THEN
        RAISE EXCEPTION 'buyer identity evidence incomplete';
    END IF;

    SELECT * INTO b
      FROM public.buyers
     WHERE lower(trim(COALESCE(email,'')))=v_buyer_email
     ORDER BY created_at ASC
     LIMIT 1
     FOR UPDATE;

    IF NOT FOUND THEN
        SELECT * INTO b
          FROM public.buyers
         WHERE buyer_name=v_buyer_name
           AND niche=v_buyer_niche
         ORDER BY created_at ASC
         LIMIT 1
         FOR UPDATE;
    END IF;

    IF NOT FOUND THEN
        BEGIN
            INSERT INTO public.buyers(
                buyer_name,
                niche,
                metro,
                email,
                contact_name,
                daily_cap,
                calls_today,
                is_active,
                status,
                commercial_activation_state,
                notes
            ) VALUES (
                v_buyer_name,
                v_buyer_niche,
                NULLIF(v_buyer_metro,''),
                v_buyer_email,
                NULLIF(v_buyer_contact,''),
                0,
                0,
                false,
                'pending_commercial_evidence',
                'prospective',
                'Provisioned from genuine closer case ' || c.id::text
            )
            RETURNING * INTO b;
        EXCEPTION WHEN unique_violation THEN
            SELECT * INTO b
              FROM public.buyers
             WHERE buyer_name=v_buyer_name
               AND niche=v_buyer_niche
             ORDER BY created_at ASC
             LIMIT 1
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE;
            END IF;
        END;
    END IF;

    UPDATE public.closer_cases
       SET buyer_id=b.id,
           updated_at=clock_timestamp()
     WHERE id=c.id
     RETURNING * INTO c;

    INSERT INTO public.closer_events(case_id,event_type,actor,payload)
    VALUES(
        c.id,
        'buyer_provisioned',
        actor,
        jsonb_build_object(
            'buyer_id',b.id,
            'buyer_name',b.buyer_name,
            'email',b.email,
            'commercial_activation_state',b.commercial_activation_state,
            'actual_revenue',false
        )
    );

    RETURN jsonb_build_object(
        'decision','provisioned',
        'case_id',c.id,
        'buyer_id',b.id,
        'commercial_activation_state',b.commercial_activation_state,
        'is_active',COALESCE(b.is_active,false),
        'actual_revenue',false
    );
END;
$$;

REVOKE ALL ON FUNCTION public.provision_buyer_from_closer_case(uuid,text)
  FROM PUBLIC,anon,authenticated,empire_closer_approver;

GRANT EXECUTE ON FUNCTION public.provision_buyer_from_closer_case(uuid,text)
  TO service_role;

COMMENT ON FUNCTION public.provision_buyer_from_closer_case(uuid,text) IS
'Creates or reuses a non-active prospective buyer from a genuine closer case. No commercial activation, allocation, payment, fulfilment or revenue mutation.';

COMMIT;
