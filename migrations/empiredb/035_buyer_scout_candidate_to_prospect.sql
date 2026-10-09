-- Governed Buyer Scout -> canonical raw prospect promotion.
--
-- Internal-only transition:
-- REVIEW_READY Buyer Scout candidate -> canonical prospect.
--
-- This function does NOT:
--   create a buyer
--   create a qualification
--   authorize/send outbound
--   create binding terms
--   move funds
--   recognize revenue

CREATE OR REPLACE FUNCTION
public.promote_buyer_scout_candidate_to_prospect(
    p_candidate_id uuid,
    p_actor text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    v_candidate public.buyer_scout_candidates%ROWTYPE;
    v_verified_people integer := 0;

    v_identity_key text;
    v_ingest_key text;
    v_product_code text;

    v_existing_ids uuid[];
    v_prospect_id uuid;

    v_created boolean := false;
    v_evidence jsonb;
BEGIN
    IF NULLIF(btrim(p_actor), '') IS NULL THEN
        RAISE EXCEPTION
            'actor is required for buyer scout promotion';
    END IF;

    SELECT *
      INTO v_candidate
      FROM public.buyer_scout_candidates
     WHERE id = p_candidate_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_candidate_not_found',
            'candidate_id',
                p_candidate_id,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    -- Idempotent fast path.
    IF v_candidate.canonical_prospect_id IS NOT NULL THEN
        RETURN jsonb_build_object(
            'decision',
                'already_canonical',
            'candidate_id',
                v_candidate.id,
            'canonical_prospect_id',
                v_candidate.canonical_prospect_id,
            'prospect_created',
                false,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'buy_signal_score_policy',
                'UNKNOWN_NULL',
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    -- A canonical buyer is already a stronger commercial identity.
    IF v_candidate.canonical_buyer_id IS NOT NULL THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_existing_canonical_buyer',
            'candidate_id',
                v_candidate.id,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    -- Revalidate the source review state atomically.
    IF v_candidate.review_state <> 'review_ready'
       OR v_candidate.reconciliation_state <> 'REVIEW_READY'
    THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_not_review_ready',
            'candidate_id',
                v_candidate.id,
            'review_state',
                v_candidate.review_state,
            'reconciliation_state',
                v_candidate.reconciliation_state,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    IF NULLIF(btrim(v_candidate.domain), '') IS NULL
       OR NULLIF(btrim(v_candidate.business_name), '') IS NULL
       OR NULLIF(btrim(v_candidate.website), '') IS NULL
    THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_missing_company_identity',
            'candidate_id',
                v_candidate.id,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    IF jsonb_typeof(
        v_candidate.target_product_codes
    ) <> 'array'
       OR jsonb_array_length(
           v_candidate.target_product_codes
       ) = 0
    THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_target_product_missing',
            'candidate_id',
                v_candidate.id,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    -- Revalidate first-party person-bound evidence inside the
    -- same transaction as the canonical promotion.
    SELECT count(*)
      INTO v_verified_people
      FROM jsonb_array_elements(
          COALESCE(
              v_candidate.site_evidence
                  -> 'first_party_people',
              '[]'::jsonb
          )
      ) AS person
     WHERE person
               ->> 'person_explicitly_named'
               = 'true'
       AND person
               ->> 'email_directly_bound_to_person'
               = 'true'
       AND person
               ->> 'mx_verified'
               = 'true'
       AND person
               ->> 'source'
               = 'first_party_site'
       AND NULLIF(
               btrim(person ->> 'name'),
               ''
           ) IS NOT NULL
       AND NULLIF(
               btrim(person ->> 'email'),
               ''
           ) IS NOT NULL
       AND NULLIF(
               btrim(person ->> 'source_url'),
               ''
           ) IS NOT NULL;

    IF v_verified_people = 0 THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_verified_person_evidence_missing',
            'candidate_id',
                v_candidate.id,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    v_product_code :=
        NULLIF(
            btrim(
                v_candidate.target_product_codes
                    ->> 0
            ),
            ''
        );

    IF v_product_code IS NULL THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_target_product_missing',
            'candidate_id',
                v_candidate.id,
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    v_identity_key :=
        'buyer_scout_domain:'
        || lower(
            btrim(v_candidate.domain)
        );

    v_ingest_key :=
        'buyer_scout_candidate:'
        || v_candidate.id::text;

    -- Serialize promotion for this canonical domain.
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            v_identity_key,
            0
        )
    );

    -- Reuse an existing canonical prospect if this exact
    -- acquisition, scoped identity claim, or canonical website
    -- domain already resolves to one prospect.
    SELECT array_agg(
               DISTINCT candidate_prospect_id
           )
      INTO v_existing_ids
      FROM (
          SELECT pa.prospect_id
            AS candidate_prospect_id
            FROM public.prospect_acquisitions pa
           WHERE pa.ingest_key = v_ingest_key

          UNION ALL

          SELECT pic.prospect_id
            FROM public.prospect_identity_claims pic
           WHERE pic.identity_key = v_identity_key

          UNION ALL

          SELECT p.id
            FROM public.prospects p
           WHERE p.website IS NOT NULL
             AND lower(
                   regexp_replace(
                     split_part(
                       regexp_replace(
                         btrim(p.website),
                         '^https?://',
                         '',
                         'i'
                       ),
                       '/',
                       1
                     ),
                     '^www\.',
                     '',
                     'i'
                   )
                 )
                 = lower(
                     btrim(v_candidate.domain)
                   )
      ) AS identities;

    IF COALESCE(
        cardinality(v_existing_ids),
        0
    ) > 1
    THEN
        RETURN jsonb_build_object(
            'decision',
                'blocked_ambiguous_canonical_identity',
            'candidate_id',
                v_candidate.id,
            'matching_prospect_ids',
                to_jsonb(v_existing_ids),
            'database_write_performed',
                false,
            'canonical_promotion_performed',
                false,
            'qualification_created',
                false,
            'buyer_created',
                false,
            'outbound_sent',
                false,
            'terms_accepted',
                false,
            'payment_action',
                false,
            'actual_revenue',
                false
        );
    END IF;

    IF COALESCE(
        cardinality(v_existing_ids),
        0
    ) = 1
    THEN
        v_prospect_id :=
            v_existing_ids[1];
    ELSE
        v_prospect_id :=
            gen_random_uuid();

        INSERT INTO public.prospects (
            id,
            business_name,
            niche,
            website,
            buy_signal_score,
            contact_source,
            contacted_status
        )
        VALUES (
            v_prospect_id,
            v_candidate.business_name,
            v_product_code,
            v_candidate.website,
            NULL,
            'buyer_scout_review_ready',
            'not_contacted'
        );

        v_created := true;
    END IF;

    -- Scoped canonical identity claim.
    INSERT INTO public.prospect_identity_claims (
        identity_key,
        prospect_id
    )
    VALUES (
        v_identity_key,
        v_prospect_id
    )
    ON CONFLICT (identity_key)
    DO NOTHING;

    -- Fail closed if another canonical prospect owns the same
    -- scoped Buyer Scout identity.
    IF EXISTS (
        SELECT 1
          FROM public.prospect_identity_claims
         WHERE identity_key = v_identity_key
           AND prospect_id <> v_prospect_id
    )
    THEN
        RAISE EXCEPTION
            'buyer scout canonical identity conflict for %',
            v_identity_key;
    END IF;

    v_evidence :=
        jsonb_build_object(
            'source',
                'buyer_scout_review_ready',
            'source_url',
                v_candidate.website,
            'candidate_id',
                v_candidate.id,
            'domain',
                v_candidate.domain,
            'business_name',
                v_candidate.business_name,
            'target_product_codes',
                v_candidate.target_product_codes,
            'target_buyer_pools',
                v_candidate.target_buyer_pools,
            'target_corridor_keys',
                v_candidate.target_corridor_keys,
            'verified_person_count',
                v_verified_people,
            'site_evidence',
                v_candidate.site_evidence,
            'provenance',
                v_candidate.provenance,
            'promoted_by',
                p_actor
        );

    INSERT INTO public.prospect_acquisitions (
        prospect_id,
        ingest_key,
        identity_keys,
        source,
        source_url,
        evidence
    )
    VALUES (
        v_prospect_id,
        v_ingest_key,
        ARRAY[v_identity_key],
        'buyer_scout_review_ready',
        v_candidate.website,
        v_evidence
    )
    ON CONFLICT (ingest_key)
    DO NOTHING;

    UPDATE public.buyer_scout_candidates
       SET canonical_prospect_id =
               v_prospect_id,
           review_state =
               'promoted',
           reconciliation_state =
               'PROMOTED',
           provenance =
               COALESCE(
                   provenance,
                   '{}'::jsonb
               )
               || jsonb_build_object(
                   'raw_prospect_promotion',
                   jsonb_build_object(
                       'actor',
                           p_actor,
                       'promoted_at',
                           now(),
                       'canonical_prospect_id',
                           v_prospect_id,
                       'verified_person_count',
                           v_verified_people,
                       'product_code',
                           v_product_code
                   )
               ),
           updated_at =
               now()
     WHERE id =
           v_candidate.id;

    RETURN jsonb_build_object(
        'decision',
            CASE
                WHEN v_created
                THEN 'raw_prospect_created'
                ELSE 'raw_prospect_attached'
            END,
        'candidate_id',
            v_candidate.id,
        'canonical_prospect_id',
            v_prospect_id,
        'prospect_created',
            v_created,
        'database_write_performed',
            true,
        'canonical_promotion_performed',
            true,
        'buy_signal_score_policy',
            'UNKNOWN_NULL',
        'verified_person_count',
            v_verified_people,
        'product_code',
            v_product_code,
        'qualification_created',
            false,
        'buyer_created',
            false,
        'outbound_sent',
            false,
        'terms_accepted',
            false,
        'payment_action',
            false,
        'actual_revenue',
            false
    );
END;
$function$;

REVOKE ALL ON FUNCTION
public.promote_buyer_scout_candidate_to_prospect(
    uuid,
    text
)
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION
public.promote_buyer_scout_candidate_to_prospect(
    uuid,
    text
)
TO empiredb_app;

COMMENT ON FUNCTION
public.promote_buyer_scout_candidate_to_prospect(
    uuid,
    text
)
IS
    'Atomically promotes a REVIEW_READY Buyer Scout holding to a canonical raw prospect with no buyer, qualification, outbound, terms, payment or revenue authority.';
