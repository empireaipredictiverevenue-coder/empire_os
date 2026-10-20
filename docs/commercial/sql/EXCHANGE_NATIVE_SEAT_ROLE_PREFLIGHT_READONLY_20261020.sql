-- READ ONLY, catalog metadata only. Never SELECT customer, financial or
-- payment data. No secrets, credentials, wallet, recipient or row values.
-- Owner must execute through their existing approved DBA terminal.
-- This report is an audit hint, NOT an entitlement, RLS proof or grant.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '1s';
WITH required(table_name, column_name) AS (
 VALUES
 ('buyers','id'),('buyers','org_id'),('buyers','commercial_activation_state'),
 ('fulfilment_orders','id'),('fulfilment_orders','buyer_id'),
 ('fulfilment_orders','commercial_payload'),('fulfilment_orders','price_cents'),
 ('fulfilment_orders','quantity'),('fulfilment_orders','state'),
 ('bsc_payment_requests','id'),('bsc_payment_requests','buyer_id'),
 ('bsc_payment_requests','fulfilment_order_id'),
 ('bsc_payment_requests','approved_at'),('bsc_payment_requests','approved_by'),
 ('bsc_payment_requests','commercial_terms_sha256'),
 ('bsc_payment_requests','settlement_mode'),
 ('bsc_payment_requests','min_block_number'),
 ('bsc_payment_requests','treasury_address'),
 ('bsc_payment_requests','payer_address'),
 ('bsc_payment_requests','amount_usdt'),
 ('bsc_payment_evidence','id'),('bsc_payment_evidence','request_id'),
 ('bsc_payment_evidence','fulfilment_order_id'),
 ('bsc_payment_evidence','block_number'),
 ('bsc_payment_evidence','confirmations'),
 ('bsc_payment_evidence','chain_id'),
 ('bsc_payment_evidence','token_contract'),
 ('bsc_payment_evidence','transaction_hash'),
 ('bsc_payment_evidence','amount_raw'),
 ('bsc_payment_evidence','treasury_address'),
 ('bsc_payment_evidence','sender_address')
), inspected AS (
 SELECT r.table_name, r.column_name,
        c.oid IS NOT NULL AS relation_exists,
        a.attnum IS NOT NULL AS column_exists,
        c.relrowsecurity AS rls_enabled,
        c.relforcerowsecurity AS rls_forced
 FROM required r
 LEFT JOIN pg_catalog.pg_namespace n ON n.nspname='public'
 LEFT JOIN pg_catalog.pg_class c
   ON c.relnamespace=n.oid AND c.relname=r.table_name
      AND c.relkind IN ('r','p')
 LEFT JOIN pg_catalog.pg_attribute a
   ON a.attrelid=c.oid AND a.attname=r.column_name
      AND a.attnum>0 AND NOT a.attisdropped
), roles AS (
 SELECT
  EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
    AS migrator_role_exists,
  EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_bsc_verifier')
    AS bsc_verifier_role_exists,
  EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_direct_checkout_status_reader')
    AS direct_status_reader_role_exists,
  EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_revenue_crm_reader')
    AS crm_reader_role_exists,
  EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_exchange_seat_finance_reader')
    AS proposed_exchange_seat_finance_role_already_exists
)
SELECT pg_catalog.jsonb_build_object(
 'report_schema','empire.exchange.seat_catalog_preflight.v1',
 'production_database_name_expected',current_database()='empiredb',
 'current_connection_is_read_only',current_setting('transaction_read_only')='on',
 'native_source_relations_all_exist',
   NOT EXISTS(SELECT 1 FROM inspected WHERE NOT relation_exists),
 'native_required_source_columns_all_exist',
   NOT EXISTS(SELECT 1 FROM inspected WHERE NOT column_exists),
 'native_source_relations_with_rls_enabled_count',
   (SELECT count(DISTINCT table_name)
    FROM inspected WHERE rls_enabled IS TRUE),
 'native_source_relations_with_rls_forced_count',
   (SELECT count(DISTINCT table_name)
    FROM inspected WHERE rls_forced IS TRUE),
 'proposed_seat_membership_table_absent',
   pg_catalog.to_regclass('public.exchange_seat_memberships') IS NULL,
 'proposed_invoice_cycle_table_absent',
   pg_catalog.to_regclass('public.exchange_seat_invoice_cycles') IS NULL,
 'migrator_role_exists',roles.migrator_role_exists,
 'bsc_verifier_role_exists',roles.bsc_verifier_role_exists,
 'direct_status_reader_role_exists',roles.direct_status_reader_role_exists,
 'crm_reader_role_exists',roles.crm_reader_role_exists,
 'proposed_exchange_seat_finance_role_already_exists',
   roles.proposed_exchange_seat_finance_role_already_exists,
 'finance_role_reader_grants_proven',false,
 'tenant_rls_identity_proven',false,
 'settlement_authenticated',false,
 'entitlement_activation_authorized',false,
 'schema_migration_authorized',false,
 'missing_required_column_names',
   COALESCE((SELECT pg_catalog.jsonb_agg(
       i.table_name||'.'||i.column_name ORDER BY i.table_name,i.column_name)
     FROM inspected i WHERE NOT i.column_exists),'[]'::jsonb)
) AS preflight_review
FROM roles;
ROLLBACK;
