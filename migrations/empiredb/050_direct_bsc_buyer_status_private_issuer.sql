-- EmpireDB 050 v1: ISOLATED buyer-status token issuer, STAGED ONLY.
-- NOT approved for production. No customer email, bearer storage, wallet action,
-- public route, reader login or checkout feature activation.
BEGIN;
SET LOCAL statement_timeout='12s';
SET LOCAL lock_timeout='3s';

DO $preflight$
DECLARE
  owner_oid oid;
  reader_oid oid;
BEGIN
  IF current_database() NOT IN ('empiredb','direct_bsc_capability_fixture')
     OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                    WHERE rolname=current_user AND rolsuper)
  THEN RAISE EXCEPTION 'DIRECT050_CANONICAL_SUPERUSER_REQUIRED'; END IF;
  IF pg_catalog.to_regrole('empire_direct_checkout_status_issuer_owner') IS NOT NULL
    OR pg_catalog.to_regrole('empire_direct_checkout_status_issuer') IS NOT NULL
    OR pg_catalog.to_regprocedure(
      'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)'
    ) IS NOT NULL
  THEN RAISE EXCEPTION 'DIRECT050_OBJECT_ALREADY_EXISTS_RECONCILE'; END IF;
  owner_oid:=pg_catalog.to_regrole('empire_direct_checkout_status_owner');
  reader_oid:=pg_catalog.to_regrole('empire_direct_checkout_status_reader');
  IF owner_oid IS NULL OR reader_oid IS NULL
    OR EXISTS (
       SELECT 1 FROM pg_catalog.pg_auth_members m
       WHERE m.member IN (owner_oid,reader_oid)
          OR m.roleid IN (owner_oid,reader_oid))
    OR NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_proc f
       WHERE f.oid=pg_catalog.to_regprocedure(
         'public.read_direct_bsc_buyer_status(text)')
         AND f.proowner=owner_oid AND f.prosecdef)
    OR pg_catalog.has_function_privilege(
       'empiredb_app','public.read_direct_bsc_buyer_status(text)','EXECUTE')
    OR NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_class c
       WHERE c.oid=pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities')
         AND c.relrowsecurity AND c.relforcerowsecurity)
    OR (SELECT count(*) FROM pg_catalog.pg_policy p
       WHERE p.polrelid=pg_catalog.to_regclass(
         'public.direct_bsc_buyer_capabilities'))<>1
  THEN RAISE EXCEPTION 'DIRECT050_049_ISOLATED_READER_CONTRACT_DRIFT'; END IF;
  -- Source request table must still be migrator-owned and RLS enabled.
  IF NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_class c
       JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
       WHERE c.oid=pg_catalog.to_regclass('public.bsc_payment_requests')
         AND o.rolname='empiredb_migrator'
         AND c.relrowsecurity AND NOT c.relforcerowsecurity)
    OR (SELECT count(*) FROM pg_catalog.pg_policy p
        WHERE p.polrelid='public.bsc_payment_requests'::regclass)<>11
  THEN RAISE EXCEPTION 'DIRECT050_REQUEST_RLS_BASELINE_DRIFT'; END IF;
  -- The existing 047 guard trigger must still reject mismatched requests.
  IF NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_trigger t
       WHERE t.tgrelid='public.direct_bsc_buyer_capabilities'::regclass
         AND t.tgname='direct_bsc_buyer_capability_guard'
         AND NOT t.tgisinternal AND t.tgenabled='O'
         AND t.tgfoid=pg_catalog.to_regprocedure(
           'public.guard_direct_bsc_buyer_capability()'))
  THEN RAISE EXCEPTION 'DIRECT050_047_GUARD_TRIGGER_DRIFT'; END IF;
END
$preflight$;

-- Distinct ownership identity; never grant a login membership here.
CREATE ROLE empire_direct_checkout_status_issuer_owner
  NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS;
CREATE ROLE empire_direct_checkout_status_issuer
  NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO
  empire_direct_checkout_status_issuer_owner,
  empire_direct_checkout_status_issuer;

GRANT SELECT (
  id,fulfilment_order_id,settlement_mode,status,created_at,expires_at
) ON public.bsc_payment_requests
  TO empire_direct_checkout_status_issuer_owner;
GRANT INSERT (
  token_fingerprint,fulfilment_order_id,request_id,issued_at,expires_at
) ON public.direct_bsc_buyer_capabilities
  TO empire_direct_checkout_status_issuer_owner;

CREATE POLICY direct_bsc_status_issuer_request_select
  ON public.bsc_payment_requests
  FOR SELECT TO empire_direct_checkout_status_issuer_owner USING (true);
CREATE POLICY direct_bsc_status_issuer_capability_insert
  ON public.direct_bsc_buyer_capabilities
  FOR INSERT TO empire_direct_checkout_status_issuer_owner
  WITH CHECK (revoked_at IS NULL
    AND issued_at <= pg_catalog.statement_timestamp()
    AND expires_at > pg_catalog.statement_timestamp()
    AND expires_at <= issued_at + interval '2 hours');

CREATE FUNCTION public.issue_direct_bsc_buyer_status(
  p_digest text, p_order_id uuid, p_request_id uuid,
  p_issued_at timestamptz, p_expires_at timestamptz
) RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=''
AS $issuer$
DECLARE
  r record;
BEGIN
  IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
    OR p_order_id IS NULL OR p_request_id IS NULL
    OR p_issued_at IS NULL OR p_expires_at IS NULL
    OR p_issued_at > pg_catalog.statement_timestamp()
    OR p_expires_at <= pg_catalog.statement_timestamp()
    OR p_expires_at <= p_issued_at
    OR p_expires_at > p_issued_at + interval '2 hours'
  THEN RAISE EXCEPTION 'DIRECT050_INVALID_CAPABILITY_REQUEST'; END IF;
  SELECT id,fulfilment_order_id,settlement_mode,status,
         created_at,expires_at
    INTO r
    FROM public.bsc_payment_requests
    WHERE id=p_request_id;
  IF NOT FOUND OR r.fulfilment_order_id IS DISTINCT FROM p_order_id
     OR r.settlement_mode IS DISTINCT FROM 'direct'
     OR r.status IS DISTINCT FROM 'pending'
     OR p_issued_at < r.created_at
     OR p_expires_at > r.expires_at
  THEN RAISE EXCEPTION 'DIRECT050_PENDING_BOUND_REQUEST_REQUIRED'; END IF;
  INSERT INTO public.direct_bsc_buyer_capabilities (
    token_fingerprint,fulfilment_order_id,request_id,issued_at,expires_at
  ) VALUES (
    p_digest,p_order_id,p_request_id,p_issued_at,p_expires_at
  );
  RETURN pg_catalog.jsonb_build_object(
    'decision','created','token_fingerprint',p_digest);
END
$issuer$;
ALTER FUNCTION public.issue_direct_bsc_buyer_status(
  text,uuid,uuid,timestamptz,timestamptz
) OWNER TO empire_direct_checkout_status_issuer_owner;
REVOKE ALL ON FUNCTION public.issue_direct_bsc_buyer_status(
  text,uuid,uuid,timestamptz,timestamptz
) FROM PUBLIC,empiredb_app,empiredb_readonly;
GRANT EXECUTE ON FUNCTION public.issue_direct_bsc_buyer_status(
  text,uuid,uuid,timestamptz,timestamptz
) TO empire_direct_checkout_status_issuer;

DO $postcheck$
DECLARE
  owner_oid oid := 'empire_direct_checkout_status_issuer_owner'::regrole;
  caller_oid oid := 'empire_direct_checkout_status_issuer'::regrole;
  fun_oid oid := pg_catalog.to_regprocedure(
    'public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)');
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    WHERE m.member IN (owner_oid,caller_oid)
       OR m.roleid IN (owner_oid,caller_oid)
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.oid IN (owner_oid,caller_oid)
      AND (r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
           OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
  ) THEN RAISE EXCEPTION 'DIRECT050_ROLE_ISOLATION_FAILED'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc f
    WHERE f.oid=fun_oid AND f.proowner=owner_oid
      AND f.prosecdef AND f.provolatile='v'
  ) OR (SELECT count(*) FROM pg_catalog.pg_proc f
     CROSS JOIN LATERAL pg_catalog.aclexplode(
       COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))) a
     WHERE f.oid=fun_oid AND a.grantee=caller_oid
       AND a.privilege_type='EXECUTE' AND NOT a.is_grantable)<>1
    OR EXISTS (
      SELECT 1 FROM pg_catalog.pg_proc f
      CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))) a
      WHERE f.oid=fun_oid AND a.grantee NOT IN (owner_oid,caller_oid))
    OR pg_catalog.has_function_privilege(
      'empiredb_app',fun_oid,'EXECUTE')
    OR pg_catalog.has_function_privilege(
      'empiredb_migrator_login',fun_oid,'EXECUTE')
    OR pg_catalog.has_table_privilege(
      'empire_direct_checkout_status_issuer',
      'public.direct_bsc_buyer_capabilities','INSERT')
  THEN RAISE EXCEPTION 'DIRECT050_ISSUER_PERMISSION_SEAL_FAILED'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_policy p
      WHERE p.polrelid='public.direct_bsc_buyer_capabilities'::regclass)<>2
    OR (SELECT count(*) FROM pg_catalog.pg_policy p
      WHERE p.polrelid='public.bsc_payment_requests'::regclass)<>12
  THEN RAISE EXCEPTION 'DIRECT050_UNEXPECTED_PARENT_POLICY_DRIFT'; END IF;
END
$postcheck$;
COMMIT;
