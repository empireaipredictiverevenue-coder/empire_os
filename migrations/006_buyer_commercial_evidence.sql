-- Empire OS — governed buyer commercial evidence
-- Migration: 006_buyer_commercial_evidence
--
-- Adds a service-role-only evidence ledger and activation RPC.
-- This migration activates no buyers and creates no evidence rows.

CREATE TABLE IF NOT EXISTS public.buyer_commercial_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id UUID NOT NULL REFERENCES public.buyers(id) ON DELETE RESTRICT,
    evidence_type TEXT NOT NULL,
    evidence_reference TEXT NOT NULL,
    niche TEXT NOT NULL,
    metro TEXT NOT NULL,
    daily_cap INTEGER NOT NULL CHECK (daily_cap > 0),
    price_per_lead_cents INTEGER NOT NULL CHECK (price_per_lead_cents > 0),
    destination_phone TEXT,
    webhook_url TEXT,
    verification_state TEXT NOT NULL DEFAULT 'pending',
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    rejected_at TIMESTAMPTZ,
    rejected_by TEXT,
    rejection_reason TEXT,
    terms JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT buyer_commercial_evidence_type_check CHECK (
        evidence_type IN ('paid_subscription','signed_agreement','verified_payment')
    ),
    CONSTRAINT buyer_commercial_evidence_state_check CHECK (
        verification_state IN ('pending','verified','rejected','revoked')
    ),
    CONSTRAINT buyer_commercial_evidence_delivery_check CHECK (
        NULLIF(trim(COALESCE(destination_phone,'')), '') IS NOT NULL
        OR NULLIF(trim(COALESCE(webhook_url,'')), '') IS NOT NULL
    ),
    CONSTRAINT buyer_commercial_evidence_unique_ref UNIQUE (
        buyer_id, evidence_type, evidence_reference
    )
);

ALTER TABLE public.buyer_commercial_evidence ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.buyer_commercial_evidence FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.buyer_commercial_evidence TO service_role;

CREATE INDEX IF NOT EXISTS idx_buyer_commercial_evidence_buyer_state
    ON public.buyer_commercial_evidence (buyer_id, verification_state, created_at DESC);

CREATE OR REPLACE FUNCTION public.register_buyer_commercial_evidence(
    p_buyer_id UUID,
    p_evidence_type TEXT,
    p_evidence_reference TEXT,
    p_niche TEXT,
    p_metro TEXT,
    p_daily_cap INTEGER,
    p_price_per_lead_cents INTEGER,
    p_destination_phone TEXT DEFAULT NULL,
    p_webhook_url TEXT DEFAULT NULL,
    p_terms JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_id UUID;
BEGIN
    IF p_buyer_id IS NULL THEN RAISE EXCEPTION 'buyer_id is required'; END IF;
    IF p_evidence_type NOT IN ('paid_subscription','signed_agreement','verified_payment') THEN
        RAISE EXCEPTION 'unsupported evidence_type';
    END IF;
    IF NULLIF(trim(COALESCE(p_evidence_reference,'')), '') IS NULL THEN
        RAISE EXCEPTION 'evidence_reference is required';
    END IF;
    IF NULLIF(trim(COALESCE(p_niche,'')), '') IS NULL
       OR NULLIF(trim(COALESCE(p_metro,'')), '') IS NULL THEN
        RAISE EXCEPTION 'niche and metro are required';
    END IF;
    IF COALESCE(p_daily_cap,0) <= 0 OR COALESCE(p_price_per_lead_cents,0) <= 0 THEN
        RAISE EXCEPTION 'verified capacity and price are required';
    END IF;
    IF NULLIF(trim(COALESCE(p_destination_phone,'')), '') IS NULL
       AND NULLIF(trim(COALESCE(p_webhook_url,'')), '') IS NULL THEN
        RAISE EXCEPTION 'delivery destination is required';
    END IF;
    PERFORM 1 FROM public.buyers WHERE id=p_buyer_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer not found'; END IF;

    INSERT INTO public.buyer_commercial_evidence (
        buyer_id,evidence_type,evidence_reference,niche,metro,daily_cap,
        price_per_lead_cents,destination_phone,webhook_url,terms
    ) VALUES (
        p_buyer_id,p_evidence_type,trim(p_evidence_reference),trim(p_niche),trim(p_metro),
        p_daily_cap,p_price_per_lead_cents,NULLIF(trim(COALESCE(p_destination_phone,'')),''),
        NULLIF(trim(COALESCE(p_webhook_url,'')),''),COALESCE(p_terms,'{}'::jsonb)
    )
    ON CONFLICT (buyer_id,evidence_type,evidence_reference)
    DO UPDATE SET
        niche=EXCLUDED.niche,
        metro=EXCLUDED.metro,
        daily_cap=EXCLUDED.daily_cap,
        price_per_lead_cents=EXCLUDED.price_per_lead_cents,
        destination_phone=EXCLUDED.destination_phone,
        webhook_url=EXCLUDED.webhook_url,
        terms=EXCLUDED.terms,
        updated_at=now()
    WHERE public.buyer_commercial_evidence.verification_state='pending'
    RETURNING id INTO v_id;

    IF v_id IS NULL THEN
        SELECT id INTO v_id FROM public.buyer_commercial_evidence
        WHERE buyer_id=p_buyer_id AND evidence_type=p_evidence_type
          AND evidence_reference=trim(p_evidence_reference);
    END IF;
    RETURN v_id;
END;
$$;

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
BEGIN
    IF NULLIF(trim(COALESCE(p_verified_by,'')), '') IS NULL THEN
        RAISE EXCEPTION 'verified_by is required';
    END IF;
    SELECT * INTO v_e FROM public.buyer_commercial_evidence
    WHERE id=p_evidence_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'evidence not found'; END IF;
    IF v_e.verification_state = 'verified' THEN
        RETURN jsonb_build_object(
            'decision','existing_verification','evidence_id',p_evidence_id,'buyer_id',v_e.buyer_id
        );
    END IF;
    IF v_e.verification_state <> 'pending' THEN
        RAISE EXCEPTION 'evidence is not pending';
    END IF;

    SELECT * INTO v_buyer FROM public.buyers WHERE id=v_e.buyer_id;
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
        BEGIN
            v_ref := v_e.evidence_reference::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'verified_payment reference must be a payment UUID';
        END;

        PERFORM 1
          FROM public.crypto_payment_requests p
         WHERE p.id=v_ref
           AND lower(trim(COALESCE(p.customer_email,''))) = lower(trim(COALESCE(v_buyer.email,'')))
           AND lower(trim(COALESCE(p.status,''))) IN ('paid','verified','confirmed','completed')
           AND p.paid_at IS NOT NULL
           AND NULLIF(trim(COALESCE(p.transaction_signature,'')), '') IS NOT NULL;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'verified payment does not resolve to this buyer';
        END IF;
        IF COALESCE(v_e.terms->>'commercial_terms_sha256','') !~ '^[0-9a-fA-F]{64}$' THEN
            RAISE EXCEPTION 'verified payment requires commercial_terms_sha256';
        END IF;
    ELSE
        RAISE EXCEPTION 'unsupported evidence_type';
    END IF;

    UPDATE public.buyer_commercial_evidence
       SET verification_state='verified', verified_at=now(),
           verified_by=trim(p_verified_by), updated_at=now()
     WHERE id=p_evidence_id;

    RETURN jsonb_build_object(
        'decision','verified','evidence_id',p_evidence_id,'buyer_id',v_e.buyer_id
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.activate_buyer_from_evidence(
    p_evidence_id UUID,
    p_actor TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_e public.buyer_commercial_evidence%ROWTYPE;
    v_b public.buyers%ROWTYPE;
BEGIN
    IF NULLIF(trim(COALESCE(p_actor,'')), '') IS NULL THEN
        RAISE EXCEPTION 'actor is required';
    END IF;

    SELECT * INTO v_e FROM public.buyer_commercial_evidence
    WHERE id=p_evidence_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'evidence not found'; END IF;
    IF v_e.verification_state <> 'verified' OR v_e.verified_at IS NULL
       OR NULLIF(trim(COALESCE(v_e.verified_by,'')), '') IS NULL THEN
        RAISE EXCEPTION 'verified evidence is required';
    END IF;

    SELECT * INTO v_b FROM public.buyers WHERE id=v_e.buyer_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'buyer not found'; END IF;

    IF lower(trim(COALESCE(v_b.commercial_activation_state,'')))='activated' THEN
        IF COALESCE(v_b.commercial_terms_source,'')=v_e.evidence_type
           AND COALESCE(v_b.commercial_terms_reference,'')=v_e.evidence_reference THEN
            RETURN jsonb_build_object(
                'decision','existing_activation','buyer_id',v_e.buyer_id,'evidence_id',v_e.id,
                'niche',v_b.niche,'metro',v_b.metro,'daily_cap',v_b.daily_cap
            );
        END IF;
        RAISE EXCEPTION 'buyer already activated from different evidence';
    END IF;

    UPDATE public.buyers
       SET niche=v_e.niche,
           metro=v_e.metro,
           daily_cap=v_e.daily_cap,
           calls_today=LEAST(COALESCE(calls_today,0),v_e.daily_cap),
           per_lead_rate=(v_e.price_per_lead_cents::numeric / 100.0),
           destination_phone=v_e.destination_phone,
           webhook_url=v_e.webhook_url,
           is_active=TRUE,
           status='active',
           commercial_activation_state='activated',
           commercial_activated_at=now(),
           commercial_terms_source=v_e.evidence_type,
           commercial_terms_reference=v_e.evidence_reference,
           commercial_terms_verified_at=v_e.verified_at,
           capacity_verified_at=v_e.verified_at,
           delivery_verified_at=v_e.verified_at,
           reviewed_at=COALESCE(reviewed_at,v_e.verified_at),
           notes=concat_ws(E'\n',NULLIF(notes,''),
               'Commercial activation evidence: ' || v_e.evidence_type || ':' || v_e.evidence_reference),
           updated_at=now()
     WHERE id=v_e.buyer_id;

    INSERT INTO public.commercial_events (
        event_type,buyer_id,channel,actor,amount_cents,cost_cents,margin_cents,payload,idempotency_key
    ) VALUES (
        'buyer_commercially_activated',v_e.buyer_id,'buyer_activation',trim(p_actor),
        0,0,0,
        jsonb_build_object(
            'evidence_id',v_e.id,'evidence_type',v_e.evidence_type,
            'evidence_reference',v_e.evidence_reference,'niche',v_e.niche,
            'metro',v_e.metro,'daily_cap',v_e.daily_cap,
            'price_per_lead_cents',v_e.price_per_lead_cents
        ),
        'buyer:' || v_e.buyer_id::text || ':activated:' || v_e.id::text
    )
    ON CONFLICT (idempotency_key) DO NOTHING;

    RETURN jsonb_build_object(
        'decision','activated','buyer_id',v_e.buyer_id,'evidence_id',v_e.id,
        'niche',v_e.niche,'metro',v_e.metro,'daily_cap',v_e.daily_cap
    );
END;
$$;

REVOKE ALL ON FUNCTION public.register_buyer_commercial_evidence(
    UUID,TEXT,TEXT,TEXT,TEXT,INTEGER,INTEGER,TEXT,TEXT,JSONB
) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.verify_buyer_commercial_evidence(UUID,TEXT)
    FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.activate_buyer_from_evidence(UUID,TEXT)
    FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.register_buyer_commercial_evidence(
    UUID,TEXT,TEXT,TEXT,TEXT,INTEGER,INTEGER,TEXT,TEXT,JSONB
) TO service_role;
GRANT EXECUTE ON FUNCTION public.verify_buyer_commercial_evidence(UUID,TEXT)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.activate_buyer_from_evidence(UUID,TEXT)
    TO service_role;
