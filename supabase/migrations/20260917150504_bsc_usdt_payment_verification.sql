-- Tested in isolated PostgreSQL; live application requires explicit approval.
-- Creates no requests/payments; API recording and buyer activation stay disabled.
BEGIN;
CREATE TABLE public.bsc_payment_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id uuid NOT NULL REFERENCES public.buyers(id) ON DELETE RESTRICT,
    fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
    amount_usdt numeric NOT NULL CHECK (
        amount_usdt > 0 AND amount_usdt < 1e59 AND
        amount_usdt = trunc(amount_usdt,18)
    ),
    payer_address text NOT NULL CHECK (payer_address ~ '^0x[0-9a-f]{40}$'),
    treasury_address text NOT NULL CHECK (treasury_address ~ '^0x[0-9a-f]{40}$'),
    commercial_terms_sha256 text NOT NULL CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$'),
    min_block_number bigint NOT NULL CHECK (min_block_number > 0),
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending','approved','cancelled','expired')
    ),
    approved_by text,
    approved_at timestamptz,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at > created_at),
    CHECK (status <> 'approved' OR (
        approved_by IS NOT NULL AND length(trim(approved_by)) > 0
        AND approved_at IS NOT NULL AND approved_at < expires_at
    ))
);
CREATE INDEX bsc_payment_requests_buyer_idx ON public.bsc_payment_requests(buyer_id);
CREATE INDEX bsc_payment_requests_order_idx ON public.bsc_payment_requests(fulfilment_order_id);

CREATE TABLE public.bsc_payment_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL UNIQUE REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
    chain_id integer NOT NULL CHECK (chain_id = 56),
    token_contract text NOT NULL CHECK (
        token_contract = '0x55d398326f99059ff775485246999027b3197955'
    ),
    transaction_hash text NOT NULL UNIQUE CHECK (transaction_hash ~ '^0x[0-9a-f]{64}$'),
    block_hash text NOT NULL CHECK (block_hash ~ '^0x[0-9a-f]{64}$'),
    block_number bigint NOT NULL CHECK (block_number > 0),
    log_index bigint NOT NULL CHECK (log_index >= 0),
    amount_raw numeric NOT NULL CHECK (
        amount_raw > 0 AND amount_raw < power(2::numeric,256)
        AND amount_raw = trunc(amount_raw)
    ),
    confirmations integer NOT NULL CHECK (confirmations >= 12),
    verified_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
-- Whole-transaction uniqueness deliberately disallows splitting one transaction
-- between requests. Never use a check-then-insert in place of these constraints.
ALTER TABLE public.bsc_payment_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsc_payment_evidence ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bsc_payment_requests FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON public.bsc_payment_evidence FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.bsc_payment_requests, public.bsc_payment_evidence TO service_role;
-- API writes remain disabled pending the verifier-role/approval workflow and
-- replacement of the legacy activation gate. Recorder is defined below.
COMMENT ON TABLE public.bsc_payment_evidence IS
    'Reserved BSC payment evidence; not automatically recognized revenue or buyer activation.';
-- Recorder definitions follow in the same transaction.

-- Transaction-safe recording boundary. Backend assertions remain trusted:
-- PostgreSQL cannot independently query BSC; only the governed verifier may supply proof.
ALTER TABLE public.bsc_payment_evidence
    ADD COLUMN fulfilment_order_id uuid NOT NULL UNIQUE REFERENCES public.fulfilment_orders(id),
    ADD COLUMN sender_address text NOT NULL CHECK (sender_address ~ '^0x[0-9a-f]{40}$'),
    ADD COLUMN treasury_address text NOT NULL CHECK (treasury_address ~ '^0x[0-9a-f]{40}$'),
    ADD COLUMN commercial_terms_sha256 text NOT NULL CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$');

CREATE FUNCTION public.guard_bsc_payment_request()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'payment requests cannot be deleted';
    END IF;
    IF OLD.status <> 'pending' AND (
        (to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status')
        OR NEW.status NOT IN (OLD.status, 'cancelled', 'expired')
    ) THEN
        RAISE EXCEPTION 'approved payment terms are immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_bsc_payment_request
BEFORE UPDATE OR DELETE ON public.bsc_payment_requests
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_payment_request();

CREATE FUNCTION public.guard_bsc_payment_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    o public.fulfilment_orders%ROWTYPE;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'payment evidence is append-only';
    END IF;
    SELECT * INTO r FROM public.bsc_payment_requests WHERE id=NEW.request_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'payment request missing'; END IF;
    IF r.status <> 'approved' OR r.approved_at IS NULL
       OR r.approved_at > clock_timestamp() OR r.expires_at <= clock_timestamp()
       OR NULLIF(trim(r.approved_by),'') IS NULL THEN
        RAISE EXCEPTION 'current human-approved request required';
    END IF;
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'order missing'; END IF;
    IF o.buyer_id IS DISTINCT FROM r.buyer_id
       OR o.state NOT IN ('accepted','invoiced','delivered','confirmed')
       OR o.state IS NULL
       OR (o.commercial_payload->>'commercial_terms_sha256')
           IS DISTINCT FROM r.commercial_terms_sha256 THEN
        RAISE EXCEPTION 'order or terms mismatch';
    END IF;
    IF NEW.fulfilment_order_id IS DISTINCT FROM r.fulfilment_order_id
       OR NEW.sender_address IS DISTINCT FROM r.payer_address
       OR NEW.treasury_address IS DISTINCT FROM r.treasury_address
       OR NEW.commercial_terms_sha256 IS DISTINCT FROM r.commercial_terms_sha256
       OR NEW.amount_raw < r.amount_usdt * 1000000000000000000
       OR NEW.block_number < r.min_block_number THEN
        RAISE EXCEPTION 'payment evidence does not match approved request';
    END IF;
    IF NEW.verified_at < clock_timestamp() - interval '5 minutes'
       OR NEW.verified_at > clock_timestamp() + interval '5 seconds' THEN
        RAISE EXCEPTION 'fresh verification required';
    END IF;
    NEW.recorded_at := clock_timestamp();
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_bsc_payment_evidence
BEFORE INSERT OR UPDATE OR DELETE ON public.bsc_payment_evidence
FOR EACH ROW EXECUTE FUNCTION public.guard_bsc_payment_evidence();

CREATE FUNCTION public.record_bsc_payment_evidence(
    p_request_id uuid, p_evidence jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    r public.bsc_payment_requests%ROWTYPE;
    e public.bsc_payment_evidence%ROWTYPE;
BEGIN
    -- Serialize retries of the same request. Other requests compete on UNIQUE keys.
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
    RETURN jsonb_build_object('decision','recorded','evidence_id',e.id,
                              'request_id',e.request_id,'actual_revenue',false);
END;
$$;
REVOKE ALL ON FUNCTION public.guard_bsc_payment_request() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.guard_bsc_payment_evidence() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.record_bsc_payment_evidence(uuid,jsonb)
    FROM PUBLIC,anon,authenticated,service_role;
-- No API execution/write grants in this migration. The recorder is tested as
-- database owner only; enabling a dedicated verifier role requires approval.
COMMIT;
