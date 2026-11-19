-- DBA-ONLY PREPARED ROLLBACK. NO AUTOMATIC EXECUTION IN EMPIREDB.
-- Safe for an EMPTY unused Mautic review inbox only. Existing production
-- evidence/tenant writer logins must be preserved and separately reconciled.
-- This deliberately refuses data loss, dangling tenant members or other
-- objects owned by a role. Never use CASCADE or DROP OWNED BY.
BEGIN;
SET LOCAL statement_timeout='10000ms';
SET LOCAL lock_timeout='2000ms';

DO $preflight$
BEGIN
  IF current_database() NOT IN ('empiredb','mautic_crm_inbox_fixture') THEN
    RAISE EXCEPTION 'wrong canonical EmpireDB/fixture database';
  END IF;
  IF pg_catalog.to_regclass('public.empire_crm_mautic_event_inbox') IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname='empire_mautic_crm_inbox_writer'
        AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
    )
  THEN
    RAISE EXCEPTION 'writer or inbox absent: reconcile, do not drop';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
    WHERE r.rolname='empire_mautic_crm_inbox_writer'
  ) THEN
    RAISE EXCEPTION 'Mautic writer has member logins; do not drop';
  END IF;
  IF EXISTS (SELECT 1 FROM public.empire_crm_mautic_event_inbox LIMIT 1) THEN
    RAISE EXCEPTION 'Mautic inbox contains evidence; preserve and reconcile';
  END IF;
  IF pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
     OR NOT EXISTS (
       SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
     )
  THEN
    RAISE EXCEPTION 'canonical migrator/tenant function unavailable';
  END IF;
END;
$preflight$;

-- Database object is owned by the same migrator who created the prepared
-- review-only inbox. The role itself stays unprivileged/no-login.
SET LOCAL ROLE empiredb_migrator;
DROP TABLE public.empire_crm_mautic_event_inbox RESTRICT;
REVOKE EXECUTE ON FUNCTION public.empire_current_tenant_id()
  FROM empire_mautic_crm_inbox_writer;
RESET ROLE;

-- public is pg_database_owner in production; only the authorised DBA or
-- database/schema owner may revoke this grant and drop the role.
REVOKE USAGE ON SCHEMA public FROM empire_mautic_crm_inbox_writer;
DROP ROLE empire_mautic_crm_inbox_writer;

DO $postcheck$
BEGIN
  IF pg_catalog.to_regclass('public.empire_crm_mautic_event_inbox') IS NOT NULL
     OR EXISTS (
       SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname='empire_mautic_crm_inbox_writer'
     )
  THEN
    RAISE EXCEPTION 'rollback incomplete, transaction must revert';
  END IF;
END;
$postcheck$;
COMMIT;
