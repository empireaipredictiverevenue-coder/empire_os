-- EmpireDB 042 — first-party invited CRM login credentials.
-- PREPARED ONLY: requires separately scoped founder approval.
-- No user created, password initialized, login role granted or HTTP endpoint activated.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','crm_login_fixture','crm_membership_fixture') THEN
    RAISE EXCEPTION 'invalid EmpireDB CRM login target';
 END IF;
 IF pg_catalog.to_regclass('public.empire_crm_login_credentials') IS NOT NULL THEN
    RAISE EXCEPTION 'CRM credential table exists: reconcile, do not overwrite';
 END IF;
 IF pg_catalog.to_regclass('public.empire_crm_tenant_memberships') IS NULL
    OR pg_catalog.to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NULL
 THEN
    RAISE EXCEPTION 'canonical CRM membership migration 041 required';
 END IF;
END;
$guard$;
CREATE TABLE public.empire_crm_login_credentials (
    subject text PRIMARY KEY CHECK (subject ~ '^[A-Za-z0-9:@._/-]{1,128}$'),
    login_email text NOT NULL UNIQUE CHECK (
        login_email = lower(btrim(login_email))
        AND length(login_email) BETWEEN 5 AND 254
        AND position('@' in login_email)>1
    ),
    password_salt bytea NOT NULL CHECK (octet_length(password_salt)=32),
    password_digest bytea NOT NULL CHECK (octet_length(password_digest)=64),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','active','disabled')),
    evidence_ref text NOT NULL
        CHECK (length(btrim(evidence_ref)) BETWEEN 1 AND 512),
    password_change_required boolean NOT NULL DEFAULT true,
    failed_attempts integer NOT NULL DEFAULT 0
        CHECK (failed_attempts BETWEEN 0 AND 5),
    locked_until timestamptz,
    verified_at timestamptz NOT NULL,
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.empire_crm_login_credentials ENABLE ROW LEVEL SECURITY;
-- Session identity is verified separately from SET ROLE; an unbound shared
-- EmpireDB application session can never become the CRM login principal.
CREATE POLICY crm_auth_login_read ON public.empire_crm_login_credentials
  FOR SELECT TO PUBLIC USING (session_user = 'empire_crm_auth_login');
CREATE POLICY crm_auth_login_lockout ON public.empire_crm_login_credentials
  FOR UPDATE TO PUBLIC
  USING (session_user = 'empire_crm_auth_login')
  WITH CHECK (session_user = 'empire_crm_auth_login');
REVOKE ALL ON TABLE public.empire_crm_login_credentials FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_crm_login_credentials FROM
    empiredb_app, empiredb_readonly, empiredb_tenant_reader,
    empire_revenue_crm_reader;
COMMENT ON TABLE public.empire_crm_login_credentials IS
 'Invite-only first-party CRM credentials; locked down until separate dedicated login approval.';
COMMIT;
