-- PREPARED ONLY. EmpireDB 049: internal buyer-bound BSC status reader.
-- DOES NOT INSTALL without separate founder migration approval.
-- No live public endpoint, no credential, no payment execution, no writer role.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $bootstrap$
BEGIN
  IF current_database() NOT IN ('empiredb','direct_bsc_capability_fixture') THEN
    RAISE EXCEPTION 'DIRECT049_WRONG_CANONICAL_DATABASE';
  END IF;
  IF pg_catalog.to_regrole('empire_direct_checkout_status_reader') IS NOT NULL
  THEN
    RAISE EXCEPTION 'DIRECT049_READER_ROLE_ALREADY_EXISTS_RECONCILE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname=current_user AND rolsuper
  ) THEN
    RAISE EXCEPTION 'DIRECT049_PRIVILEGED_ROLE_BOOTSTRAP_REQUIRED';
  END IF;
  CREATE ROLE empire_direct_checkout_status_reader
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
  -- Bootstrap under privileged DBA before SET LOCAL ROLE; migrator may not
  -- have GRANT OPTION for public schema USAGE in canonical EmpireDB.
  GRANT USAGE ON SCHEMA public TO empire_direct_checkout_status_reader;
END;
$bootstrap$;

SET LOCAL ROLE empiredb_migrator;

DO $guard$
BEGIN
  IF current_user <> 'empiredb_migrator'
    OR pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities') IS NULL
    OR pg_catalog.to_regclass('public.fulfilment_orders') IS NULL
    OR pg_catalog.to_regclass('public.bsc_payment_requests') IS NULL
    OR pg_catalog.to_regclass('public.bsc_payment_evidence') IS NULL
  THEN
    RAISE EXCEPTION 'DIRECT049_PARENT_OR_AUTHORITY_MISSING';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.rolname='empire_direct_checkout_status_reader'
      AND NOT r.rolcanlogin AND NOT r.rolinherit AND NOT r.rolsuper
      AND NOT r.rolcreatedb AND NOT r.rolcreaterole
      AND NOT r.rolreplication AND NOT r.rolbypassrls
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
    WHERE r.rolname='empire_direct_checkout_status_reader'
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles r ON r.oid=m.member
    WHERE r.rolname='empire_direct_checkout_status_reader'
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
    WHERE granted.rolname='empiredb_migrator'
  ) THEN
    RAISE EXCEPTION 'DIRECT049_ROLE_MEMBERSHIP_OR_PRIVILEGE_UNSAFE';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_policy p
    WHERE p.polrelid='public.direct_bsc_buyer_capabilities'::pg_catalog.regclass
  ) OR pg_catalog.to_regprocedure(
     'public.read_direct_bsc_buyer_status(text)') IS NOT NULL
    OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_roles owner ON owner.oid=c.relowner
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::pg_catalog.regclass
      AND c.relrowsecurity AND c.relforcerowsecurity
      AND owner.rolname='empiredb_migrator'
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) acl
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::pg_catalog.regclass
      AND acl.grantee <> c.relowner
  ) THEN
    RAISE EXCEPTION 'DIRECT049_SEALED_CAPABILITY_TABLE_NOT_VERIFIED';
  END IF;
  IF NOT pg_catalog.has_table_privilege(
       current_user,'public.fulfilment_orders','SELECT')
    OR NOT pg_catalog.has_table_privilege(
       current_user,'public.bsc_payment_requests','SELECT')
    OR NOT pg_catalog.has_table_privilege(
       current_user,'public.bsc_payment_evidence','SELECT')
  THEN
    RAISE EXCEPTION 'DIRECT049_PARENT_READ_AUTHORITY_UNVERIFIED';
  END IF;
END;
$guard$;

-- Owner is a NOLOGIN migrator with no members. RLS remains FORCED; only
-- its DEFINER function uses this SELECT policy. No app role gets table ACL.
CREATE POLICY direct_bsc_buyer_status_migrator_select
ON public.direct_bsc_buyer_capabilities
FOR SELECT TO empiredb_migrator
USING (
  revoked_at IS NULL
  AND issued_at <= pg_catalog.statement_timestamp()
  AND expires_at > pg_catalog.statement_timestamp()
);

-- Returns only fields needed for a second independent Python projector.
-- NO buyer email, business identity, idempotency key or tx hash returned.
-- A keyed HMAC fingerprint is derived by the private caller; never a raw token.
CREATE FUNCTION public.read_direct_bsc_buyer_status(p_digest text)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $read$
SELECT pg_catalog.jsonb_build_object(
  'access', pg_catalog.jsonb_build_object(
    'token_fingerprint', cap.token_fingerprint,
    'order_id', cap.fulfilment_order_id,
    'request_id', cap.request_id,
    'issued_at', cap.issued_at,
    'expires_at', cap.expires_at,
    'revoked_at', cap.revoked_at
  ),
  'order', pg_catalog.jsonb_build_object(
    'id', ord.id, 'buyer_id', ord.buyer_id,
    'state', ord.state, 'price_cents', ord.price_cents,
    'commercial_payload', pg_catalog.jsonb_build_object(
      'commercial_terms_sha256', ord.commercial_payload->>'commercial_terms_sha256',
      'payer_wallet', ord.commercial_payload->>'payer_wallet'
    )
  ),
  'payment', pg_catalog.jsonb_build_object(
    'id', req.id, 'buyer_id', req.buyer_id,
    'fulfilment_order_id', req.fulfilment_order_id,
    'settlement_mode', req.settlement_mode,
    'commercial_terms_sha256', req.commercial_terms_sha256,
    'payer_address', req.payer_address,
    'treasury_address', req.treasury_address,
    'amount_usdt', req.amount_usdt::text,
    'status', req.status, 'approved_by', req.approved_by,
    'approved_at', req.approved_at, 'expires_at', req.expires_at
  ),
  'evidence', CASE WHEN evidence.id IS NULL THEN NULL
    ELSE pg_catalog.jsonb_build_object(
      'request_id', evidence.request_id,
      'fulfilment_order_id', evidence.fulfilment_order_id,
      'chain_id', evidence.chain_id,
      'token_contract', evidence.token_contract,
      'treasury_address', evidence.treasury_address,
      'commercial_terms_sha256', evidence.commercial_terms_sha256,
      'confirmations', evidence.confirmations
    ) END
)
FROM public.direct_bsc_buyer_capabilities cap
JOIN public.fulfilment_orders ord ON ord.id=cap.fulfilment_order_id
JOIN public.bsc_payment_requests req
  ON req.id=cap.request_id
 AND req.fulfilment_order_id=ord.id
 AND req.buyer_id=ord.buyer_id
LEFT JOIN public.bsc_payment_evidence evidence
  ON evidence.request_id=req.id AND evidence.fulfilment_order_id=ord.id
WHERE p_digest ~ '^[0-9a-f]{64}$'
  AND cap.token_fingerprint=p_digest
  AND cap.revoked_at IS NULL
  AND cap.issued_at <= pg_catalog.statement_timestamp()
  AND cap.expires_at > pg_catalog.statement_timestamp()
  AND cap.expires_at <= req.expires_at
  AND req.settlement_mode='direct'
  AND req.status IN ('pending','approved','cancelled','expired')
  AND ord.state IN ('accepted','invoiced','delivered','confirmed')
  AND ord.commercial_payload->>'commercial_terms_sha256' =
      req.commercial_terms_sha256
  AND pg_catalog.lower(ord.commercial_payload->>'payer_wallet') =
      req.payer_address
  AND req.amount_usdt = ord.price_cents::numeric / 100
LIMIT 1;
$read$;

REVOKE ALL ON FUNCTION public.read_direct_bsc_buyer_status(text)
  FROM PUBLIC, empiredb_app, empiredb_readonly;
GRANT EXECUTE ON FUNCTION public.read_direct_bsc_buyer_status(text)
  TO empire_direct_checkout_status_reader;

DO $verify$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc f
    JOIN pg_catalog.pg_roles o ON o.oid=f.proowner
    WHERE f.oid=pg_catalog.to_regprocedure(
      'public.read_direct_bsc_buyer_status(text)')
      AND o.rolname='empiredb_migrator'
      AND f.prosecdef AND f.provolatile='s'
  ) OR NOT pg_catalog.has_function_privilege(
    'empire_direct_checkout_status_reader',
    'public.read_direct_bsc_buyer_status(text)','EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empiredb_app','public.read_direct_bsc_buyer_status(text)','EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'empiredb_readonly','public.read_direct_bsc_buyer_status(text)','EXECUTE'
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_policy p
    WHERE p.polrelid='public.direct_bsc_buyer_capabilities'::pg_catalog.regclass
      AND p.polname='direct_bsc_buyer_status_migrator_select'
  ) OR pg_catalog.has_table_privilege(
    'empire_direct_checkout_status_reader',
    'public.direct_bsc_buyer_capabilities','SELECT'
  ) THEN
    RAISE EXCEPTION 'DIRECT049_READER_SEAL_OR_ROLE_FAILED';
  END IF;
END;
$verify$;
COMMIT;
