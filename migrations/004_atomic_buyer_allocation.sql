-- Empire OS — Phase 3D atomic buyer allocation
-- Migration: 004_atomic_buyer_allocation
--
-- Purpose:
--   Race-safe exclusive prospect allocation to an eligible buyer.
--   Buyer capacity gates allocation only; prospect acquisition remains independent.
--
-- Safety:
--   No existing prospect identity is updated or deleted.
--   No outreach or delivery side effect is performed.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE public.fulfilment_orders
    ADD COLUMN IF NOT EXISTS allocation_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fulfilment_orders_allocation_key
    ON public.fulfilment_orders (allocation_key)
    WHERE allocation_key IS NOT NULL;

COMMENT ON COLUMN public.fulfilment_orders.allocation_key IS
    'Idempotency key for one governed commercial allocation decision.';

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
    v_locked_prospect_id UUID;
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

    SELECT id
      INTO v_locked_prospect_id
      FROM public.prospects
     WHERE id = p_prospect_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'prospect not found';
    END IF;

    -- Recheck after taking the prospect lock. This serializes even callers
    -- that accidentally use different allocation keys for one prospect.
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
            v_buyer_id := NULLIF(
                v_candidate->>'buyer_id',
                ''
            )::UUID;
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
           AND lower(trim(COALESCE(status, ''))) NOT IN (
               'inactive', 'disabled'
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
            id,
            prospect_id,
            buyer_id,
            state,
            quantity,
            price_cents,
            acquisition_cost_cents,
            fulfilment_cost_cents,
            expected_margin_cents,
            delivery_payload,
            commercial_payload,
            allocation_key
        )
        VALUES (
            v_order_id,
            p_prospect_id,
            v_buyer_id,
            'matched',
            1,
            0,
            0,
            0,
            0,
            '{}'::jsonb,
            jsonb_build_object(
                'allocation_version', 'v1',
                'match_score', v_match_score,
                'candidate_snapshot', v_candidate
            ),
            p_allocation_key
        );

        INSERT INTO public.commercial_events (
            event_type,
            fulfilment_order_id,
            prospect_id,
            buyer_id,
            channel,
            actor,
            amount_cents,
            cost_cents,
            margin_cents,
            payload
        )
        VALUES (
            'prospect_allocated',
            v_order_id,
            p_prospect_id,
            v_buyer_id,
            'buyer_matching',
            p_actor,
            0,
            0,
            0,
            jsonb_build_object(
                'allocation_key', p_allocation_key,
                'match_score', v_match_score,
                'candidate_snapshot', v_candidate
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
    'Phase 3D: atomically allocate one owned prospect to the first ranked buyer with live capacity.';
