-- DRAFT: review and test in disposable Postgres before any live application.
-- Creates no requests/payments; enables no recording or activation endpoint.
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
-- NO API write grants yet: recording RPC, approval workflow, immutable terms,
-- race/replay tests, and legacy activation-gate replacement remain required.
COMMENT ON TABLE public.bsc_payment_evidence IS
    'Reserved BSC payment evidence; not automatically recognized revenue or buyer activation.';
COMMIT;
