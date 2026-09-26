-- Empire Phase 3E dedicated runtime LOGIN identities.
-- Safe default: roles are LOGIN-capable but have no password until provisioned out of band.
BEGIN;

DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY[
    'empire_outbound_approver_login',
    'empire_outbound_sender_login',
    'empire_reply_ingest_login',
    'empire_closer_approver_login'
  ] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format(
        'CREATE ROLE %I LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5',
        r
      );
    END IF;
  END LOOP;
END $$;

GRANT empire_outbound_approver TO empire_outbound_approver_login;
GRANT empire_outbound_sender TO empire_outbound_sender_login;
GRANT empire_reply_ingest TO empire_reply_ingest_login;
GRANT empire_closer_approver TO empire_closer_approver_login;

REVOKE empire_outbound_sender,empire_reply_ingest,empire_closer_approver
  FROM empire_outbound_approver_login;
REVOKE empire_outbound_approver,empire_reply_ingest,empire_closer_approver
  FROM empire_outbound_sender_login;
REVOKE empire_outbound_approver,empire_outbound_sender,empire_closer_approver
  FROM empire_reply_ingest_login;
REVOKE empire_outbound_approver,empire_outbound_sender,empire_reply_ingest
  FROM empire_closer_approver_login;

ALTER ROLE empire_outbound_approver_login SET statement_timeout='15s';
ALTER ROLE empire_outbound_sender_login SET statement_timeout='15s';
ALTER ROLE empire_reply_ingest_login SET statement_timeout='15s';
ALTER ROLE empire_closer_approver_login SET statement_timeout='15s';
ALTER ROLE empire_outbound_approver_login SET idle_in_transaction_session_timeout='30s';
ALTER ROLE empire_outbound_sender_login SET idle_in_transaction_session_timeout='30s';
ALTER ROLE empire_reply_ingest_login SET idle_in_transaction_session_timeout='30s';
ALTER ROLE empire_closer_approver_login SET idle_in_transaction_session_timeout='30s';

COMMENT ON ROLE empire_outbound_approver_login IS 'Dedicated Phase 3E login; membership only in empire_outbound_approver. Password provisioned out of band.';
COMMENT ON ROLE empire_outbound_sender_login IS 'Dedicated Phase 3E login; membership only in empire_outbound_sender. Password provisioned out of band.';
COMMENT ON ROLE empire_reply_ingest_login IS 'Dedicated Phase 3E login; membership only in empire_reply_ingest. Password provisioned out of band.';
COMMENT ON ROLE empire_closer_approver_login IS 'Dedicated Phase 3E login; membership only in empire_closer_approver. Password provisioned out of band.';

COMMIT;
