-- Empire BSC USDT smart-contract escrow evidence model.
-- Forward-only, fail-closed, creates no escrow/payment rows and recognizes no revenue.
BEGIN;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_escrow_verifier') THEN
        CREATE ROLE empire_escrow_verifier NOLOGIN NOINHERIT;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_escrow_verifier;
REVOKE empire_escrow_verifier FROM service_role;

ALTER TABLE public.bsc_payment_requests
    ADD COLUMN settlement_mode text NOT NULL DEFAULT 'direct';
ALTER TABLE public.bsc_payment_requests
    ADD CONSTRAINT bsc_payment_requests_settlement_mode_check
    CHECK (settlement_mode IN ('direct','escrow'));

COMMENT ON COLUMN public.bsc_payment_requests.settlement_mode IS
    'Explicit payment rail: direct treasury transfer or governed smart-contract escrow.';
CREATE TABLE public.bsc_escrow_agreements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL UNIQUE REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
    escrow_id text NOT NULL UNIQUE CHECK (escrow_id ~ '^0x[0-9a-f]{64}$'),
    contract_address text NOT NULL CHECK (contract_address ~ '^0x[0-9a-f]{40}$'),
    beneficiary_address text NOT NULL CHECK (beneficiary_address ~ '^0x[0-9a-f]{40}$'),
    runtime_sha256 text NOT NULL CHECK (runtime_sha256 ~ '^[0-9a-f]{64}$'),
    creation_transaction_hash text NOT NULL UNIQUE CHECK (creation_transaction_hash ~ '^0x[0-9a-f]{64}$'),
    creation_block_hash text NOT NULL CHECK (creation_block_hash ~ '^0x[0-9a-f]{64}$'),
    creation_block_number bigint NOT NULL CHECK (creation_block_number > 0),
    payer_address text NOT NULL CHECK (payer_address ~ '^0x[0-9a-f]{40}$'),
    amount_raw numeric NOT NULL CHECK (amount_raw > 0 AND amount_raw = trunc(amount_raw)),
    commercial_terms_sha256 text NOT NULL CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$'),
    funding_deadline timestamptz NOT NULL,
    refund_after timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (
        status IN ('open','funded','disputed','resolution_pending','released','refunded','cancelled')
    ),
    creation_verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (funding_deadline < refund_after)
);
CREATE TABLE public.bsc_escrow_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agreement_id uuid NOT NULL REFERENCES public.bsc_escrow_agreements(id) ON DELETE RESTRICT,
    action text NOT NULL CHECK (action IN ('funded','released','refunded')),
    transaction_hash text NOT NULL UNIQUE CHECK (transaction_hash ~ '^0x[0-9a-f]{64}$'),
    block_hash text NOT NULL CHECK (block_hash ~ '^0x[0-9a-f]{64}$'),
    block_number bigint NOT NULL CHECK (block_number > 0),
    amount_raw numeric NOT NULL CHECK (amount_raw > 0 AND amount_raw = trunc(amount_raw)),
    party_address text NOT NULL CHECK (party_address ~ '^0x[0-9a-f]{40}$'),
    confirmations integer NOT NULL CHECK (confirmations >= 12),
    chain_timestamp timestamptz NOT NULL,
    verified_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(agreement_id, action)
);

CREATE INDEX bsc_escrow_evidence_agreement_idx
    ON public.bsc_escrow_evidence(agreement_id, recorded_at);

ALTER TABLE public.bsc_escrow_agreements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsc_escrow_evidence ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bsc_escrow_agreements, public.bsc_escrow_evidence
    FROM PUBLIC, anon, authenticated, service_role, empire_escrow_verifier;
GRANT SELECT ON public.bsc_escrow_agreements, public.bsc_escrow_evidence TO service_role;
CREATE FUNCTION public.guard_bsc_escrow_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'escrow evidence is append-only';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_bsc_escrow_evidence
BEFORE UPDATE OR DELETE ON public.bsc_escrow_evidence
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_escrow_evidence();

CREATE FUNCTION public.propose_bsc_escrow_request(
    p_fulfilment_order_id uuid,
    p_amount_usdt numeric,
    p_payer_address text,
    p_beneficiary_address text,
    p_min_block_number bigint,
    p_expires_at timestamptz,
    p_idempotency_key text,
    p_actor text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    o public.fulfilment_orders%ROWTYPE;
    r public.bsc_payment_requests%ROWTYPE;
    v_terms text;
    v_payer text := lower(trim(COALESCE(p_payer_address,'')));
    v_beneficiary text := lower(trim(COALESCE(p_beneficiary_address,'')));
    v_key text := trim(COALESCE(p_idempotency_key,''));
    v_actor text := trim(COALESCE(p_actor,''));
BEGIN
    IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'fulfilment_order_id is required'; END IF;
    IF p_amount_usdt IS NULL OR p_amount_usdt <= 0 THEN RAISE EXCEPTION 'positive amount_usdt is required'; END IF;
    IF v_payer !~ '^0x[0-9a-f]{40}$' OR v_beneficiary !~ '^0x[0-9a-f]{40}$' THEN
        RAISE EXCEPTION 'canonical BSC payer and beneficiary addresses are required';
    END IF;
    IF v_payer = v_beneficiary THEN RAISE EXCEPTION 'payer and beneficiary must differ'; END IF;
    IF COALESCE(p_min_block_number,0) <= 0 THEN RAISE EXCEPTION 'positive min_block_number is required'; END IF;
    IF length(v_key) < 8 OR length(v_key) > 128 THEN RAISE EXCEPTION 'idempotency_key length is invalid'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'actor is required'; END IF;
    IF p_expires_at IS NULL OR p_expires_at < clock_timestamp() + interval '10 minutes'
       OR p_expires_at > clock_timestamp() + interval '7 days' THEN
        RAISE EXCEPTION 'expires_at must be 10 minutes to 7 days in the future';
    END IF;
    SELECT * INTO o FROM public.fulfilment_orders
     WHERE id=p_fulfilment_order_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    IF o.buyer_id IS NULL OR o.state NOT IN ('accepted','invoiced','delivered','confirmed') THEN
        RAISE EXCEPTION 'fulfilment order is not payment-eligible';
    END IF;
    v_terms := lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''));
    IF v_terms !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'fulfilment order requires commercial_terms_sha256';
    END IF;

    SELECT * INTO r FROM public.bsc_payment_requests
     WHERE idempotency_key=v_key FOR UPDATE;
    IF FOUND THEN
        IF r.settlement_mode <> 'escrow'
           OR r.fulfilment_order_id IS DISTINCT FROM p_fulfilment_order_id
           OR r.buyer_id IS DISTINCT FROM o.buyer_id
           OR r.amount_usdt IS DISTINCT FROM p_amount_usdt
           OR r.payer_address IS DISTINCT FROM v_payer
           OR r.treasury_address IS DISTINCT FROM v_beneficiary
           OR r.commercial_terms_sha256 IS DISTINCT FROM v_terms
           OR r.min_block_number IS DISTINCT FROM p_min_block_number
           OR r.expires_at IS DISTINCT FROM p_expires_at THEN
            RAISE EXCEPTION 'idempotency_key already belongs to different escrow terms';
        END IF;
        RETURN jsonb_build_object('decision','existing_request','request_id',r.id,
            'status',r.status,'settlement_mode','escrow','actual_revenue',false);
    END IF;
    PERFORM 1 FROM public.bsc_payment_requests
     WHERE fulfilment_order_id=p_fulfilment_order_id
       AND status IN ('pending','approved');
    IF FOUND THEN RAISE EXCEPTION 'fulfilment order already has an open payment request'; END IF;
    INSERT INTO public.bsc_payment_requests (
        buyer_id, fulfilment_order_id, amount_usdt, payer_address, treasury_address,
        commercial_terms_sha256, min_block_number, status, expires_at,
        idempotency_key, settlement_mode
    ) VALUES (
        o.buyer_id, p_fulfilment_order_id, p_amount_usdt, v_payer, v_beneficiary,
        v_terms, p_min_block_number, 'pending', p_expires_at, v_key, 'escrow'
    ) RETURNING * INTO r;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'proposed',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object(
            'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
            'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
            'beneficiary_address',r.treasury_address,'commercial_terms_sha256',v_terms,
            'min_block_number',r.min_block_number,'expires_at',r.expires_at,
            'idempotency_key',v_key,'settlement_mode','escrow','actual_revenue',false
        ));
    RETURN jsonb_build_object('decision','proposed','request_id',r.id,
        'status',r.status,'settlement_mode','escrow','actual_revenue',false);
END;
$$;
CREATE FUNCTION public.record_bsc_escrow_creation(
    p_request_id uuid, p_evidence jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    a public.bsc_escrow_agreements%ROWTYPE;
    v_expected_id text;
    v_verified_at timestamptz;
    v_chain_time timestamptz;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF r.settlement_mode <> 'escrow' THEN RAISE EXCEPTION 'escrow payment request required'; END IF;
    IF r.status <> 'approved' OR r.approved_at IS NULL OR r.expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'current human-approved escrow request required';
    END IF;
    IF (p_evidence->>'verified') IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'verified escrow creation proof required';
    END IF;
    v_expected_id := '0x' || lpad(replace(r.id::text,'-',''),64,'0');
    IF lower(COALESCE(p_evidence->>'escrow_id','')) IS DISTINCT FROM v_expected_id THEN
        RAISE EXCEPTION 'escrow id does not match payment request';
    END IF;
    IF lower(COALESCE(p_evidence->>'payer_address','')) IS DISTINCT FROM r.payer_address
       OR (p_evidence->>'amount_raw')::numeric IS DISTINCT FROM r.amount_usdt * 1000000000000000000
       OR lower(COALESCE(p_evidence->>'terms_hash','')) IS DISTINCT FROM ('0x' || r.commercial_terms_sha256) THEN
        RAISE EXCEPTION 'escrow creation proof does not match approved terms';
    END IF;
    IF lower(COALESCE(p_evidence->>'beneficiary_address','')) IS DISTINCT FROM r.treasury_address THEN
        RAISE EXCEPTION 'escrow beneficiary does not match approved request';
    END IF;
    IF lower(COALESCE(p_evidence->>'contract_address','')) !~ '^0x[0-9a-f]{40}$'
       OR lower(COALESCE(p_evidence->>'runtime_sha256','')) !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'canonical escrow contract identity is required';
    END IF;
    v_verified_at := (p_evidence->>'verified_at')::timestamptz;
    v_chain_time := to_timestamp((p_evidence->>'block_timestamp')::bigint);
    IF v_verified_at < clock_timestamp() - interval '5 minutes'
       OR v_verified_at > clock_timestamp() + interval '5 seconds' THEN
        RAISE EXCEPTION 'fresh escrow creation verification required';
    END IF;
    IF v_chain_time < r.approved_at - interval '5 minutes' OR v_chain_time >= r.expires_at THEN
        RAISE EXCEPTION 'escrow creation is outside approved request window';
    END IF;
    IF to_timestamp((p_evidence->>'funding_deadline')::bigint) <= v_chain_time
       OR to_timestamp((p_evidence->>'funding_deadline')::bigint) > r.expires_at
       OR to_timestamp((p_evidence->>'refund_after')::bigint) <= to_timestamp((p_evidence->>'funding_deadline')::bigint)
       OR to_timestamp((p_evidence->>'refund_after')::bigint) > v_chain_time + interval '365 days' THEN
        RAISE EXCEPTION 'escrow deadlines exceed approved bounds';
    END IF;
    SELECT * INTO a FROM public.bsc_escrow_agreements WHERE request_id=r.id;
    IF FOUND THEN
        RETURN jsonb_build_object('decision','already_recorded','agreement_id',a.id,
            'request_id',r.id,'status',a.status,'actual_revenue',false);
    END IF;

    INSERT INTO public.bsc_escrow_agreements(
        request_id,escrow_id,contract_address,beneficiary_address,runtime_sha256,
        creation_transaction_hash,creation_block_hash,creation_block_number,
        payer_address,amount_raw,commercial_terms_sha256,
        funding_deadline,refund_after,creation_verified_at
    ) VALUES (
        r.id,v_expected_id,lower(p_evidence->>'contract_address'),r.treasury_address,
        lower(p_evidence->>'runtime_sha256'),lower(p_evidence->>'transaction_hash'),
        lower(p_evidence->>'block_hash'),(p_evidence->>'block_number')::bigint,
        r.payer_address,(p_evidence->>'amount_raw')::numeric,r.commercial_terms_sha256,
        to_timestamp((p_evidence->>'funding_deadline')::bigint),
        to_timestamp((p_evidence->>'refund_after')::bigint),v_verified_at
    ) RETURNING * INTO a;
    RETURN jsonb_build_object('decision','recorded','agreement_id',a.id,
        'request_id',r.id,'status',a.status,'actual_revenue',false);
END;
$$;
CREATE FUNCTION public.record_bsc_escrow_lifecycle(
    p_agreement_id uuid, p_action text, p_evidence jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    a public.bsc_escrow_agreements%ROWTYPE;
    e public.bsc_escrow_evidence%ROWTYPE;
    v_action text := lower(trim(COALESCE(p_action,'')));
    v_verified_at timestamptz;
    v_chain_time timestamptz;
    v_next text;
BEGIN
    IF v_action NOT IN ('funded','released','refunded') THEN
        RAISE EXCEPTION 'unsupported escrow lifecycle action';
    END IF;
    SELECT * INTO a FROM public.bsc_escrow_agreements WHERE id=p_agreement_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'escrow agreement missing'; END IF;
    IF (p_evidence->>'verified') IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'verified escrow lifecycle proof required';
    END IF;
    IF lower(COALESCE(p_evidence->>'escrow_id','')) IS DISTINCT FROM a.escrow_id
       OR (p_evidence->>'amount_raw')::numeric IS DISTINCT FROM a.amount_raw THEN
        RAISE EXCEPTION 'escrow lifecycle proof does not match agreement';
    END IF;
    IF v_action='funded' THEN
        IF a.status <> 'open' THEN RAISE EXCEPTION 'open escrow agreement required for funding'; END IF;
        IF lower(COALESCE(p_evidence->>'party_address','')) IS DISTINCT FROM a.payer_address THEN
            RAISE EXCEPTION 'escrow funding party mismatch';
        END IF;
        v_next := 'funded';
    ELSIF v_action='released' THEN
        IF a.status <> 'funded' THEN RAISE EXCEPTION 'funded escrow agreement required for release'; END IF;
        IF lower(COALESCE(p_evidence->>'party_address','')) IS DISTINCT FROM a.beneficiary_address THEN
            RAISE EXCEPTION 'escrow release beneficiary mismatch';
        END IF;
        v_next := 'released';
    ELSE
        IF a.status <> 'funded' THEN RAISE EXCEPTION 'funded escrow agreement required for refund'; END IF;
        IF lower(COALESCE(p_evidence->>'party_address','')) IS DISTINCT FROM a.payer_address THEN
            RAISE EXCEPTION 'escrow refund payer mismatch';
        END IF;
        v_next := 'refunded';
    END IF;
    v_verified_at := (p_evidence->>'verified_at')::timestamptz;
    v_chain_time := to_timestamp((p_evidence->>'block_timestamp')::bigint);
    IF v_verified_at < clock_timestamp() - interval '5 minutes'
       OR v_verified_at > clock_timestamp() + interval '5 seconds' THEN
        RAISE EXCEPTION 'fresh escrow lifecycle verification required';
    END IF;
    IF (p_evidence->>'confirmations')::integer < 12 THEN
        RAISE EXCEPTION 'at least 12 escrow confirmations are required';
    END IF;
    IF lower(COALESCE(p_evidence->>'transaction_hash','')) !~ '^0x[0-9a-f]{64}$'
       OR lower(COALESCE(p_evidence->>'block_hash','')) !~ '^0x[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'canonical escrow transaction and block hashes are required';
    END IF;

    SELECT * INTO e FROM public.bsc_escrow_evidence
     WHERE agreement_id=a.id AND action=v_action;
    IF FOUND THEN
        IF e.transaction_hash IS DISTINCT FROM lower(p_evidence->>'transaction_hash')
           OR e.block_hash IS DISTINCT FROM lower(p_evidence->>'block_hash')
           OR e.block_number IS DISTINCT FROM (p_evidence->>'block_number')::bigint
           OR e.amount_raw IS DISTINCT FROM (p_evidence->>'amount_raw')::numeric
           OR e.party_address IS DISTINCT FROM lower(p_evidence->>'party_address') THEN
            RAISE EXCEPTION 'escrow action already recorded with different evidence';
        END IF;
        RETURN jsonb_build_object('decision','already_recorded','evidence_id',e.id,
            'agreement_id',a.id,'action',v_action,'status',a.status,'actual_revenue',false);
    END IF;

    INSERT INTO public.bsc_escrow_evidence(
        agreement_id,action,transaction_hash,block_hash,block_number,
        amount_raw,party_address,confirmations,chain_timestamp,verified_at
    ) VALUES (
        a.id,v_action,lower(p_evidence->>'transaction_hash'),
        lower(p_evidence->>'block_hash'),(p_evidence->>'block_number')::bigint,
        (p_evidence->>'amount_raw')::numeric,lower(p_evidence->>'party_address'),
        (p_evidence->>'confirmations')::integer,v_chain_time,v_verified_at
    ) RETURNING * INTO e;

    UPDATE public.bsc_escrow_agreements
       SET status=v_next, updated_at=clock_timestamp()
     WHERE id=a.id
     RETURNING * INTO a;

    RETURN jsonb_build_object(
        'decision','recorded','evidence_id',e.id,'agreement_id',a.id,
        'action',v_action,'status',a.status,
        'revenue_eligible',(v_action='released'),'actual_revenue',false
    );
END;
$$;

CREATE FUNCTION public.guard_direct_bsc_payment_mode()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE r public.bsc_payment_requests%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=NEW.request_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF r.settlement_mode <> 'direct' THEN
        RAISE EXCEPTION 'direct payment evidence cannot satisfy an escrow request';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_direct_bsc_payment_mode
BEFORE INSERT ON public.bsc_payment_evidence
FOR EACH ROW EXECUTE FUNCTION public.guard_direct_bsc_payment_mode();

REVOKE ALL ON FUNCTION public.guard_bsc_escrow_evidence()
    FROM PUBLIC,anon,authenticated,service_role,empire_escrow_verifier;
REVOKE ALL ON FUNCTION public.propose_bsc_escrow_request(
    uuid,numeric,text,text,bigint,timestamptz,text,text
) FROM PUBLIC,anon,authenticated,empire_payment_approver,empire_bsc_verifier,empire_escrow_verifier;
REVOKE ALL ON FUNCTION public.record_bsc_escrow_creation(uuid,jsonb)
    FROM PUBLIC,anon,authenticated,service_role,empire_payment_approver,empire_bsc_verifier;
REVOKE ALL ON FUNCTION public.record_bsc_escrow_lifecycle(uuid,text,jsonb)
    FROM PUBLIC,anon,authenticated,service_role,empire_payment_approver,empire_bsc_verifier;
REVOKE ALL ON FUNCTION public.guard_direct_bsc_payment_mode()
    FROM PUBLIC,anon,authenticated,service_role,empire_payment_approver,
         empire_bsc_verifier,empire_escrow_verifier;

GRANT EXECUTE ON FUNCTION public.propose_bsc_escrow_request(
    uuid,numeric,text,text,bigint,timestamptz,text,text
) TO service_role;
GRANT EXECUTE ON FUNCTION public.record_bsc_escrow_creation(uuid,jsonb)
    TO empire_escrow_verifier;
GRANT EXECUTE ON FUNCTION public.record_bsc_escrow_lifecycle(uuid,text,jsonb)
    TO empire_escrow_verifier;
CREATE FUNCTION public.get_bsc_escrow_request_review(p_request_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    a public.bsc_escrow_agreements%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    IF r.settlement_mode <> 'escrow' THEN RAISE EXCEPTION 'escrow payment request required'; END IF;
    SELECT * INTO a FROM public.bsc_escrow_agreements WHERE request_id=r.id;
    RETURN jsonb_build_object(
        'request_id',r.id,'status',r.status,'settlement_mode',r.settlement_mode,
        'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
        'beneficiary_address',r.treasury_address,
        'commercial_terms_sha256',r.commercial_terms_sha256,
        'approved_by',r.approved_by,'approved_at',r.approved_at,'expires_at',r.expires_at,
        'agreement_id',a.id,'escrow_id',a.escrow_id,'contract_address',a.contract_address,
        'runtime_sha256',a.runtime_sha256,'escrow_status',a.status,
        'funding_deadline',a.funding_deadline,'refund_after',a.refund_after,
        'actual_revenue',false
    );
END;
$$;
REVOKE ALL ON FUNCTION public.get_bsc_escrow_request_review(uuid)
    FROM PUBLIC,anon,authenticated,service_role,empire_payment_approver,empire_bsc_verifier;
GRANT EXECUTE ON FUNCTION public.get_bsc_escrow_request_review(uuid) TO empire_escrow_verifier;

COMMENT ON TABLE public.bsc_escrow_agreements IS
    'Verified BSC USDT escrow creation bound to an approved Empire payment request.';
COMMENT ON TABLE public.bsc_escrow_evidence IS
    'Append-only funded/released/refunded escrow evidence. Funding is never revenue.';
COMMENT ON FUNCTION public.propose_bsc_escrow_request(uuid,numeric,text,text,bigint,timestamptz,text,text) IS
    'Service proposal for escrow-mode BSC USDT payment. Human approval remains separate.';
COMMENT ON FUNCTION public.record_bsc_escrow_creation(uuid,jsonb) IS
    'Dedicated escrow verifier boundary for canonical on-chain EscrowCreated evidence.';
COMMENT ON FUNCTION public.record_bsc_escrow_lifecycle(uuid,text,jsonb) IS
    'Dedicated escrow verifier boundary for canonical funded/released/refunded evidence.';

COMMIT;
