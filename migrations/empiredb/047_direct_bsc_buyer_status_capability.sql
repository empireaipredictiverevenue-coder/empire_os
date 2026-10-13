-- HELD / NOT APPROVED FOR PRODUCTION.
-- EmpireDB 047: sealed one-time direct BSC buyer capability register.
-- Creates NO login, NO function, NO service admission, NO payment permission.
-- Must be independently approved before any migration invocation.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $preflight$
BEGIN
  IF current_database() NOT IN ('empiredb', 'direct_bsc_capability_fixture') THEN
    RAISE EXCEPTION 'DIRECT047_WRONG_DATABASE';
  END IF;
  IF current_user <> 'empiredb_migrator' THEN
    RAISE EXCEPTION 'DIRECT047_WRONG_MIGRATOR';
  END IF;
  -- Mirror the strict read-only preflight inside the same migration
  -- transaction. Preserve the existing intentional tenant-reader inheritance;
  -- NEVER allow extra role memberships or any financial-role inheritance.
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.rolname='empiredb_migrator'
      AND NOT r.rolcanlogin AND r.rolinherit AND NOT r.rolsuper
      AND NOT r.rolcreatedb AND NOT r.rolcreaterole
      AND NOT r.rolreplication AND NOT r.rolbypassrls
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.rolname='empiredb_tenant_reader'
      AND NOT r.rolcanlogin AND NOT r.rolinherit AND NOT r.rolsuper
      AND NOT r.rolcreatedb AND NOT r.rolcreaterole
      AND NOT r.rolreplication AND NOT r.rolbypassrls
  ) OR (
    SELECT count(*) FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles member ON member.oid=m.member
    WHERE member.rolname='empiredb_migrator'
  ) <> 1 OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles member ON member.oid=m.member
    JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
    WHERE member.rolname='empiredb_migrator'
      AND granted.rolname='empiredb_tenant_reader'
      AND m.inherit_option AND m.set_option AND NOT m.admin_option
      AND pg_catalog.pg_has_role(
        'empiredb_migrator',granted.oid,'USAGE'
      )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles member ON member.oid=m.member
    WHERE member.rolname='empiredb_tenant_reader'
  ) THEN
    RAISE EXCEPTION 'DIRECT047_UNREVIEWED_MIGRATOR_INHERITED_AUTHORITY';
  END IF;
  IF pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities') IS NOT NULL THEN
    RAISE EXCEPTION 'DIRECT047_CAPABILITY_REGISTER_EXISTS_RECONCILE';
  END IF;
  IF pg_catalog.to_regclass('public.fulfilment_orders') IS NULL
     OR pg_catalog.to_regclass('public.bsc_payment_requests') IS NULL
     OR NOT pg_catalog.has_table_privilege(
       current_user, 'public.fulfilment_orders', 'REFERENCES'
     )
     OR NOT pg_catalog.has_table_privilege(
       current_user, 'public.bsc_payment_requests', 'REFERENCES'
     )
     OR NOT pg_catalog.has_table_privilege(
       current_user, 'public.fulfilment_orders', 'SELECT'
     )
     OR NOT pg_catalog.has_table_privilege(
       current_user, 'public.bsc_payment_requests', 'SELECT'
     )
  THEN
    RAISE EXCEPTION 'DIRECT047_CANONICAL_PAYMENT_FOREIGN_KEYS_UNAVAILABLE';
  END IF;
END;
$preflight$;

CREATE TABLE public.direct_bsc_buyer_capabilities (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  -- HMAC-SHA256 fingerprint only, never store plaintext bearer or HMAC key.
  token_fingerprint text NOT NULL UNIQUE
    CHECK (token_fingerprint ~ '^[0-9a-f]{64}$'),
  fulfilment_order_id uuid NOT NULL
    REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  request_id uuid NOT NULL
    REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
  issued_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (expires_at > issued_at),
  CHECK (expires_at <= issued_at + interval '48 hours'),
  CHECK (revoked_at IS NULL OR revoked_at >= issued_at)
);

-- Identity recovery requires explicit revocation first; no two simultaneously
-- unrevoked capability bindings may point at the same order/request.
CREATE UNIQUE INDEX direct_bsc_buyer_capabilities_active_order_uidx
  ON public.direct_bsc_buyer_capabilities(fulfilment_order_id)
  WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX direct_bsc_buyer_capabilities_active_request_uidx
  ON public.direct_bsc_buyer_capabilities(request_id)
  WHERE revoked_at IS NULL;

-- SECURITY DEFINER is required because future issuer role must not receive
-- unrestricted SELECT on buyer, payment or order tables. This trigger performs
-- linkage checks only; no endpoint or role is granted EXECUTE.
CREATE FUNCTION public.guard_direct_bsc_buyer_capability()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $guard$
DECLARE
  r public.bsc_payment_requests%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF OLD.revoked_at IS NOT NULL
       OR NEW.revoked_at IS NULL
       OR (pg_catalog.to_jsonb(NEW) - 'revoked_at')
          IS DISTINCT FROM (pg_catalog.to_jsonb(OLD) - 'revoked_at')
    THEN
      RAISE EXCEPTION 'DIRECT047_CAPABILITY_IMMUTABLE_EXCEPT_FIRST_REVOCATION';
    END IF;
  END IF;
  SELECT * INTO r FROM public.bsc_payment_requests WHERE id=NEW.request_id;
  SELECT * INTO o FROM public.fulfilment_orders WHERE id=NEW.fulfilment_order_id;
  IF NOT FOUND OR r.id IS NULL
     OR r.fulfilment_order_id IS DISTINCT FROM NEW.fulfilment_order_id
     OR r.buyer_id IS DISTINCT FROM o.buyer_id
     OR r.settlement_mode IS DISTINCT FROM 'direct'
     OR (TG_OP = 'INSERT' AND r.status NOT IN ('pending','approved'))
     OR o.state NOT IN ('accepted', 'invoiced', 'delivered', 'confirmed')
     OR NEW.issued_at < r.created_at
     OR NEW.expires_at > r.expires_at
  THEN
    RAISE EXCEPTION 'DIRECT047_CAPABILITY_BINDING_NOT_VERIFIED';
  END IF;
  RETURN NEW;
END;
$guard$;

REVOKE ALL ON FUNCTION public.guard_direct_bsc_buyer_capability() FROM PUBLIC;
CREATE TRIGGER direct_bsc_buyer_capability_guard
BEFORE INSERT OR UPDATE ON public.direct_bsc_buyer_capabilities
FOR EACH ROW EXECUTE FUNCTION public.guard_direct_bsc_buyer_capability();

ALTER TABLE public.direct_bsc_buyer_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.direct_bsc_buyer_capabilities FORCE ROW LEVEL SECURITY;
-- IMPORTANT: No RLS policy, login role, role membership, GRANT, SQL RPC,
-- or provider credential is introduced by this migration. Deny by default.
REVOKE ALL ON TABLE public.direct_bsc_buyer_capabilities FROM PUBLIC;

COMMENT ON TABLE public.direct_bsc_buyer_capabilities IS
  'HELD: buyer-held HMAC fingerprint only. Sealed until independently approved private issuer, reader, and scope-limited RLS/role authority. Never treat order UUID as access.';

DO $postcheck$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::pg_catalog.regclass
      AND c.relrowsecurity AND c.relforcerowsecurity
      AND r.rolname='empiredb_migrator'
  ) THEN
    RAISE EXCEPTION 'DIRECT047_SEALED_RLS_OR_OWNER_MISMATCH';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_class c
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))
    ) acl
    WHERE c.oid='public.direct_bsc_buyer_capabilities'::pg_catalog.regclass
      AND acl.grantee=0
  ) THEN
    RAISE EXCEPTION 'DIRECT047_PUBLIC_ACL_UNSAFE';
  END IF;
END;
$postcheck$;
COMMIT;
