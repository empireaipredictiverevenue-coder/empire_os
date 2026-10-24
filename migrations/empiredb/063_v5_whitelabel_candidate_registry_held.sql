-- Original EmpireDB 063: HELD V5 white-label candidate registry, NOT activation.
-- No new DB, schema-per-tenant, live Login, API, provider, billing or domain.
-- Original CRM authoritative membership still requires separate owner proof.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v5_fixture') THEN
   RAISE EXCEPTION 'V5_063_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
    AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
    AND NOT rolcreatedb AND NOT rolcreaterole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members
       WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles
                     WHERE rolname='empiredb_migrator')) THEN
   RAISE EXCEPTION 'V5_063_RESTRICTED_OWNER_REQUIRED';
 END IF;
 IF pg_catalog.to_regclass('public.empire_v5_whitelabel_candidates_held') IS NOT NULL
    OR pg_catalog.to_regclass('public.empire_v5_domain_candidates_held') IS NOT NULL THEN
   RAISE EXCEPTION 'V5_063_EXISTING_REGISTRY_REQUIRES_REVIEW';
 END IF;
END;
$guard$;
SET LOCAL ROLE empiredb_migrator;

CREATE TABLE public.empire_v5_whitelabel_candidates_held (
 tenant_id uuid PRIMARY KEY,
 display_name text NOT NULL CHECK (
   length(display_name) BETWEEN 2 AND 60
   AND display_name ~ '^[A-Za-z0-9][A-Za-z0-9 .&''()_-]*$'),
 accent_hex text NOT NULL CHECK (accent_hex ~ '^#[A-F0-9]{6}$'),
 logo_asset_digest text NOT NULL CHECK (logo_asset_digest ~ '^[a-f0-9]{64}$'),
 requested_plan text NOT NULL CHECK (
   requested_plan IN ('enterprise','scale','whale','sovereign')),
 lifecycle_state text NOT NULL DEFAULT 'PENDING_REVIEW'
   CHECK (lifecycle_state = 'PENDING_REVIEW'),
 created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 CHECK (tenant_id <> '00000000-0000-0000-0000-000000000000'::uuid)
);

CREATE TABLE public.empire_v5_domain_candidates_held (
 hostname text PRIMARY KEY CHECK (
   length(hostname) BETWEEN 4 AND 253
   AND hostname ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?){2,7}$'
   AND hostname !~ '(^|\.)xn--'
   AND hostname !~ '\.(local|internal|localhost|test|invalid|example)$'
   AND hostname !~ '\.empire-ai\.co\.uk$'
 ),
 tenant_id uuid NOT NULL REFERENCES public.empire_v5_whitelabel_candidates_held(tenant_id)
   ON DELETE RESTRICT,
 ownership_state text NOT NULL DEFAULT 'UNVERIFIED'
   CHECK (ownership_state='UNVERIFIED'),
 certificate_state text NOT NULL DEFAULT 'UNVERIFIED'
   CHECK (certificate_state='UNVERIFIED'),
 dns_state text NOT NULL DEFAULT 'UNVERIFIED'
   CHECK (dns_state='UNVERIFIED'),
 activation_state text NOT NULL DEFAULT 'HELD'
   CHECK (activation_state='HELD'),
 created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

-- Owner-review only. No runtime role/LOGIN or public policies.
ALTER TABLE public.empire_v5_whitelabel_candidates_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_v5_whitelabel_candidates_held FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_v5_domain_candidates_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_v5_domain_candidates_held FORCE ROW LEVEL SECURITY;
CREATE POLICY empire_v5_owner_brand_held_063
 ON public.empire_v5_whitelabel_candidates_held FOR ALL TO empiredb_migrator
 USING (true) WITH CHECK (true);
CREATE POLICY empire_v5_owner_domain_held_063
 ON public.empire_v5_domain_candidates_held FOR ALL TO empiredb_migrator
 USING (true) WITH CHECK (true);
REVOKE ALL ON TABLE public.empire_v5_whitelabel_candidates_held FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_v5_domain_candidates_held FROM PUBLIC;
COMMENT ON TABLE public.empire_v5_domain_candidates_held IS
 'HELD. Domain claims are unverified candidates, not DNS/TLS, tenancy authority or router activation.';
COMMENT ON TABLE public.empire_v5_whitelabel_candidates_held IS
 'HELD. Candidate branding only. No canonical CRM membership, paid subscription or white-label activation is proved.';
COMMIT;
