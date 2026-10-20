-- NOT APPROVED FOR PRODUCTION. DBA AND FOUNDER MUST FIRST REVIEW.
-- Stored outside migrations/empiredb to prevent accidental discovery.
-- No app grants, logins, payment function, delivery action or revenue logic.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';
DO $preflight$
BEGIN
 IF current_database() NOT IN ('empiredb','exchange_seat_fixture')
   OR current_user <> 'empiredb_migrator' THEN
   RAISE EXCEPTION 'EXCHANGE_SEAT_DRAFT_WRONG_DB_ROLE';
 END IF;
 IF pg_catalog.to_regclass('public.exchange_seat_memberships') IS NOT NULL
    OR pg_catalog.to_regclass('public.exchange_seat_invoice_cycles') IS NOT NULL THEN
   RAISE EXCEPTION 'EXCHANGE_SEAT_DRAFT_OBJECT_ALREADY_PRESENT';
 END IF;
 IF pg_catalog.to_regclass('public.buyers') IS NULL
    OR pg_catalog.to_regclass('public.fulfilment_orders') IS NULL
    OR pg_catalog.to_regclass('public.bsc_payment_requests') IS NULL
    OR pg_catalog.to_regclass('public.bsc_payment_evidence') IS NULL THEN
   RAISE EXCEPTION 'EXCHANGE_SEAT_DRAFT_PARENT_SCHEMA_MISSING';
 END IF;
END;
$preflight$;

-- Separate from old strike_packs/Stripe-era buyer_subscriptions. A seat
-- proposal does NOT create a paid subscription or entitlement.
CREATE TABLE public.exchange_seat_memberships (
 id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
 buyer_id uuid NOT NULL REFERENCES public.buyers(id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL,
 product_code text NOT NULL CHECK (product_code IN (
  'exchange_seat_starter','exchange_seat_growth',
  'exchange_seat_pro','exchange_seat_enterprise'
 )),
 monthly_price_cents integer NOT NULL CHECK (
  (product_code='exchange_seat_starter' AND monthly_price_cents=9900)
  OR (product_code='exchange_seat_growth' AND monthly_price_cents=24900)
  OR (product_code='exchange_seat_pro' AND monthly_price_cents=49900)
  OR (product_code='exchange_seat_enterprise' AND monthly_price_cents=99900)
 ),
 currency text NOT NULL DEFAULT 'USD' CHECK (currency='USD'),
 source_kind text NOT NULL DEFAULT 'native_exchange_seat_monthly'
   CHECK (source_kind='native_exchange_seat_monthly'),
 commercial_terms_sha256 text NOT NULL CHECK (commercial_terms_sha256 ~ '^[a-f0-9]{64}$'),
 accepted_terms_at timestamptz,
 billing_anchor_at timestamptz NOT NULL,
 contract_state text NOT NULL DEFAULT 'proposed'
   CHECK (contract_state IN ('proposed','accepted','suspended','cancelled')),
 suspension_reason text CHECK (
   suspension_reason IN ('dispute','nonpayment','revocation','fraud_review')),
 cancel_effective_at timestamptz,
 approved_issuer_ref text NOT NULL
   CHECK (length(btrim(approved_issuer_ref)) BETWEEN 8 AND 160),
 created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 UNIQUE (id,tenant_id,buyer_id),
 CHECK (contract_state <> 'accepted' OR accepted_terms_at IS NOT NULL),
 CHECK (contract_state <> 'cancelled' OR cancel_effective_at IS NOT NULL),
 CHECK (cancel_effective_at IS NULL OR cancel_effective_at >= billing_anchor_at)
);
CREATE INDEX exchange_seat_memberships_tenant_buyer_idx
 ON public.exchange_seat_memberships(tenant_id,buyer_id,contract_state);

-- Per-calendar-month journal, with native order/request/evidence uniqueness.
-- NOT a completed payment ledger by itself: finality requires independent
-- finance attestation and secure tenant-scoped owner writer.
CREATE TABLE public.exchange_seat_invoice_cycles (
 id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
 membership_id uuid NOT NULL,
 tenant_id uuid NOT NULL,
 buyer_id uuid NOT NULL REFERENCES public.buyers(id) ON DELETE RESTRICT,
 FOREIGN KEY (membership_id,tenant_id,buyer_id)
   REFERENCES public.exchange_seat_memberships(id,tenant_id,buyer_id)
   ON DELETE RESTRICT,
 period_index integer NOT NULL CHECK (period_index BETWEEN 0 AND 23),
 period_start timestamptz NOT NULL,
 period_end timestamptz NOT NULL,
 invoice_order_id uuid UNIQUE
   REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
 payment_request_id uuid UNIQUE
   REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
 payment_evidence_id uuid UNIQUE
   REFERENCES public.bsc_payment_evidence(id) ON DELETE RESTRICT,
 quote_source_digest text CHECK (
   quote_source_digest IS NULL OR quote_source_digest ~ '^[a-f0-9]{64}$'),
 commercial_terms_sha256 text NOT NULL CHECK (
   commercial_terms_sha256 ~ '^[a-f0-9]{64}$'),
 quoted_monthly_price_cents integer NOT NULL
   CHECK (quoted_monthly_price_cents IN (9900,24900,49900,99900)),
 cycle_state text NOT NULL DEFAULT 'pending' CHECK (
   cycle_state IN ('pending','paid_receipt_review','held','refunded','reversed')),
 reversal_evidence_ref text,
 created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 UNIQUE (membership_id,period_index),
 UNIQUE (membership_id,period_start),
 CHECK (period_end > period_start),
 CHECK (cycle_state <> 'paid_receipt_review'
   OR (invoice_order_id IS NOT NULL AND payment_request_id IS NOT NULL
     AND payment_evidence_id IS NOT NULL AND quote_source_digest IS NOT NULL)),
 CHECK (cycle_state NOT IN ('refunded','reversed')
   OR (reversal_evidence_ref IS NOT NULL
     AND length(btrim(reversal_evidence_ref)) BETWEEN 8 AND 160))
);
CREATE INDEX exchange_seat_invoice_cycles_tenant_buyer_period_idx
 ON public.exchange_seat_invoice_cycles(tenant_id,buyer_id,period_start);

-- SEALED: no tenant, buyer, app or finance user may read or write via these
-- new tables after deployment until a separately approved ACL/role gate.
ALTER TABLE public.exchange_seat_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exchange_seat_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE public.exchange_seat_invoice_cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exchange_seat_invoice_cycles FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.exchange_seat_memberships FROM PUBLIC;
REVOKE ALL ON public.exchange_seat_invoice_cycles FROM PUBLIC;

-- Fail the proposed migration if any default privilege expands application
-- access, if RLS is not forced, or if even one policy was inherited.
DO $postcheck$
BEGIN
 IF EXISTS (
   SELECT 1
   FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public'
     AND c.relname IN (
       'exchange_seat_memberships','exchange_seat_invoice_cycles')
     AND (c.relkind <> 'r'
       OR NOT c.relrowsecurity OR NOT c.relforcerowsecurity
       OR c.relowner <> 'empiredb_migrator'::regrole
       OR EXISTS (
         SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid)
       OR EXISTS (
         SELECT 1
         FROM pg_catalog.aclexplode(
           COALESCE(c.relacl,
             pg_catalog.acldefault('r',c.relowner))) acl
         WHERE acl.grantee <> c.relowner))
 ) OR (
   SELECT count(*) FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public'
     AND c.relname IN (
       'exchange_seat_memberships','exchange_seat_invoice_cycles')
 ) <> 2 THEN
   RAISE EXCEPTION 'EXCHANGE_SEAT_DRAFT_UNEXPECTED_ACL_OR_RLS_DRIFT';
 END IF;
END;
$postcheck$;

-- Further controls REQUIRED BEFORE APPROVAL, not implemented here:
-- 1. Trusted session tenant and buyer.org_id binding (enforced in DB).
-- Composite FK already enforces cycle->member tenant/buyer; it does not
-- prove buyers.org_id against caller tenant or authenticate current role.
-- 2. Independently authenticated Stripe-free USDT/BSC settlement.
-- 3. Immutable per-cycle event audit/reversal, concurrent invoice lock.
-- 4. Terms/FX proof, cancellation, expiry, MRR recognition contracts.
-- 5. Least-privilege new owner-only reader/writer role, guarded RLS policy.
-- 6. No entitlement or lead delivery without independent release gate.

COMMENT ON TABLE public.exchange_seat_memberships IS
 'Prepared-only Exchange membership schema, no payment or entitlement authority';
COMMENT ON TABLE public.exchange_seat_invoice_cycles IS
 'Prepared-only calendar billing audit schema, not evidence of actual MRR';
COMMIT;
-- DO NOT INVOKE IN PRODUCTION. Reconcile live catalog + approve later version.
