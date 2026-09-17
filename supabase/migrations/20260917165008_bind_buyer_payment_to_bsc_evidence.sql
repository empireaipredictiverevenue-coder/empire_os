-- Bind buyer commercial verification to canonical BSC USDT evidence.
-- Forward-only replacement for the verified_payment branch from migration 006.
-- Does not create payment requests, record chain evidence, or activate buyers.
BEGIN;

CREATE OR REPLACE FUNCTION public.verify_buyer_commercial_evidence(
    p_evidence_id UUID,
    p_verified_by TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_e public.buyer_commercial_evidence%ROWTYPE;
    v_ref UUID;
    v_buyer public.buyers%ROWTYPE;
    v_terms_hash TEXT;
BEGIN
    IF NULLIF(trim(COALESCE(p_verified_by,'')), '') IS NULL THEN
        RAISE EXCEPTION 'verified_by is required';
    END IF;

    SELECT * INTO v_e
      FROM public.buyer_commercial_evidence
     WHERE id=p_evidence_id
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'evidence not found'; END IF;

    IF v_e.verification_state = 'verified' THEN
        RETURN jsonb_build_object(
            'decision','existing_verification',
            'evidence_id',p_evidence_id,
            'buyer_id',v_e.buyer_id
        );
    END IF;
    IF v_e.verification_state <> 'pending' THEN
        RAISE EXCEPTION 'evidence is not pending';
    END IF;

    SELECT * INTO v_buyer
      FROM public.buyers
     WHERE id=v_e.buyer_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer not found'; END IF;

    IF v_e.evidence_type = 'paid_subscription' THEN
        BEGIN
            v_ref := v_e.evidence_reference::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'paid_subscription reference must be a subscription UUID';
        END;

        PERFORM 1
          FROM public.buyer_subscriptions s
         WHERE s.id=v_ref
           AND s.buyer_id=v_e.buyer_id
           AND COALESCE(s.active,FALSE)=TRUE
           AND lower(trim(COALESCE(s.status,'')))='active'
           AND COALESCE(s.max_leads_per_day,0)=v_e.daily_cap
           AND COALESCE(s.price_per_lead_cents,0)=v_e.price_per_lead_cents
           AND (s.period_end IS NULL OR s.period_end > now());
        IF NOT FOUND THEN
            RAISE EXCEPTION 'active buyer subscription does not verify these terms';
        END IF;

    ELSIF v_e.evidence_type = 'signed_agreement' THEN
        IF COALESCE(v_e.terms->>'agreement_sha256','') !~ '^[0-9a-fA-F]{64}$' THEN
            RAISE EXCEPTION 'signed agreement requires agreement_sha256';
        END IF;
        IF NULLIF(trim(COALESCE(v_e.terms->>'agreement_effective_at','')), '') IS NULL THEN
            RAISE EXCEPTION 'signed agreement requires agreement_effective_at';
        END IF;

    ELSIF v_e.evidence_type = 'verified_payment' THEN
        v_terms_hash := lower(COALESCE(v_e.terms->>'commercial_terms_sha256',''));
        IF v_terms_hash !~ '^[0-9a-f]{64}$' THEN
            RAISE EXCEPTION 'verified payment requires commercial_terms_sha256';
        END IF;

        BEGIN
            v_ref := v_e.evidence_reference::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'verified_payment reference must be a BSC payment evidence UUID';
        END;

        PERFORM 1
          FROM public.bsc_payment_evidence pe
          JOIN public.bsc_payment_requests pr
            ON pr.id=pe.request_id
          JOIN public.fulfilment_orders o
            ON o.id=pe.fulfilment_order_id
         WHERE pe.id=v_ref
           AND pr.buyer_id=v_e.buyer_id
           AND o.buyer_id=v_e.buyer_id
           AND pr.fulfilment_order_id=pe.fulfilment_order_id
           AND pr.status='approved'
           AND pr.approved_at IS NOT NULL
           AND NULLIF(trim(COALESCE(pr.approved_by,'')), '') IS NOT NULL
           AND pr.approved_at <= pe.verified_at
           AND pe.verified_at < pr.expires_at
           AND pe.commercial_terms_sha256=v_terms_hash
           AND pr.commercial_terms_sha256=v_terms_hash
           AND lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''))=v_terms_hash
           AND pe.sender_address=pr.payer_address
           AND pe.treasury_address=pr.treasury_address
           AND pe.amount_raw >= pr.amount_usdt * 1000000000000000000
           AND pe.block_number >= pr.min_block_number
           AND pe.chain_id=56
           AND pe.token_contract='0x55d398326f99059ff775485246999027b3197955'
           AND pe.confirmations >= 12;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'verified BSC payment evidence does not resolve to this buyer and terms';
        END IF;
    ELSE
        RAISE EXCEPTION 'unsupported evidence_type';
    END IF;

    UPDATE public.buyer_commercial_evidence
       SET verification_state='verified',
           verified_at=now(),
           verified_by=trim(p_verified_by),
           updated_at=now()
     WHERE id=p_evidence_id;

    RETURN jsonb_build_object(
        'decision','verified',
        'evidence_id',p_evidence_id,
        'buyer_id',v_e.buyer_id
    );
END;
$$;

REVOKE ALL ON FUNCTION public.verify_buyer_commercial_evidence(UUID,TEXT)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.verify_buyer_commercial_evidence(UUID,TEXT)
    TO service_role;

COMMENT ON FUNCTION public.verify_buyer_commercial_evidence(UUID,TEXT) IS
    'Governed commercial evidence verification. verified_payment requires canonical BSC USDT evidence.';

COMMIT;
