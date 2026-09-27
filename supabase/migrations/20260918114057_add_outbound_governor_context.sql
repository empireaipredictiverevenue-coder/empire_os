-- Phase 3E: expose only the evidence needed by the Outbound Governor.
-- Read-only SECURITY DEFINER surface; no table write authority is granted.
BEGIN;

CREATE FUNCTION public.get_outbound_governor_context(
    p_intent_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE
    r public.outbound_intents%ROWTYPE;
    evidence jsonb;
    contact jsonb;
    contacts jsonb;
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
            CASE WHEN contact IS NULL THEN NULL
                 ELSE contact->'bound_to_decision_maker' END,
        'contact_source',
            COALESCE(contact->>'source', evidence->>'contact_source'),
        'contact_confidence',
            CASE WHEN contact IS NULL THEN NULL
                 ELSE contact->'confidence' END,
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
'Read-only evidence projection for the Phase 3E Outbound Governor.';

-- Bounded read-only queue for autonomous governor polling.
CREATE FUNCTION public.list_outbound_governor_work(
    p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
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
        ) ORDER BY q.updated_at, q.id
    ), '[]'::jsonb)
    INTO result
    FROM (
        SELECT id,status,expires_at,updated_at
          FROM public.outbound_intents
         WHERE status IN ('pending_approval','approved')
           AND expires_at>clock_timestamp()
         ORDER BY updated_at,id
         LIMIT p_limit
    ) q;

    RETURN result;
END;
$$;

REVOKE ALL ON FUNCTION public.list_outbound_governor_work(integer)
FROM PUBLIC,anon,authenticated,service_role,empire_outbound_approver,
     empire_reply_ingest,empire_outbound_sender;

GRANT EXECUTE ON FUNCTION public.list_outbound_governor_work(integer)
TO empire_outbound_sender;

COMMENT ON FUNCTION public.list_outbound_governor_work(integer) IS
'Bounded read-only queue for Phase 3E Outbound Governor polling.';

COMMIT;
