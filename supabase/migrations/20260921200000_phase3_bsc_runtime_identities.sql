-- Phase 3 BSC payment runtime identities.
-- Passwords remain NULL until explicitly provisioned out of band.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_payment_approver_login'
  ) THEN
    CREATE ROLE empire_payment_approver_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_bsc_verifier_login'
  ) THEN
    CREATE ROLE empire_bsc_verifier_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_payment_approver_login PASSWORD NULL;
ALTER ROLE empire_bsc_verifier_login PASSWORD NULL;

GRANT empire_payment_approver TO empire_payment_approver_login;
GRANT empire_bsc_verifier TO empire_bsc_verifier_login;

ALTER ROLE empire_payment_approver_login
  SET statement_timeout='15s';
ALTER ROLE empire_payment_approver_login
  SET idle_in_transaction_session_timeout='30s';
ALTER ROLE empire_bsc_verifier_login
  SET statement_timeout='15s';
ALTER ROLE empire_bsc_verifier_login
  SET idle_in_transaction_session_timeout='30s';

COMMIT;
