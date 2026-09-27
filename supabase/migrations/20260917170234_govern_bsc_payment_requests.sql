-- Govern BSC payment requests with separated proposal, approval, and verification roles.
-- Creates no payment requests/evidence and activates no buyers. OBSERVE remains unchanged.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_payment_approver') THEN
        CREATE ROLE empire_payment_approver NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_bsc_verifier') THEN
        CREATE ROLE empire_bsc_verifier NOLOGIN NOINHERIT;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO empire_payment_approver, empire_bsc_verifier;
REVOKE empire_payment_approver FROM service_role;
REVOKE empire_bsc_verifier FROM service_role;

ALTER TABLE public.bsc_payment_requests
    ADD COLUMN IF NOT EXISTS idempotency_key text;
ALTER TABLE public.bsc_payment_requests
    ADD CONSTRAINT bsc_payment_requests_idempotency_key_check
    CHECK (idempotency_key IS NULL OR length(trim(idempotency_key)) BETWEEN 8 AND 128);
CREATE UNIQUE INDEX bsc_payment_requests_idempotency_key_uidx
    ON public.bsc_payment_requests(idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX bsc_payment_requests_one_open_order_uidx
    ON public.bsc_payment_requests(fulfilment_order_id)
    WHERE status IN ('pending','approved');
CREATE TABLE public.bsc_payment_request_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
    event_type text NOT NULL CHECK (
        event_type IN ('proposed','approved','cancelled','expired','evidence_recorded')
    ),
    actor text NOT NULL CHECK (length(trim(actor)) BETWEEN 1 AND 200),
    db_role text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX bsc_payment_request_events_request_idx
    ON public.bsc_payment_request_events(request_id, created_at);
ALTER TABLE public.bsc_payment_request_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bsc_payment_request_events
    FROM PUBLIC, anon, authenticated, service_role, empire_payment_approver, empire_bsc_verifier;
GRANT SELECT ON public.bsc_payment_request_events TO service_role;

CREATE FUNCTION public.guard_bsc_payment_request_event()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment request audit events are append-only';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_bsc_payment_request_event
BEFORE UPDATE OR DELETE ON public.bsc_payment_request_events
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_payment_request_event();
CREATE FUNCTION public.propose_bsc_payment_request(
    p_fulfilment_order_id uuid,
    p_amount_usdt numeric,
    p_payer_address text,
    p_treasury_address text,
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
    v_treasury text := lower(trim(COALESCE(p_treasury_address,'')));
    v_key text := trim(COALESCE(p_idempotency_key,''));
    v_actor text := trim(COALESCE(p_actor,''));
BEGIN
    IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'fulfilment_order_id is required'; END IF;
    IF p_amount_usdt IS NULL OR p_amount_usdt <= 0 THEN RAISE EXCEPTION 'positive amount_usdt is required'; END IF;
    IF v_payer !~ '^0x[0-9a-f]{40}$' OR v_treasury !~ '^0x[0-9a-f]{40}$' THEN
        RAISE EXCEPTION 'canonical BSC payer and treasury addresses are required';
    END IF;
    IF v_payer = v_treasury THEN RAISE EXCEPTION 'payer and treasury must differ'; END IF;
    IF COALESCE(p_min_block_number,0) <= 0 THEN RAISE EXCEPTION 'positive min_block_number is required'; END IF;
    IF length(v_key) < 8 OR length(v_key) > 128 THEN RAISE EXCEPTION 'idempotency_key length is invalid'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'actor is required'; END IF;
    IF p_expires_at IS NULL OR p_expires_at < clock_timestamp() + interval '10 minutes'
       OR p_expires_at > clock_timestamp() + interval '7 days' THEN
        RAISE EXCEPTION 'expires_at must be 10 minutes to 7 days in the future';
    END IF;
    SELECT * INTO o
      FROM public.fulfilment_orders
     WHERE id=p_fulfilment_order_id
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    IF o.buyer_id IS NULL THEN RAISE EXCEPTION 'fulfilment order buyer is required'; END IF;
    IF o.state IS NULL OR o.state NOT IN ('accepted','invoiced','delivered','confirmed') THEN
        RAISE EXCEPTION 'fulfilment order is not payment-eligible';
    END IF;
    v_terms := lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''));
    IF v_terms !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'fulfilment order requires commercial_terms_sha256';
    END IF;

    SELECT * INTO r
      FROM public.bsc_payment_requests
     WHERE idempotency_key=v_key
     FOR UPDATE;
    IF FOUND THEN
        IF r.fulfilment_order_id IS DISTINCT FROM p_fulfilment_order_id
           OR r.buyer_id IS DISTINCT FROM o.buyer_id
           OR r.amount_usdt IS DISTINCT FROM p_amount_usdt
           OR r.payer_address IS DISTINCT FROM v_payer
           OR r.treasury_address IS DISTINCT FROM v_treasury
           OR r.commercial_terms_sha256 IS DISTINCT FROM v_terms
           OR r.min_block_number IS DISTINCT FROM p_min_block_number
           OR r.expires_at IS DISTINCT FROM p_expires_at THEN
            RAISE EXCEPTION 'idempotency_key already belongs to different payment terms';
        END IF;
        RETURN jsonb_build_object(
            'decision','existing_request','request_id',r.id,
            'status',r.status,'actual_revenue',false
        );
    END IF;
    SELECT * INTO r
      FROM public.bsc_payment_requests
     WHERE fulfilment_order_id=p_fulfilment_order_id
       AND status IN ('pending','approved')
     FOR UPDATE;
    IF FOUND THEN
        RAISE EXCEPTION 'fulfilment order already has an open payment request';
    END IF;

    INSERT INTO public.bsc_payment_requests (
        buyer_id, fulfilment_order_id, amount_usdt, payer_address, treasury_address,
        commercial_terms_sha256, min_block_number, status, expires_at, idempotency_key
    ) VALUES (
        o.buyer_id, p_fulfilment_order_id, p_amount_usdt, v_payer, v_treasury,
        v_terms, p_min_block_number, 'pending', p_expires_at, v_key
    ) RETURNING * INTO r;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'proposed',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object(
            'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
            'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
            'treasury_address',r.treasury_address,'commercial_terms_sha256',v_terms,
            'min_block_number',r.min_block_number,'expires_at',r.expires_at,
            'idempotency_key',v_key,'actual_revenue',false
        ));
    RETURN jsonb_build_object(
        'decision','proposed','request_id',r.id,'status',r.status,
        'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
        'actual_revenue',false
    );
END;
$$;
CREATE FUNCTION public.approve_bsc_payment_request(
    p_request_id uuid,
    p_approved_by text,
    p_approval_note text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    o public.fulfilment_orders%ROWTYPE;
    v_actor text := trim(COALESCE(p_approved_by,''));
    v_note text := trim(COALESCE(p_approval_note,''));
    v_terms text;
BEGIN
    IF p_request_id IS NULL THEN RAISE EXCEPTION 'request_id is required'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'approved_by is required'; END IF;
    IF length(v_note) < 4 OR length(v_note) > 1000 THEN RAISE EXCEPTION 'approval_note is required'; END IF;

    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    IF r.status='approved' THEN
        RETURN jsonb_build_object(
            'decision','existing_approval','request_id',r.id,
            'approved_by',r.approved_by,'approved_at',r.approved_at,
            'actual_revenue',false
        );
    END IF;
    IF r.status NOT IN ('pending') THEN RAISE EXCEPTION 'pending payment request required'; END IF;
    IF r.expires_at <= clock_timestamp() THEN
        UPDATE public.bsc_payment_requests SET status='expired' WHERE id=r.id;
        INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
        VALUES (r.id,'expired',v_actor,
            COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
            jsonb_build_object('reason','expired before human approval','actual_revenue',false));
        RETURN jsonb_build_object('decision','expired','request_id',r.id,'actual_revenue',false);
    END IF;
    SELECT * INTO o
      FROM public.fulfilment_orders
     WHERE id=r.fulfilment_order_id
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    v_terms := lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''));
    IF o.buyer_id IS DISTINCT FROM r.buyer_id
       OR o.state IS NULL OR o.state NOT IN ('accepted','invoiced','delivered','confirmed')
       OR v_terms IS DISTINCT FROM r.commercial_terms_sha256 THEN
        RAISE EXCEPTION 'fulfilment order or commercial terms changed since proposal';
    END IF;

    UPDATE public.bsc_payment_requests
       SET status='approved', approved_by=v_actor, approved_at=clock_timestamp()
     WHERE id=r.id
     RETURNING * INTO r;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'approved',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object(
            'approval_note',v_note,'buyer_id',r.buyer_id,
            'fulfilment_order_id',r.fulfilment_order_id,
            'amount_usdt',r.amount_usdt::text,'payer_address',r.payer_address,
            'treasury_address',r.treasury_address,
            'commercial_terms_sha256',r.commercial_terms_sha256,
            'min_block_number',r.min_block_number,'expires_at',r.expires_at,
            'actual_revenue',false
        ));
    RETURN jsonb_build_object(
        'decision','approved','request_id',r.id,'status',r.status,
        'approved_by',r.approved_by,'approved_at',r.approved_at,
        'actual_revenue',false
    );
END;
$$;
CREATE FUNCTION public.cancel_bsc_payment_request(
    p_request_id uuid,
    p_actor text,
    p_reason text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    v_actor text := trim(COALESCE(p_actor,''));
    v_reason text := trim(COALESCE(p_reason,''));
BEGIN
    IF p_request_id IS NULL THEN RAISE EXCEPTION 'request_id is required'; END IF;
    IF length(v_actor) < 1 OR length(v_actor) > 200 THEN RAISE EXCEPTION 'actor is required'; END IF;
    IF length(v_reason) < 4 OR length(v_reason) > 1000 THEN RAISE EXCEPTION 'cancellation reason is required'; END IF;

    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    IF r.status='cancelled' THEN
        RETURN jsonb_build_object('decision','existing_cancellation','request_id',r.id,'actual_revenue',false);
    END IF;
    IF r.status='expired' THEN
        RETURN jsonb_build_object('decision','already_expired','request_id',r.id,'actual_revenue',false);
    END IF;
    PERFORM 1 FROM public.bsc_payment_evidence WHERE request_id=r.id;
    IF FOUND THEN RAISE EXCEPTION 'payment evidence already recorded; cancellation is not permitted'; END IF;

    UPDATE public.bsc_payment_requests SET status='cancelled' WHERE id=r.id RETURNING * INTO r;
    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'cancelled',v_actor,
        COALESCE(NULLIF(current_setting('role',true),'none'),session_user),
        jsonb_build_object('reason',v_reason,'previous_status','open','actual_revenue',false));
    RETURN jsonb_build_object('decision','cancelled','request_id',r.id,'status',r.status,'actual_revenue',false);
END;
$$;
CREATE FUNCTION public.get_bsc_payment_request_review(p_request_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    o public.fulfilment_orders%ROWTYPE;
    e public.bsc_payment_evidence%ROWTYPE;
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request not found'; END IF;
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
    SELECT * INTO e FROM public.bsc_payment_evidence WHERE request_id=r.id;
    RETURN jsonb_build_object(
        'request_id',r.id,'buyer_id',r.buyer_id,'fulfilment_order_id',r.fulfilment_order_id,
        'status',r.status,'amount_usdt',r.amount_usdt::text,
        'payer_address',r.payer_address,'treasury_address',r.treasury_address,
        'commercial_terms_sha256',r.commercial_terms_sha256,
        'min_block_number',r.min_block_number,'expires_at',r.expires_at,
        'approved_by',r.approved_by,'approved_at',r.approved_at,
        'idempotency_key',r.idempotency_key,'created_at',r.created_at,
        'order_state',o.state,
        'order_commercial_terms_sha256',lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256','')),
        'evidence_id',e.id,'evidence_transaction_hash',e.transaction_hash,
        'actual_revenue',false
    );
END;
$$;
CREATE OR REPLACE FUNCTION public.record_bsc_payment_evidence(
    p_request_id uuid, p_evidence jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    e public.bsc_payment_evidence%ROWTYPE;
    v_db_role text := COALESCE(NULLIF(current_setting('role',true),'none'),session_user);
BEGIN
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=p_request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF (p_evidence->>'verified') IS DISTINCT FROM 'true'
       OR (p_evidence->>'token_decimals') IS DISTINCT FROM '18' THEN
        RAISE EXCEPTION 'verified BSC USDT proof required';
    END IF;
    SELECT * INTO e FROM public.bsc_payment_evidence WHERE request_id=p_request_id;
    IF FOUND THEN
        IF e.transaction_hash IS DISTINCT FROM p_evidence->>'transaction_hash'
           OR e.block_hash IS DISTINCT FROM p_evidence->>'block_hash'
           OR e.amount_raw IS DISTINCT FROM (p_evidence->>'amount_raw')::numeric
           OR e.log_index IS DISTINCT FROM (p_evidence->>'log_index')::bigint
           OR e.chain_id IS DISTINCT FROM (p_evidence->>'chain_id')::integer
           OR e.token_contract IS DISTINCT FROM p_evidence->>'token_contract'
           OR e.block_number IS DISTINCT FROM (p_evidence->>'block_number')::bigint
           OR e.sender_address IS DISTINCT FROM p_evidence->>'sender_address'
           OR e.treasury_address IS DISTINCT FROM p_evidence->>'treasury_address'
           OR e.commercial_terms_sha256 IS DISTINCT FROM p_evidence->>'commercial_terms_sha256' THEN
            RAISE EXCEPTION 'request already recorded with different evidence';
        END IF;
        RETURN jsonb_build_object('decision','already_recorded','evidence_id',e.id,
                                  'request_id',e.request_id,'actual_revenue',false);
    END IF;
    INSERT INTO public.bsc_payment_evidence (
        request_id,fulfilment_order_id,chain_id,token_contract,transaction_hash,
        block_hash,block_number,log_index,amount_raw,confirmations,verified_at,
        sender_address,treasury_address,commercial_terms_sha256
    ) VALUES (
        p_request_id,r.fulfilment_order_id,(p_evidence->>'chain_id')::integer,
        p_evidence->>'token_contract',p_evidence->>'transaction_hash',
        p_evidence->>'block_hash',(p_evidence->>'block_number')::bigint,
        (p_evidence->>'log_index')::bigint,(p_evidence->>'amount_raw')::numeric,
        (p_evidence->>'confirmations')::integer,(p_evidence->>'verified_at')::timestamptz,
        p_evidence->>'sender_address',p_evidence->>'treasury_address',
        p_evidence->>'commercial_terms_sha256'
    ) RETURNING * INTO e;

    INSERT INTO public.bsc_payment_request_events(request_id,event_type,actor,db_role,details)
    VALUES (r.id,'evidence_recorded',v_db_role,v_db_role,
        jsonb_build_object(
            'evidence_id',e.id,'transaction_hash',e.transaction_hash,
            'block_hash',e.block_hash,'block_number',e.block_number,
            'confirmations',e.confirmations,'amount_raw',e.amount_raw::text,
            'verified_at',e.verified_at,'actual_revenue',false
        ));
    RETURN jsonb_build_object('decision','recorded','evidence_id',e.id,
                              'request_id',e.request_id,'actual_revenue',false);
END;
$$;
REVOKE ALL ON FUNCTION public.guard_bsc_payment_request_event()
    FROM PUBLIC,anon,authenticated,service_role,empire_payment_approver,empire_bsc_verifier;
REVOKE ALL ON FUNCTION public.propose_bsc_payment_request(
    uuid,numeric,text,text,bigint,timestamptz,text,text
) FROM PUBLIC,anon,authenticated,empire_payment_approver,empire_bsc_verifier;
REVOKE ALL ON FUNCTION public.approve_bsc_payment_request(uuid,text,text)
    FROM PUBLIC,anon,authenticated,service_role,empire_bsc_verifier;
REVOKE ALL ON FUNCTION public.cancel_bsc_payment_request(uuid,text,text)
    FROM PUBLIC,anon,authenticated,empire_bsc_verifier;
REVOKE ALL ON FUNCTION public.get_bsc_payment_request_review(uuid)
    FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.record_bsc_payment_evidence(uuid,jsonb)
    FROM PUBLIC,anon,authenticated,service_role,empire_payment_approver;

GRANT EXECUTE ON FUNCTION public.propose_bsc_payment_request(
    uuid,numeric,text,text,bigint,timestamptz,text,text
) TO service_role;
GRANT EXECUTE ON FUNCTION public.approve_bsc_payment_request(uuid,text,text)
    TO empire_payment_approver;
GRANT EXECUTE ON FUNCTION public.cancel_bsc_payment_request(uuid,text,text)
    TO service_role, empire_payment_approver;
GRANT EXECUTE ON FUNCTION public.get_bsc_payment_request_review(uuid)
    TO empire_payment_approver, empire_bsc_verifier;
GRANT EXECUTE ON FUNCTION public.record_bsc_payment_evidence(uuid,jsonb)
    TO empire_bsc_verifier;

COMMENT ON FUNCTION public.propose_bsc_payment_request(uuid,numeric,text,text,bigint,timestamptz,text,text)
    IS 'Service proposal only. Creates pending BSC payment terms; cannot approve or record evidence.';
COMMENT ON FUNCTION public.approve_bsc_payment_request(uuid,text,text)
    IS 'Human-approver boundary. Rechecks order and terms before approving a payment request.';
COMMENT ON FUNCTION public.cancel_bsc_payment_request(uuid,text,text)
    IS 'Fail-closed cancellation boundary. Cannot cancel after evidence has been recorded.';
COMMENT ON FUNCTION public.get_bsc_payment_request_review(uuid)
    IS 'Narrow review surface for payment approver/verifier roles; performs no mutation.';
COMMENT ON FUNCTION public.record_bsc_payment_evidence(uuid,jsonb)
    IS 'Dedicated verifier boundary. Records canonical BSC USDT evidence only after approved terms.';
COMMENT ON TABLE public.bsc_payment_request_events
    IS 'Append-only governance audit for BSC payment request lifecycle; not revenue recognition.';

COMMIT;
