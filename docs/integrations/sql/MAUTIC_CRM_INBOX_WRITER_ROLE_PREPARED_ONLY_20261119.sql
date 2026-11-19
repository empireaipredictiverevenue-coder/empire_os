-- EmpireOS Smart CRM / Mautic inbox role bootstrap. PREPARED ONLY, DO NOT APPLY.
-- Separate founder + DBA authority and verified backup/rollback required.
-- Creates exactly one NOLOGIN/NOINHERIT role. No tenant login, database
-- table, network endpoint, credentials, customer data or sending is created.
-- Must be executed by authorised DBA operator (CREATE ROLE + SET ROLE migrator).
BEGIN;

DO $preflight$
BEGIN
  IF current_database() NOT IN ('empiredb','mautic_crm_inbox_fixture') THEN
    RAISE EXCEPTION 'wrong canonical EmpireDB/Mautic fixture database';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_mautic_crm_inbox_writer'
  ) THEN
    RAISE EXCEPTION 'Mautic inbox role exists; reconcile before provisioning';
  END IF;
  IF pg_catalog.to_regclass('public.empire_crm_mautic_event_inbox') IS NOT NULL THEN
    RAISE EXCEPTION 'Mautic inbox schema already exists; reconcile first';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator'
      AND NOT rolcanlogin AND NOT rolsuper AND NOT rolinherit
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_revenue_crm_reader'
      AND NOT rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'canonical CRM migrator / reader ownership missing';
  END IF;
  IF pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
    OR NOT EXISTS (
      SELECT 1
      FROM pg_catalog.pg_proc p
      JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
      WHERE p.oid='public.empire_current_tenant_id()'::pg_catalog.regprocedure
      AND p.prosecdef AND p.provolatile='s'
      AND r.rolname='empiredb_migrator'
    )
  THEN
    RAISE EXCEPTION 'canonical security-definer tenant binding required';
  END IF;
END;
$preflight$;

CREATE ROLE empire_mautic_crm_inbox_writer
  NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS PASSWORD NULL;

-- In live EmpireDB, public is owned by pg_database_owner, while the
-- empiredb_migrator role has USAGE/CREATE but NO GRANT OPTION. The
-- authenticated authorised DBA/database owner must perform this GRANT
-- before entering the separately controlled inbox migration. Switching
-- to migrator would fail and leave no usable writer schema privilege.
-- This role receives NO permissions on CRM tables or any LOGIN membership.
GRANT USAGE ON SCHEMA public TO empire_mautic_crm_inbox_writer;

DO $postcheck$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_mautic_crm_inbox_writer'
      AND NOT rolcanlogin AND NOT rolinherit
      AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
      AND NOT rolreplication AND NOT rolbypassrls
  ) OR NOT pg_catalog.has_schema_privilege(
    'empire_mautic_crm_inbox_writer', 'public', 'USAGE'
  )
  THEN
    RAISE EXCEPTION 'writer bootstrap privilege postcheck failed';
  END IF;
  IF pg_catalog.to_regclass('public.empire_crm_login_credentials') IS NOT NULL
  THEN
    IF pg_catalog.has_table_privilege(
      'empire_mautic_crm_inbox_writer',
      'public.empire_crm_login_credentials', 'SELECT'
    ) THEN
      RAISE EXCEPTION 'writer has unexpected login credentials privilege';
    END IF;
  END IF;
END;
$postcheck$;

COMMIT;
