BEGIN;

SET LOCAL ROLE empiredb_migrator;

DO $guard$
BEGIN
    IF current_database() <> 'empiredb' THEN
        RAISE EXCEPTION 'EmpireDB required';
    END IF;

    IF to_regprocedure(
        'public.empire_current_tenant_id()'
    ) IS NULL THEN
        RAISE EXCEPTION 'empire_current_tenant_id() required';
    END IF;

    IF to_regclass(
        'public.tenant_business_entity_bindings'
    ) IS NULL THEN
        RAISE EXCEPTION
            'tenant_business_entity_bindings required';
    END IF;

    IF to_regclass(
        'public.intelligence_signals'
    ) IS NULL THEN
        RAISE EXCEPTION 'intelligence_signals required';
    END IF;

    IF to_regclass(
        'public.intelligence_sources'
    ) IS NULL THEN
        RAISE EXCEPTION 'intelligence_sources required';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_roles
        WHERE rolname = 'empiredb_tenant_reader'
          AND NOT rolcanlogin
          AND NOT rolsuper
    ) THEN
        RAISE EXCEPTION
            'guarded empiredb_tenant_reader role required';
    END IF;

    IF to_regclass('public.economic_signal_provenance') IS NULL THEN
        RAISE EXCEPTION 'economic_signal_provenance required';
    END IF;
    IF NOT pg_catalog.has_table_privilege(
        'empiredb_migrator','public.economic_signal_provenance','SELECT'
    ) THEN
        RAISE EXCEPTION 'economic provenance SELECT privilege required';
    END IF;

    -- Validate the actual SECURITY DEFINER owner's read permissions.
    IF NOT pg_catalog.has_table_privilege(
        'empiredb_migrator',
        'public.tenant_business_entity_bindings',
        'SELECT'
    ) OR NOT pg_catalog.has_table_privilege(
        'empiredb_migrator',
        'public.intelligence_signals',
        'SELECT'
    ) OR NOT pg_catalog.has_table_privilege(
        'empiredb_migrator',
        'public.intelligence_sources',
        'SELECT'
    ) THEN
        RAISE EXCEPTION
            'economic signal reader owner SELECT privileges required';
    END IF;
END;
$guard$;


CREATE OR REPLACE FUNCTION
public.empire_read_economic_signals(
    p_entity_id uuid DEFAULT NULL,
    p_as_of timestamp with time zone
        DEFAULT CURRENT_TIMESTAMP
)
RETURNS TABLE (
    signal_id uuid,
    entity_id uuid,
    signal_type text,
    signal_domain text,
    observed_at timestamp with time zone,
    expires_at timestamp with time zone,
    strength numeric,
    confidence numeric,
    source_id uuid,
    source_key text,
    source_type text,
    source_authority_score numeric,
    payload jsonb,
    tenant_binding_ref text
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
SET timezone = 'UTC'
AS $function$
DECLARE
    v_tenant_id uuid;
BEGIN
    IF p_as_of IS NULL THEN
        RAISE EXCEPTION 'as_of required';
    END IF;

    v_tenant_id :=
        public.empire_current_tenant_id();

    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION
            'authenticated tenant binding required';
    END IF;


    -- Match the Python resolver: multiple active kinds are ambiguous.
    IF EXISTS (
        SELECT 1
        FROM public.tenant_business_entity_bindings b
        WHERE b.tenant_id = v_tenant_id
          AND b.active IS TRUE
          AND b.valid_from <= p_as_of
          AND (b.valid_until IS NULL OR b.valid_until > p_as_of)
          AND (p_entity_id IS NULL OR b.entity_id = p_entity_id)
        GROUP BY b.entity_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'tenant_entity_binding_ambiguous';
    END IF;

    RETURN QUERY
    SELECT
        s.id,
        s.entity_id,
        s.signal_type,
        s.signal_domain,
        s.observed_at,
        s.expires_at,
        s.strength,
        s.confidence,
        src.id,
        src.source_key,
        src.source_type,
        src.authority_score,
        s.payload,
        b.evidence_ref
    FROM public.intelligence_signals s
    JOIN public.economic_signal_provenance provenance
      ON provenance.signal_id = s.id
     AND provenance.tenant_id = v_tenant_id
     AND provenance.signal_snapshot = (to_jsonb(s) - 'created_at')
    JOIN public.intelligence_sources src
      ON src.id = s.source_id
    JOIN public.tenant_business_entity_bindings b
      ON b.entity_id = s.entity_id
     AND b.tenant_id = v_tenant_id
     AND b.active IS TRUE
     AND b.valid_from <= p_as_of
     AND (
        b.valid_until IS NULL
        OR b.valid_until > p_as_of
     )
    WHERE
        (
            p_entity_id IS NULL
            OR s.entity_id = p_entity_id
        )
        AND s.signal_type IN (
            'revenue_leak',
            'idle_asset',
            'market_gap',
            'idle_waste'
        )
        -- Tenant label is necessary, not proof of writer authority.
        AND jsonb_typeof(s.payload -> '_economic_signal') = 'object'
        AND s.payload #>> '{_economic_signal,tenant_id}' = v_tenant_id::text
        AND s.payload #>> '{_economic_signal,tenant_binding_ref}' = b.evidence_ref
        AND src.source_key = 'empire.' || s.signal_type || '.observed.v1'
        AND src.enabled IS TRUE
        AND s.observed_at >= p_as_of - interval '24 hours'
        AND s.observed_at <= p_as_of
        AND (
            s.expires_at IS NULL
            OR s.expires_at > p_as_of
        )
    ORDER BY
        s.observed_at DESC,
        s.id;
END;
$function$;


REVOKE ALL ON FUNCTION
public.empire_read_economic_signals(
    uuid,
    timestamp with time zone
) FROM PUBLIC;

REVOKE ALL ON FUNCTION
public.empire_read_economic_signals(
    uuid,
    timestamp with time zone
) FROM empiredb_app;

GRANT EXECUTE ON FUNCTION
public.empire_read_economic_signals(
    uuid,
    timestamp with time zone
) TO empiredb_tenant_reader;


COMMENT ON FUNCTION
public.empire_read_economic_signals(
    uuid,
    timestamp with time zone
) IS
'Tenant-scoped OBSERVE-only Economic Signal reader. Tenant identity is derived from authenticated database role; no execution authority.';

COMMIT;
