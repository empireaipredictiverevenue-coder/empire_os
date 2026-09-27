-- Hydrate strict legacy direct-publication evidence into the outbound governor context.
-- Read-only projection change; does not grant new authority or mutate commercial truth.

CREATE OR REPLACE FUNCTION public.get_outbound_governor_context(
    p_intent_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
    r public.outbound_intents%ROWTYPE;
    evidence jsonb;
    contact jsonb;
    contacts jsonb;
    legacy_email text;
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
    legacy_bound := (
        contact IS NULL
        AND legacy_email <> ''
        AND legacy_email = r.normalized_recipient
        AND COALESCE((evidence->>'direct_publication')::boolean,false)
        AND COALESCE((evidence->>'role_corroborated')::boolean,false)
        AND lower(trim(COALESCE(evidence->>'contact_source','')))
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
            COALESCE(contact->>'source', evidence->>'contact_source'),
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

REVOKE ALL ON FUNCTION public.get_outbound_governor_context(uuid)
FROM PUBLIC,anon,authenticated,service_role,empire_reply_ingest,
     empire_outbound_sender,empire_outbound_approver;

GRANT EXECUTE ON FUNCTION public.get_outbound_governor_context(uuid)
TO empire_outbound_sender;

COMMENT ON FUNCTION public.get_outbound_governor_context(uuid) IS
'Read-only evidence projection for the Phase 3E Outbound Governor, including strict legacy direct-publication normalization.';
