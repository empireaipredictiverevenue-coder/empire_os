-- EmpireDB 049 v2 — STAGED, NOT APPROVED FOR PRODUCTION.
-- Separate SECURITY DEFINER owner. Does not reuse the inherited migrator.
-- Only an explicitly authorised DBA may apply after independent preflight.
-- No buyer login, payment authority, API route, mailbox or money activation.
BEGIN;
SET LOCAL statement_timeout = '12s';
SET LOCAL lock_timeout = '3s';

DO $preflight$
BEGIN
  IF current_database() NOT IN ('empiredb','direct_bsc_capability_fixture')
     OR NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname=current_user AND rolsuper
     )
  THEN
    RAISE EXCEPTION 'DIRECT049_WRONG_DATABASE_OR_OPERATOR';
  END IF;
  IF pg_catalog.to_regrole('empire_direct_checkout_status_owner') IS NOT NULL
    OR pg_catalog.to_regrole('empire_direct_checkout_status_reader') IS NOT NULL
    OR pg_catalog.to_regprocedure(
      'public.read_direct_bsc_buyer_status(text)') IS NOT NULL
  THEN
    RAISE EXCEPTION 'DIRECT049_READER_OBJECT_ALREADY_EXISTS_RECONCILE';
  END IF;
  -- This is the *existing* audited migration login. Preserve it untouched,
  -- while NEVER using empiredb_migrator as a buyer-status DEFINER or RLS role.
  IF (SELECT count(*) FROM pg_catalog.pg_auth_members m
      JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
      WHERE r.rolname='empiredb_migrator') <> 1
     OR NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_auth_members m
       JOIN pg_catalog.pg_roles parent ON parent.oid=m.roleid
       JOIN pg_catalog.pg_roles member ON member.oid=m.member
       WHERE parent.rolname='empiredb_migrator'
         AND member.rolname='empiredb_migrator_login'
         AND member.rolcanlogin AND member.rolinherit
         AND NOT member.rolsuper AND NOT member.rolbypassrls
         AND m.inherit_option AND m.set_option AND NOT m.admin_option
     )
  THEN
    RAISE EXCEPTION 'DIRECT049_UNEXPECTED_MIGRATOR_INCOMING_MEMBERSHIP';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
    WHERE c.oid=pg_catalog.to_regclass(
      'public.direct_bsc_buyer_capabilities')
      AND o.rolname='empiredb_migrator'
      AND c.relrowsecurity AND c.relforcerowsecurity
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_policy p
    WHERE p.polrelid=pg_catalog.to_regclass(
      'public.direct_bsc_buyer_capabilities')
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
    WHERE c.oid=pg_catalog.to_regclass(
      'public.direct_bsc_buyer_capabilities')
      AND a.grantee<>c.relowner
  ) THEN
    RAISE EXCEPTION 'DIRECT049_CAPABILITY_NOT_SEALED_AFTER_048';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
      WHERE c.relnamespace='public'::regnamespace
        AND c.relname IN ('fulfilment_orders','bsc_payment_requests',
                          'bsc_payment_evidence')
        AND o.rolname='empiredb_migrator'
        AND c.relrowsecurity AND NOT c.relforcerowsecurity
        AND EXISTS (
          SELECT 1 FROM pg_catalog.pg_policy p
          WHERE p.polrelid=c.oid AND p.polcmd='r'
            AND p.polpermissive
        )
      ) <> 3
  THEN
    RAISE EXCEPTION 'DIRECT049_PARENT_RLS_CONTRACT_DRIFT';
  END IF;
  -- Exact read-only production inventory: source policies observed on
  -- 13 Oct 2026, and no restrictive policy. Any drift needs fresh review.
  IF EXISTS (
    WITH expected(name, policies) AS (
      VALUES ('fulfilment_orders',23),
             ('bsc_payment_requests',10),
             ('bsc_payment_evidence',9)
    )
    SELECT 1
    FROM expected e
    JOIN pg_catalog.pg_class c ON c.relname=e.name
      AND c.relnamespace='public'::regnamespace
    WHERE (SELECT count(*) FROM pg_catalog.pg_policy p
           WHERE p.polrelid=c.oid) <> e.policies
      OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_policy p
        WHERE p.polrelid=c.oid AND NOT p.polpermissive
      )
  ) THEN
    RAISE EXCEPTION 'DIRECT049_PARENT_POLICY_BASELINE_DRIFT';
  END IF;
END;
$preflight$;

-- Two disjoint NOLOGIN, NOINHERIT roles with zero memberships:
-- owner has only needed column SELECT; reader has only function EXECUTE.
CREATE ROLE empire_direct_checkout_status_owner
  NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS;
CREATE ROLE empire_direct_checkout_status_reader
  NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO
  empire_direct_checkout_status_owner,
  empire_direct_checkout_status_reader;

GRANT SELECT (
  token_fingerprint,fulfilment_order_id,request_id,
  issued_at,expires_at,revoked_at
) ON public.direct_bsc_buyer_capabilities
  TO empire_direct_checkout_status_owner;
GRANT SELECT (
  id,buyer_id,state,price_cents,commercial_payload
) ON public.fulfilment_orders
  TO empire_direct_checkout_status_owner;
GRANT SELECT (
  id,buyer_id,fulfilment_order_id,settlement_mode,
  commercial_terms_sha256,payer_address,treasury_address,
  amount_usdt,status,approved_by,approved_at,expires_at
) ON public.bsc_payment_requests
  TO empire_direct_checkout_status_owner;
GRANT SELECT (
  id,request_id,fulfilment_order_id,chain_id,
  token_contract,treasury_address,
  commercial_terms_sha256,confirmations
) ON public.bsc_payment_evidence
  TO empire_direct_checkout_status_owner;

-- Existing parent policies remain unchanged. Dedicated owner alone gets
-- a read path; no login can SET this new owner. The SECURITY DEFINER
-- function below requires the 256-bit HMAC fingerprint and exact joins.
CREATE POLICY direct_bsc_status_owner_capability_select
  ON public.direct_bsc_buyer_capabilities
  FOR SELECT TO empire_direct_checkout_status_owner
  USING (revoked_at IS NULL
    AND issued_at <= pg_catalog.statement_timestamp()
    AND expires_at > pg_catalog.statement_timestamp());
CREATE POLICY direct_bsc_status_owner_orders_select
  ON public.fulfilment_orders
  FOR SELECT TO empire_direct_checkout_status_owner USING (true);
CREATE POLICY direct_bsc_status_owner_requests_select
  ON public.bsc_payment_requests
  FOR SELECT TO empire_direct_checkout_status_owner USING (true);
CREATE POLICY direct_bsc_status_owner_evidence_select
  ON public.bsc_payment_evidence
  FOR SELECT TO empire_direct_checkout_status_owner USING (true);

CREATE FUNCTION public.read_direct_bsc_buyer_status(p_digest text)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path=''
AS $reader$
SELECT pg_catalog.jsonb_build_object(
  'access', pg_catalog.jsonb_build_object(
    'token_fingerprint',cap.token_fingerprint,
    'order_id',cap.fulfilment_order_id,
    'request_id',cap.request_id,
    'issued_at',cap.issued_at,
    'expires_at',cap.expires_at,
    'revoked_at',cap.revoked_at),
  'order', pg_catalog.jsonb_build_object(
    'id',o.id,'buyer_id',o.buyer_id,
    'state',o.state,'price_cents',o.price_cents,
    'commercial_payload',pg_catalog.jsonb_build_object(
      'commercial_terms_sha256',o.commercial_payload->>'commercial_terms_sha256',
      'payer_wallet',o.commercial_payload->>'payer_wallet')),
  'payment',pg_catalog.jsonb_build_object(
    'id',p.id,'buyer_id',p.buyer_id,
    'fulfilment_order_id',p.fulfilment_order_id,
    'settlement_mode',p.settlement_mode,
    'commercial_terms_sha256',p.commercial_terms_sha256,
    'payer_address',p.payer_address,
    'treasury_address',p.treasury_address,
    'amount_usdt',p.amount_usdt::text,
    'status',p.status,
    'approved_by',p.approved_by,
    'approved_at',p.approved_at,
    'expires_at',p.expires_at),
  'evidence',CASE WHEN e.id IS NULL THEN NULL
    ELSE pg_catalog.jsonb_build_object(
      'request_id',e.request_id,
      'fulfilment_order_id',e.fulfilment_order_id,
      'chain_id',e.chain_id,
      'token_contract',e.token_contract,
      'treasury_address',e.treasury_address,
      'commercial_terms_sha256',e.commercial_terms_sha256,
      'confirmations',e.confirmations) END
)
FROM public.direct_bsc_buyer_capabilities cap
JOIN public.fulfilment_orders o
  ON o.id=cap.fulfilment_order_id
JOIN public.bsc_payment_requests p
  ON p.id=cap.request_id
 AND p.fulfilment_order_id=o.id AND p.buyer_id=o.buyer_id
LEFT JOIN public.bsc_payment_evidence e
  ON e.request_id=p.id AND e.fulfilment_order_id=o.id
WHERE p_digest ~ '^[0-9a-f]{64}$'
  AND cap.token_fingerprint=p_digest
  AND cap.revoked_at IS NULL
  AND cap.issued_at <= pg_catalog.statement_timestamp()
  AND cap.expires_at > pg_catalog.statement_timestamp()
  AND cap.expires_at <= p.expires_at
  AND p.settlement_mode='direct'
  AND p.status IN ('pending','approved','cancelled','expired')
  AND o.state IN ('accepted','invoiced','delivered','confirmed')
  AND o.commercial_payload->>'commercial_terms_sha256' =
      p.commercial_terms_sha256
  AND pg_catalog.lower(o.commercial_payload->>'payer_wallet') = p.payer_address
  AND p.amount_usdt = o.price_cents::numeric / 100
LIMIT 1;
$reader$;

-- Created by postgres initially; transfer to a purpose-specific NOLOGIN
-- owner. Never owned by migrator or its inherited LOGIN role.
ALTER FUNCTION public.read_direct_bsc_buyer_status(text)
  OWNER TO empire_direct_checkout_status_owner;
REVOKE ALL ON FUNCTION public.read_direct_bsc_buyer_status(text)
  FROM PUBLIC, empiredb_app, empiredb_readonly;
GRANT EXECUTE ON FUNCTION public.read_direct_bsc_buyer_status(text)
  TO empire_direct_checkout_status_reader;

DO $postcheck$
DECLARE
  owner_oid oid := 'empire_direct_checkout_status_owner'::regrole;
  reader_oid oid := 'empire_direct_checkout_status_reader'::regrole;
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    WHERE m.member IN (owner_oid,reader_oid)
       OR m.roleid IN (owner_oid,reader_oid)
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.rolname IN (
      'empire_direct_checkout_status_owner',
      'empire_direct_checkout_status_reader')
      AND (r.rolcanlogin OR r.rolinherit OR r.rolsuper
           OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication
           OR r.rolbypassrls)
  ) THEN
    RAISE EXCEPTION 'DIRECT049_ISOLATED_ROLES_UNSAFE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc f
    WHERE f.oid=pg_catalog.to_regprocedure(
      'public.read_direct_bsc_buyer_status(text)')
      AND f.proowner=owner_oid AND f.prosecdef AND f.provolatile='s'
  ) OR NOT pg_catalog.has_function_privilege(
      'empire_direct_checkout_status_reader',
      'public.read_direct_bsc_buyer_status(text)','EXECUTE')
    OR pg_catalog.has_function_privilege(
      'empiredb_app','public.read_direct_bsc_buyer_status(text)','EXECUTE')
    OR pg_catalog.has_function_privilege(
      'empiredb_readonly','public.read_direct_bsc_buyer_status(text)','EXECUTE')
  THEN
    RAISE EXCEPTION 'DIRECT049_FUNCTION_AUTHORITY_DRIFT';
  END IF;
  -- Detect any unexpected grantor/default-function grant including PUBLIC.
  IF (SELECT count(*) FROM pg_catalog.pg_proc f
      CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))) acl
      WHERE f.oid=pg_catalog.to_regprocedure(
        'public.read_direct_bsc_buyer_status(text)')
        AND acl.grantee<>owner_oid
        AND acl.grantee<>reader_oid
    ) <> 0 OR NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_proc f
      CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))) acl
      WHERE f.oid=pg_catalog.to_regprocedure(
        'public.read_direct_bsc_buyer_status(text)')
        AND acl.grantee=reader_oid
        AND acl.privilege_type='EXECUTE' AND NOT acl.is_grantable
    )
  THEN
    RAISE EXCEPTION 'DIRECT049_UNEXPECTED_FUNCTION_EXECUTE_GRANT';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_policy p
      WHERE p.polrelid='public.direct_bsc_buyer_capabilities'::regclass
        AND p.polname='direct_bsc_status_owner_capability_select'
        AND p.polcmd='r' AND p.polpermissive
        AND p.polroles=ARRAY[owner_oid]
    ) <> 1
  THEN
    RAISE EXCEPTION 'DIRECT049_CAPABILITY_POLICY_DRIFT';
  END IF;
  IF pg_catalog.has_table_privilege(
       'empire_direct_checkout_status_reader',
       'public.direct_bsc_buyer_capabilities','SELECT')
     OR pg_catalog.has_table_privilege(
       'empiredb_app','public.direct_bsc_buyer_capabilities','SELECT')
  THEN
    RAISE EXCEPTION 'DIRECT049_UNEXPECTED_CAPABILITY_TABLE_ACCESS';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_policy p
      WHERE p.polrelid='public.direct_bsc_buyer_capabilities'::regclass) <> 1
  THEN
    RAISE EXCEPTION 'DIRECT049_CAPABILITY_POLICY_COUNT_DRIFT';
  END IF;
END;
$postcheck$;
COMMIT;
