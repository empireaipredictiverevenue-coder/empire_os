-- Prioritize already-approved outbound sends before pending approvals.
-- This prevents a blocked approval from starving the actionable send queue.

CREATE OR REPLACE FUNCTION public.list_outbound_governor_work(
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

REVOKE ALL ON FUNCTION public.list_outbound_governor_work(integer)
FROM PUBLIC,anon,authenticated,empire_outbound_approver,
     empire_reply_ingest,empire_outbound_sender;

GRANT EXECUTE ON FUNCTION public.list_outbound_governor_work(integer)
TO empire_outbound_sender, service_role;

COMMENT ON FUNCTION public.list_outbound_governor_work(integer) IS
'Bounded read-only queue for Phase 3E Outbound Governor polling; approved sends are prioritized before pending approvals.';
