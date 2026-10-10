-- EmpireOS CRM pilot — identity role authority, PREPARED / NOT APPROVED.
-- NOT a new schema migration. No production execution permitted without
-- separate founder approval of these exact grants and roles.
-- Creates two NOLOGIN roles: no password, no session authentication.
-- Does NOT create customers, tenant reader logins, bindings, email or HTTP.
BEGIN;

DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb','crm_membership_fixture') THEN
    RAISE EXCEPTION 'canonical EmpireDB CRM identity roles only';
  END IF;
  IF pg_catalog.to_regclass('public.empire_crm_login_credentials') IS NULL
     OR pg_catalog.to_regclass('public.empire_crm_tenant_memberships') IS NULL
     OR pg_catalog.to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NULL
  THEN
    RAISE EXCEPTION 'deployed 041 and 042 prerequisites required';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname IN ('empire_crm_auth_login', 'empire_crm_membership_login')
  ) THEN
    RAISE EXCEPTION 'CRM dedicated identity role collision; reconcile first';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'canonical EmpireDB migrator role missing';
  END IF;

  CREATE ROLE empire_crm_auth_login
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS PASSWORD NULL;
  CREATE ROLE empire_crm_membership_login
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS PASSWORD NULL;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

GRANT USAGE ON SCHEMA public
  TO empire_crm_auth_login, empire_crm_membership_login;

-- Human login/password validation and atomic invitation consumption need
-- exact SELECT plus only these per-account mutable columns.
GRANT SELECT ON TABLE public.empire_crm_login_credentials
  TO empire_crm_auth_login;
GRANT UPDATE (
  failed_attempts, locked_until, last_login_at, updated_at,
  password_salt, password_digest, status,
  password_change_required, invitation_token_hash,
  invitation_redeemed_at
) ON TABLE public.empire_crm_login_credentials
  TO empire_crm_auth_login;

-- One exact active membership read; NO direct membership table access.
GRANT EXECUTE ON FUNCTION public.empire_crm_read_member(text,uuid)
  TO empire_crm_membership_login;

COMMIT;
