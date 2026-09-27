-- Empire OS — Phase 3D buyer activation gate
-- Migration: 005_buyer_activation_gate
--
-- Existing buyers default to discovered. This migration activates nobody.
-- Allocation remains service-role only and fail-closed.

ALTER TABLE public.buyers
    ADD COLUMN IF NOT EXISTS commercial_activation_state TEXT NOT NULL DEFAULT 'discovered',
    ADD COLUMN IF NOT EXISTS commercial_activated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS commercial_terms_source TEXT,
    ADD COLUMN IF NOT EXISTS commercial_terms_reference TEXT,
    ADD COLUMN IF NOT EXISTS commercial_terms_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS capacity_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS delivery_verified_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'buyers_commercial_activation_state_check'
          AND conrelid = 'public.buyers'::regclass
    ) THEN
        ALTER TABLE public.buyers
            ADD CONSTRAINT buyers_commercial_activation_state_check
            CHECK (commercial_activation_state IN (
                'discovered',
                'prospective',
                'activated',
                'suspended',
                'revoked'
            ));
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_buyers_commercial_activation_state
    ON public.buyers (commercial_activation_state);

COMMENT ON COLUMN public.buyers.commercial_activation_state IS
    'Commercial eligibility state. Only activated buyers may receive allocations.';
COMMENT ON COLUMN public.buyers.commercial_terms_source IS
    'Evidence source for verified commercial terms, such as paid subscription or signed agreement.';
COMMENT ON COLUMN public.buyers.commercial_terms_reference IS
    'Stable reference to the verified payment, subscription, or agreement evidence.';
COMMENT ON COLUMN public.buyers.capacity_verified_at IS
    'Timestamp when configured daily capacity was explicitly verified.';
COMMENT ON COLUMN public.buyers.delivery_verified_at IS
    'Timestamp when the configured delivery destination was explicitly verified.';

CREATE OR REPLACE FUNCTION public.allocate_prospect_atomic(
    p_prospect_id UUID,
    p_allocation_key TEXT,
    p_candidates JSONB,
    p_actor TEXT DEFAULT 'empire_os.buyer_allocation_v1'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_existing public.fulfilment_orders%ROWTYPE;
    v_candidate JSONB;
    v_buyer_id UUID;
    v_buyer public.buyers%ROWTYPE;
    v_order_id UUID;
    v_match_score NUMERIC;
    v_prospect public.prospects%ROWTYPE;
BEGIN
    IF p_prospect_id IS NULL
       OR NULLIF(p_allocation_key, '') IS NULL THEN
        RAISE EXCEPTION 'prospect_id and allocation_key are required';
    END IF;

    IF p_candidates IS NULL
       OR jsonb_typeof(p_candidates) <> 'array' THEN
        RAISE EXCEPTION 'candidates must be a JSON array';
    END IF;

    SELECT *
      INTO v_existing
      FROM public.fulfilment_orders
     WHERE allocation_key = p_allocation_key
     LIMIT 1;

    IF FOUND THEN
        IF v_existing.prospect_id <> p_prospect_id THEN
            RAISE EXCEPTION 'allocation_key belongs to another prospect';
        END IF;
        RETURN jsonb_build_object(
            'decision', 'existing_allocation',
            'fulfilment_order_id', v_existing.id,
            'buyer_id', v_existing.buyer_id,
            'prospect_id', v_existing.prospect_id
        );
    END IF;

    SELECT *
      INTO v_prospect
      FROM public.prospects
     WHERE id = p_prospect_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'prospect not found';
    END IF;

    SELECT *
      INTO v_existing
      FROM public.fulfilment_orders
     WHERE prospect_id = p_prospect_id
       AND state NOT IN ('rejected', 'cancelled')
     ORDER BY created_at ASC
     LIMIT 1;

    IF FOUND THEN
        RETURN jsonb_build_object(
            'decision', 'existing_allocation',
            'fulfilment_order_id', v_existing.id,
            'buyer_id', v_existing.buyer_id,
            'prospect_id', v_existing.prospect_id
        );
    END IF;

    FOR v_candidate IN
        SELECT value
          FROM jsonb_array_elements(p_candidates)
    LOOP
        BEGIN
            v_buyer_id := NULLIF(v_candidate->>'buyer_id', '')::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'candidate buyer_id is invalid';
        END;

        IF v_buyer_id IS NULL THEN
            RAISE EXCEPTION 'candidate buyer_id is required';
        END IF;

        SELECT *
          INTO v_buyer
          FROM public.buyers
         WHERE id = v_buyer_id
           AND COALESCE(is_active, FALSE) = TRUE
           AND lower(trim(COALESCE(status, ''))) = 'active'
           AND lower(trim(COALESCE(commercial_activation_state, ''))) = 'activated'
           AND reviewed_at IS NOT NULL
           AND commercial_activated_at IS NOT NULL
           AND commercial_terms_verified_at IS NOT NULL
           AND capacity_verified_at IS NOT NULL
           AND delivery_verified_at IS NOT NULL
           AND NULLIF(trim(COALESCE(commercial_terms_source, '')), '') IS NOT NULL
           AND NULLIF(trim(COALESCE(commercial_terms_reference, '')), '') IS NOT NULL
           AND NULLIF(trim(COALESCE(niche, '')), '') IS NOT NULL
           AND NULLIF(trim(COALESCE(metro, '')), '') IS NOT NULL
           AND lower(trim(niche)) = lower(trim(COALESCE(v_prospect.niche, '')))
           AND lower(trim(metro)) = lower(trim(COALESCE(v_prospect.metro, '')))
           AND (
               NULLIF(trim(COALESCE(destination_phone, '')), '') IS NOT NULL
               OR NULLIF(trim(COALESCE(webhook_url, '')), '') IS NOT NULL
           )
         FOR UPDATE;

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        IF GREATEST(
            COALESCE(v_buyer.daily_cap, 0)
            - COALESCE(v_buyer.calls_today, 0),
            0
        ) <= 0 THEN
            CONTINUE;
        END IF;

        UPDATE public.buyers
           SET calls_today = COALESCE(calls_today, 0) + 1
         WHERE id = v_buyer_id
           AND lower(trim(COALESCE(commercial_activation_state, ''))) = 'activated'
           AND capacity_verified_at IS NOT NULL
           AND COALESCE(calls_today, 0) < COALESCE(daily_cap, 0);

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        v_match_score := COALESCE(
            NULLIF(v_candidate->>'match_score', '')::NUMERIC,
            0
        );
        v_order_id := gen_random_uuid();

        INSERT INTO public.fulfilment_orders (
            id, prospect_id, buyer_id, state, quantity,
            price_cents, acquisition_cost_cents, fulfilment_cost_cents,
            expected_margin_cents, delivery_payload, commercial_payload,
            allocation_key
        )
        VALUES (
            v_order_id, p_prospect_id, v_buyer_id, 'matched', 1,
            0, 0, 0, 0, '{}'::jsonb,
            jsonb_build_object(
                'allocation_version', 'v1',
                'match_score', v_match_score,
                'candidate_snapshot', v_candidate,
                'buyer_activation_state', v_buyer.commercial_activation_state,
                'commercial_terms_source', v_buyer.commercial_terms_source,
                'commercial_terms_reference', v_buyer.commercial_terms_reference
            ),
            p_allocation_key
        );

        INSERT INTO public.commercial_events (
            event_type, fulfilment_order_id, prospect_id, buyer_id,
            channel, actor, amount_cents, cost_cents, margin_cents, payload
        )
        VALUES (
            'prospect_allocated', v_order_id, p_prospect_id, v_buyer_id,
            'buyer_matching', p_actor, 0, 0, 0,
            jsonb_build_object(
                'allocation_key', p_allocation_key,
                'match_score', v_match_score,
                'candidate_snapshot', v_candidate,
                'commercial_terms_source', v_buyer.commercial_terms_source,
                'commercial_terms_reference', v_buyer.commercial_terms_reference
            )
        );

        RETURN jsonb_build_object(
            'decision', 'allocated',
            'fulfilment_order_id', v_order_id,
            'buyer_id', v_buyer_id,
            'prospect_id', p_prospect_id,
            'match_score', v_match_score
        );
    END LOOP;

    RETURN jsonb_build_object(
        'decision', 'overflow_no_capacity',
        'prospect_id', p_prospect_id,
        'fulfilment_order_id', NULL,
        'buyer_id', NULL
    );
END;
$$;

REVOKE ALL ON FUNCTION public.allocate_prospect_atomic(
    UUID, TEXT, JSONB, TEXT
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.allocate_prospect_atomic(
    UUID, TEXT, JSONB, TEXT
) TO service_role;

COMMENT ON FUNCTION public.allocate_prospect_atomic(
    UUID, TEXT, JSONB, TEXT
) IS
    'Phase 3D: allocate only commercially activated, reviewed, verified buyers with live capacity.';
