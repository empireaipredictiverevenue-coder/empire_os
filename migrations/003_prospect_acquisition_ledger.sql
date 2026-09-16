-- Empire OS — Canonical Prospect Acquisition Ledger
-- Migration: 003_prospect_acquisition_ledger
-- Safety: append-only schema creation; no UPDATE/DELETE of prospects.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.prospect_identity_claims (
    identity_key TEXT PRIMARY KEY,
    prospect_id UUID NOT NULL
        REFERENCES public.prospects(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.prospect_acquisitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL
        REFERENCES public.prospects(id) ON DELETE RESTRICT,
    ingest_key TEXT NOT NULL,
    identity_keys TEXT[] NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    source_url TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ingest_key)
);

CREATE INDEX IF NOT EXISTS idx_prospect_acquisitions_identity
    ON public.prospect_acquisitions USING GIN (identity_keys);

CREATE INDEX IF NOT EXISTS idx_prospect_acquisitions_prospect
    ON public.prospect_acquisitions (prospect_id);

COMMENT ON TABLE public.prospect_acquisitions IS
    'Immutable acquisition provenance and idempotency ledger for canonical prospects.';

CREATE OR REPLACE FUNCTION public.ingest_prospect_atomic(
    p_prospect JSONB,
    p_evidence JSONB,
    p_ingest_key TEXT,
    p_identity_keys TEXT[]
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_prospect_id UUID;
    v_new_id UUID;
    v_prospect_ids UUID[];
BEGIN
    IF NULLIF(p_ingest_key, '') IS NULL
       OR p_identity_keys IS NULL
       OR cardinality(p_identity_keys) = 0 THEN
        RAISE EXCEPTION 'ingest_key and identity_keys are required';
    END IF;

    SELECT prospect_id
      INTO v_prospect_id
      FROM public.prospect_acquisitions
     WHERE ingest_key = p_ingest_key;

    IF v_prospect_id IS NOT NULL THEN
        RETURN jsonb_build_object(
            'decision', 'existing_ingest',
            'prospect', jsonb_build_object('id', v_prospect_id)
        );
    END IF;

    SELECT array_agg(DISTINCT prospect_id)
      INTO v_prospect_ids
      FROM public.prospect_identity_claims
     WHERE identity_key = ANY(p_identity_keys);

    IF COALESCE(cardinality(v_prospect_ids), 0) > 1 THEN
        RETURN jsonb_build_object(
            'decision', 'ambiguous',
            'reason', 'conflicting_identity_claims',
            'prospect', NULL
        );
    END IF;

    IF COALESCE(cardinality(v_prospect_ids), 0) = 1 THEN
        v_prospect_id := v_prospect_ids[1];
        BEGIN
            INSERT INTO public.prospect_acquisitions (
                prospect_id, ingest_key, identity_keys,
                source, source_url, evidence
            )
            VALUES (
                v_prospect_id,
                p_ingest_key,
                p_identity_keys,
                COALESCE(NULLIF(p_evidence->>'source', ''), 'unknown'),
                NULLIF(p_evidence->>'source_url', ''),
                COALESCE(p_evidence, '{}'::jsonb)
            );
        EXCEPTION WHEN unique_violation THEN
            SELECT prospect_id
              INTO v_prospect_id
              FROM public.prospect_acquisitions
             WHERE ingest_key = p_ingest_key;
        END;

        RETURN jsonb_build_object(
            'decision', 'existing_identity',
            'prospect', jsonb_build_object('id', v_prospect_id)
        );
    END IF;

    BEGIN
        v_new_id := gen_random_uuid();

        INSERT INTO public.prospects (
            id, business_name, niche, metro, phone,
            buy_signal_score, contact_source, contacted_status
        )
        VALUES (
            v_new_id,
            p_prospect->>'business_name',
            p_prospect->>'niche',
            p_prospect->>'metro',
            NULLIF(p_prospect->>'phone', ''),
            COALESCE(NULLIF(p_prospect->>'buy_signal_score', '')::numeric, 0),
            COALESCE(NULLIF(p_prospect->>'contact_source', ''), 'unknown'),
            COALESCE(NULLIF(p_prospect->>'contacted_status', ''), 'not_contacted')
        );

        INSERT INTO public.prospect_identity_claims (
            identity_key, prospect_id
        )
        SELECT DISTINCT identity_key, v_new_id
          FROM unnest(p_identity_keys) AS identity_key;

        INSERT INTO public.prospect_acquisitions (
            prospect_id, ingest_key, identity_keys,
            source, source_url, evidence
        )
        VALUES (
            v_new_id,
            p_ingest_key,
            p_identity_keys,
            COALESCE(NULLIF(p_evidence->>'source', ''), 'unknown'),
            NULLIF(p_evidence->>'source_url', ''),
            COALESCE(p_evidence, '{}'::jsonb)
        );

        RETURN jsonb_build_object(
            'decision', 'created',
            'prospect', jsonb_build_object('id', v_new_id)
        );

    EXCEPTION WHEN unique_violation THEN
        SELECT prospect_id
          INTO v_prospect_id
          FROM public.prospect_acquisitions
         WHERE ingest_key = p_ingest_key;

        IF v_prospect_id IS NOT NULL THEN
            RETURN jsonb_build_object(
                'decision', 'existing_ingest',
                'prospect', jsonb_build_object('id', v_prospect_id)
            );
        END IF;

        SELECT array_agg(DISTINCT prospect_id)
          INTO v_prospect_ids
          FROM public.prospect_identity_claims
         WHERE identity_key = ANY(p_identity_keys);

        IF COALESCE(cardinality(v_prospect_ids), 0) != 1 THEN
            RAISE;
        END IF;

        v_prospect_id := v_prospect_ids[1];

        INSERT INTO public.prospect_acquisitions (
            prospect_id, ingest_key, identity_keys,
            source, source_url, evidence
        )
        VALUES (
            v_prospect_id,
            p_ingest_key,
            p_identity_keys,
            COALESCE(NULLIF(p_evidence->>'source', ''), 'unknown'),
            NULLIF(p_evidence->>'source_url', ''),
            COALESCE(p_evidence, '{}'::jsonb)
        )
        ON CONFLICT (ingest_key) DO NOTHING;

        RETURN jsonb_build_object(
            'decision', 'existing_identity',
            'prospect', jsonb_build_object('id', v_prospect_id)
        );
    END;
END;
$$;

REVOKE ALL ON FUNCTION public.ingest_prospect_atomic(
    JSONB, JSONB, TEXT, TEXT[]
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.ingest_prospect_atomic(
    JSONB, JSONB, TEXT, TEXT[]
) TO service_role;
