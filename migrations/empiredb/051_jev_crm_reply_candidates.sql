-- EmpireDB 051 — tenant-scoped JEV reply candidate visibility.
-- PREPARED ONLY. Do not apply without separate founder migration approval.
-- READ-ONLY metadata RPC for EXISTING empire_revenue_crm_reader group.
-- No new roles, LOGINs, memberships, tables, DML, sender, or mail privileges.
-- Presence in the database does NOT prove original provider authentication.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $guard$
DECLARE item text;
BEGIN
    IF current_database() <> 'empiredb' THEN
        RAISE EXCEPTION 'canonical EmpireDB required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'empire_revenue_crm_reader'
          AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
          AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb
    ) THEN
        RAISE EXCEPTION 'existing restricted CRM reader role required';
    END IF;
    IF pg_catalog.to_regprocedure('public.empire_crm_prospect_authorized(uuid)') IS NULL
       OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL THEN
        RAISE EXCEPTION 'canonical tenant/prospect functions required';
    END IF;
    IF pg_catalog.to_regprocedure(
        'public.empire_read_crm_reply_candidates(uuid,integer)'
    ) IS NOT NULL THEN
        RAISE EXCEPTION 'existing reply candidate function needs reconciliation';
    END IF;
    FOREACH item IN ARRAY ARRAY[
        'public.outbound_intents', 'public.outbound_replies',
        'public.empire_conversations'
    ] LOOP
        IF pg_catalog.to_regclass(item) IS NULL
           OR NOT pg_catalog.has_table_privilege(current_user, item, 'SELECT') THEN
            RAISE EXCEPTION 'missing migrator source access: %', item;
        END IF;
        IF pg_catalog.has_table_privilege(
            'empire_revenue_crm_reader',item,'SELECT'
        ) THEN
            RAISE EXCEPTION 'unsafe direct cross-tenant reader privilege: %', item;
        END IF;
    END LOOP;
END;
$guard$;

CREATE FUNCTION public.empire_read_crm_reply_candidates(
    p_prospect_id uuid, p_limit integer DEFAULT 25
)
RETURNS TABLE (
    tenant_id uuid,
    prospect_id uuid,
    reply_id uuid,
    outbound_intent_id uuid,
    received_at timestamp with time zone,
    reply_classification text,
    intent_status text,
    provider_reference_present boolean,
    matching_conversation_count integer,
    original_provider_authenticated boolean,
    contact_binding_verified boolean
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = ''
SET timezone = 'UTC'
AS $fn$
DECLARE
    v_tenant uuid;
BEGIN
    IF p_prospect_id IS NULL OR p_limit IS NULL
       OR p_limit < 1 OR p_limit > 100 THEN
        RAISE EXCEPTION 'bounded canonical prospect and limit required';
    END IF;
    v_tenant := public.empire_current_tenant_id();
    IF v_tenant IS NULL
       OR public.empire_crm_prospect_authorized(p_prospect_id) IS NOT TRUE THEN
        RAISE EXCEPTION 'authenticated tenant prospect scope required';
    END IF;
    RETURN QUERY
        SELECT
            v_tenant AS tenant_id,
            i.prospect_id,
            r.id AS reply_id,
            i.id AS outbound_intent_id,
            r.received_at,
            r.classification AS reply_classification,
            i.status AS intent_status,
            (
                r.provider_message_id IS NOT NULL
                AND length(btrim(r.provider_message_id)) > 0
            ) AS provider_reference_present,
            (
                SELECT count(*)::integer
                FROM public.empire_conversations c
                WHERE c.outbound_intent_id = i.id
                  AND c.channel = 'email'
                  AND c.prospect_id = i.prospect_id
            ) AS matching_conversation_count,
            FALSE AS original_provider_authenticated,
            FALSE AS contact_binding_verified
        FROM public.outbound_replies r
        JOIN public.outbound_intents i
          ON i.id = r.intent_id
        WHERE i.prospect_id = p_prospect_id
          AND i.channel = 'email'
          AND r.received_at <= CURRENT_TIMESTAMP
        ORDER BY r.received_at DESC, r.id DESC
        LIMIT p_limit;
END;
$fn$;

REVOKE ALL ON FUNCTION
    public.empire_read_crm_reply_candidates(uuid,integer)
FROM PUBLIC, empiredb_app, empiredb_readonly, empiredb_tenant_reader;

GRANT EXECUTE ON FUNCTION
    public.empire_read_crm_reply_candidates(uuid,integer)
TO empire_revenue_crm_reader;

COMMENT ON FUNCTION
    public.empire_read_crm_reply_candidates(uuid,integer)
IS 'Restricted tenant-scoped reply candidate metadata only. No provider authenticity, buyer intent, contact consent or send authority.';

COMMIT;
