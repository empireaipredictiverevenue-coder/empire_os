#!/usr/bin/env bash
set -euo pipefail

[[ "$(id -u)" -eq 0 ]] || { echo "run as root"; exit 1; }

if [[ "${1:-}" == "--intelligence-materializer" ]]; then
  exec /srv/empire_os/.venv/bin/python /srv/empire_os/scripts/provision_intelligence_materializer.py --apply
fi

runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -d empiredb <<'SQL'
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY[
    'empire_outbound_approver',
    'empire_outbound_sender',
    'empire_reply_ingest',
    'empire_closer_observer',
    'empire_closer_approver',
    'empire_payment_approver',
    'empire_bsc_verifier',
    'empire_escrow_verifier',
    'empire_commercial_approver',
    'empire_outcome_recorder',
    'empire_revenue_recognizer',
    'empire_closer_planner',
    'empire_conversation_ingest',
    'empire_conversation_reader',
    'empire_revenue_exchange_ingest',
    'empire_revenue_exchange_reader',
    'empire_owned_campaign_ingest',
    'empire_a2a_identity_nonce_writer',
    'empire_a2a_intent_writer',
    'empiredb_tenant_reader'
  ] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT', r);
    END IF;
  END LOOP;
END $$;

GRANT USAGE ON SCHEMA public TO
  empire_outbound_approver,
  empire_outbound_sender,
  empire_reply_ingest,
  empire_closer_observer,
  empire_closer_approver,
  empire_payment_approver,
  empire_bsc_verifier,
  empire_escrow_verifier,
  empire_commercial_approver,
  empire_outcome_recorder,
  empire_revenue_recognizer,
  empire_closer_planner,
  empire_conversation_ingest,
  empire_conversation_reader,
  empire_revenue_exchange_ingest,
  empire_revenue_exchange_reader,
  empiredb_tenant_reader;
GRANT empiredb_tenant_reader TO empiredb_migrator;
SQL

echo '{"runtime_capability_roles":"ready","verified":true}'
