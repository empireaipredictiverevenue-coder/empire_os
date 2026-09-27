-- Preserve observed buyer-contact provenance during canonical prospect promotion.
-- Fallback to first_party_site only when no explicit source/identity_source exists.

CREATE OR REPLACE FUNCTION public.promote_buyer_scout_candidate_to_prospect(p_candidate_id uuid, p_actor text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
  candidate public.buyer_scout_candidates%ROWTYPE;
  prospect_id uuid;
  prospect_matches integer := 0;
  prospect_created boolean := false;
  normalized_name text;
  normalized_domain text;
  corridor_pair_count integer := 0;
  derived_niche text;
  derived_metro text;
  first_party_phone text;
  first_party_person jsonb;
  contact_name text;
  contact_title text;
  contact_source text;
BEGIN
  IF p_candidate_id IS NULL OR trim(COALESCE(p_actor, '')) = '' THEN
    RAISE EXCEPTION 'candidate id and actor required';
  END IF;

  SELECT *
  INTO candidate
  FROM public.buyer_scout_candidates
  WHERE id = p_candidate_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'decision', 'candidate_not_found',
      'candidate_id', p_candidate_id,
      'database_write_performed', false,
      'canonical_promotion_performed', false,
      'qualification_created', false,
      'buyer_created', false,
      'outbound_sent', false,
      'actual_revenue', false
    );
  END IF;

  IF candidate.review_state <> 'review_ready'
     OR candidate.reconciliation_state <> 'REVIEW_READY' THEN
    RETURN jsonb_build_object(
      'decision', 'blocked_not_review_ready',
      'candidate_id', candidate.id,
      'review_state', candidate.review_state,
      'reconciliation_state', candidate.reconciliation_state,
      'database_write_performed', false,
      'canonical_promotion_performed', false,
      'qualification_created', false,
      'buyer_created', false,
      'outbound_sent', false,
      'actual_revenue', false
    );
  END IF;

  IF candidate.canonical_buyer_id IS NOT NULL THEN
    RETURN jsonb_build_object(
      'decision', 'blocked_existing_canonical_buyer',
      'candidate_id', candidate.id,
      'canonical_buyer_id', candidate.canonical_buyer_id,
      'database_write_performed', false,
      'canonical_promotion_performed', false,
      'qualification_created', false,
      'buyer_created', false,
      'outbound_sent', false,
      'actual_revenue', false
    );
  END IF;

  IF candidate.canonical_prospect_id IS NOT NULL THEN
    IF EXISTS (
      SELECT 1
      FROM public.prospects
      WHERE id = candidate.canonical_prospect_id
    ) THEN
      UPDATE public.buyer_scout_candidates
      SET review_state = 'promoted',
          reconciliation_state = 'PROMOTED',
          updated_at = clock_timestamp(),
          provenance = candidate.provenance || jsonb_build_object(
            'canonical_prospect_promotion',
            jsonb_build_object(
              'actor', trim(p_actor),
              'prospect_id', candidate.canonical_prospect_id,
              'decision', 'already_linked',
              'promoted_at', clock_timestamp(),
              'qualification_created', false,
              'buyer_created', false,
              'outreach_authorized', false
            )
          )
      WHERE id = candidate.id;

      RETURN jsonb_build_object(
        'decision', 'already_linked_promoted',
        'candidate_id', candidate.id,
        'canonical_prospect_id', candidate.canonical_prospect_id,
        'prospect_created', false,
        'database_write_performed', true,
        'canonical_promotion_performed', true,
        'buy_signal_score_policy', 'UNKNOWN_NULL',
        'qualification_created', false,
        'buyer_created', false,
        'outbound_sent', false,
        'actual_revenue', false
      );
    END IF;

    RETURN jsonb_build_object(
      'decision', 'blocked_broken_canonical_prospect_link',
      'candidate_id', candidate.id,
      'canonical_prospect_id', candidate.canonical_prospect_id,
      'database_write_performed', false,
      'canonical_promotion_performed', false,
      'qualification_created', false,
      'buyer_created', false,
      'outbound_sent', false,
      'actual_revenue', false
    );
  END IF;

  normalized_name := lower(trim(COALESCE(candidate.business_name, '')));
  normalized_domain := lower(trim(COALESCE(candidate.domain, '')));

  IF normalized_name = ''
     OR normalized_domain = ''
     OR trim(COALESCE(candidate.website, '')) = '' THEN
    RETURN jsonb_build_object(
      'decision', 'blocked_identity_incomplete',
      'candidate_id', candidate.id,
      'database_write_performed', false,
      'canonical_promotion_performed', false,
      'qualification_created', false,
      'buyer_created', false,
      'outbound_sent', false,
      'actual_revenue', false
    );
  END IF;

  IF normalized_name IN (
      'home', 'about', 'about us', 'contact', 'contact us',
      'services', 'our services', 'welcome', 'homepage', 'index',
      'learn more', 'read more', 'click here', 'get started',
      'step 1', 'step 2', 'step 3'
     )
     OR normalized_name ~
       '^(home|about( us)?|contact( us)?|services?|step[[:space:]]+[0-9]+)[[:space:]]*[-|:]'
  THEN
    RETURN jsonb_build_object(
      'decision', 'blocked_business_name_not_verified',
      'candidate_id', candidate.id,
      'business_name', candidate.business_name,
      'database_write_performed', false,
      'canonical_promotion_performed', false,
      'qualification_created', false,
      'buyer_created', false,
      'outbound_sent', false,
      'actual_revenue', false
    );
  END IF;

  SELECT count(*)::integer
  INTO prospect_matches
  FROM public.prospects p
  WHERE regexp_replace(
          lower(
            split_part(
              split_part(
                regexp_replace(
                  trim(COALESCE(p.website, '')),
                  '^https?://',
                  '',
                  'i'
                ),
                '/',
                1
              ),
              ':',
              1
            )
          ),
          '^www\\.',
          '',
          'i'
        ) = normalized_domain;

  IF prospect_matches = 1 THEN
    SELECT p.id
    INTO prospect_id
    FROM public.prospects p
    WHERE regexp_replace(
            lower(
              split_part(
                split_part(
                  regexp_replace(
                    trim(COALESCE(p.website, '')),
                    '^https?://',
                    '',
                    'i'
                  ),
                  '/',
                  1
                ),
                ':',
                1
              )
            ),
            '^www\\.',
            '',
            'i'
          ) = normalized_domain
    ORDER BY p.id::text
    LIMIT 1;
  END IF;

  IF prospect_matches > 1 THEN
    RETURN jsonb_build_object(
      'decision', 'blocked_ambiguous_existing_prospect',
      'candidate_id', candidate.id,
      'domain', normalized_domain,
      'matching_prospect_count', prospect_matches,
      'database_write_performed', false,
      'canonical_promotion_performed', false,
      'qualification_created', false,
      'buyer_created', false,
      'outbound_sent', false,
      'actual_revenue', false
    );
  END IF;

  IF prospect_matches = 0 THEN
    SELECT
      count(DISTINCT split_part(value, ':', 3) || ':' || split_part(value, ':', 4))::integer,
      max(replace(split_part(value, ':', 3), '_', ' ')),
      max(replace(split_part(value, ':', 4), '_', ' '))
    INTO corridor_pair_count, derived_niche, derived_metro
    FROM jsonb_array_elements_text(candidate.target_corridor_keys) AS corridor(value)
    WHERE split_part(value, ':', 1) = 'corridor'
      AND split_part(value, ':', 2) = 'v1'
      AND split_part(value, ':', 3) <> ''
      AND split_part(value, ':', 4) <> '';

    IF corridor_pair_count <> 1 THEN
      derived_niche := NULL;
      derived_metro := NULL;
    END IF;

    IF jsonb_typeof(candidate.site_evidence -> 'first_party_phones') = 'array'
       AND jsonb_array_length(candidate.site_evidence -> 'first_party_phones') = 1
    THEN
      first_party_phone := NULLIF(
        trim(candidate.site_evidence -> 'first_party_phones' ->> 0),
        ''
      );
    ELSE
      first_party_phone := NULL;
    END IF;

    IF jsonb_typeof(candidate.site_evidence -> 'first_party_people') = 'array'
       AND jsonb_array_length(candidate.site_evidence -> 'first_party_people') = 1
    THEN
      first_party_person := candidate.site_evidence -> 'first_party_people' -> 0;
      contact_name := NULLIF(trim(first_party_person ->> 'name'), '');
      contact_title := NULLIF(trim(first_party_person ->> 'title'), '');
      contact_source := COALESCE(
        NULLIF(trim(first_party_person ->> 'source'), ''),
        NULLIF(trim(first_party_person ->> 'identity_source'), ''),
        'first_party_site'
      );
    ELSE
      contact_name := NULL;
      contact_title := NULL;
      contact_source := NULL;
    END IF;

    INSERT INTO public.prospects(
      business_name,
      niche,
      metro,
      phone,
      website,
      buy_signal_score,
      status,
      notes,
      contact_name,
      contact_title,
      contact_source,
      contacted_at,
      contacted_status
    ) VALUES (
      candidate.business_name,
      derived_niche,
      derived_metro,
      first_party_phone,
      candidate.website,
      NULL,
      'new',
      'buyer_scout_candidate:' || candidate.id::text || '; research_evidence_only',
      contact_name,
      contact_title,
      CASE WHEN contact_name IS NOT NULL THEN contact_source ELSE NULL END,
      NULL,
      'not_contacted'
    )
    RETURNING id INTO prospect_id;

    prospect_created := true;
  END IF;

  UPDATE public.buyer_scout_candidates
  SET canonical_prospect_id = prospect_id,
      review_state = 'promoted',
      reconciliation_state = 'PROMOTED',
      updated_at = clock_timestamp(),
      provenance = candidate.provenance || jsonb_build_object(
        'canonical_prospect_promotion',
        jsonb_build_object(
          'actor', trim(p_actor),
          'prospect_id', prospect_id,
          'prospect_created', prospect_created,
          'promoted_at', clock_timestamp(),
          'buy_signal_score_policy', 'UNKNOWN_NULL',
          'qualification_created', false,
          'buyer_created', false,
          'outreach_authorized', false,
          'actual_revenue', false
        )
      )
  WHERE id = candidate.id;

  RETURN jsonb_build_object(
    'decision',
      CASE
        WHEN prospect_created THEN 'raw_prospect_created'
        ELSE 'existing_prospect_linked'
      END,
    'candidate_id', candidate.id,
    'canonical_prospect_id', prospect_id,
    'prospect_created', prospect_created,
    'database_write_performed', true,
    'canonical_promotion_performed', true,
    'buy_signal_score_policy', 'UNKNOWN_NULL',
    'qualification_created', false,
    'buyer_created', false,
    'outbound_sent', false,
    'terms_accepted', false,
    'actual_revenue', false
  );
END;
$function$

