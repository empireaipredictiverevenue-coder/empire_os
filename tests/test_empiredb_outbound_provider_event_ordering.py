from pathlib import Path

from test_empiredb_materializer_bootstrap import execute
from test_empiredb_outbound_provider_event_ingest import bootstrap


MIGRATION = Path(
    "migrations/empiredb/031_outbound_provider_event_ordering.sql"
)


def test_transient_bounce_after_delivery_downgrades_to_failed(execute):
    bootstrap(execute)
    execute("empiredb", MIGRATION.read_text())
    execute("empiredb", r"""
SET ROLE empiredb_migrator;
INSERT INTO public.outbound_intents(
    id,normalized_recipient,status
) VALUES (
    '00000000-0000-0000-0000-000000000031',
    'transient@example.com',
    'sent'
);
RESET ROLE;

SET ROLE empire_reply_ingest;
SELECT public.record_outbound_provider_event(
    '00000000-0000-0000-0000-000000000031',
    'delivered',
    'msg-31',
    'transient@example.com',
    false,
    '{}'::jsonb
);
SELECT public.record_outbound_provider_event(
    '00000000-0000-0000-0000-000000000031',
    'bounced',
    'msg-31',
    'transient@example.com',
    false,
    '{"bounce":{"type":"Transient","subType":"General"}}'::jsonb
);
RESET ROLE;

SET ROLE empiredb_migrator;
DO $$
DECLARE v_status text;
BEGIN
  SELECT status INTO v_status
  FROM public.outbound_intents
  WHERE id='00000000-0000-0000-0000-000000000031';
  IF v_status <> 'failed' THEN
    RAISE EXCEPTION 'expected failed after transient bounce, got %', v_status;
  END IF;
END $$;
RESET ROLE;
""")


def test_late_delivered_event_cannot_resurrect_failed(execute):
    bootstrap(execute)
    execute("empiredb", MIGRATION.read_text())
    execute("empiredb", r"""
SET ROLE empiredb_migrator;
INSERT INTO public.outbound_intents(
    id,normalized_recipient,status
) VALUES (
    '00000000-0000-0000-0000-000000000032',
    'ordering@example.com',
    'sent'
);
RESET ROLE;

SET ROLE empire_reply_ingest;
SELECT public.record_outbound_provider_event(
    '00000000-0000-0000-0000-000000000032',
    'bounced',
    'msg-32',
    'ordering@example.com',
    false,
    '{}'::jsonb
);
SELECT public.record_outbound_provider_event(
    '00000000-0000-0000-0000-000000000032',
    'delivered',
    'msg-32',
    'ordering@example.com',
    false,
    '{}'::jsonb
);
RESET ROLE;

SET ROLE empiredb_migrator;
DO $$
DECLARE v_status text;
BEGIN
  SELECT status INTO v_status
  FROM public.outbound_intents
  WHERE id='00000000-0000-0000-0000-000000000032';
  IF v_status <> 'failed' THEN
    RAISE EXCEPTION 'late delivered resurrected failed intent: %', v_status;
  END IF;
END $$;
RESET ROLE;
""")


def test_migration_reconciles_existing_delivered_then_bounced(execute):
    bootstrap(execute)
    execute("empiredb", r"""
SET ROLE empiredb_migrator;
INSERT INTO public.outbound_intents(
    id,normalized_recipient,status
) VALUES (
    '00000000-0000-0000-0000-000000000033',
    'reconcile@example.com',
    'delivered'
);
INSERT INTO public.outbound_events(
    intent_id,event_type,actor,provider_message_id,occurred_at
) VALUES
(
    '00000000-0000-0000-0000-000000000033',
    'delivered',
    'resend_webhook',
    'msg-33',
    clock_timestamp()-interval '10 seconds'
),
(
    '00000000-0000-0000-0000-000000000033',
    'bounced',
    'resend_webhook',
    'msg-33',
    clock_timestamp()
);
RESET ROLE;
""")
    execute("empiredb", MIGRATION.read_text())
    execute("empiredb", r"""
SET ROLE empiredb_migrator;
DO $$
DECLARE v_status text;
BEGIN
  SELECT status INTO v_status
  FROM public.outbound_intents
  WHERE id='00000000-0000-0000-0000-000000000033';
  IF v_status <> 'failed' THEN
    RAISE EXCEPTION 'historical state was not reconciled: %', v_status;
  END IF;
END $$;
RESET ROLE;
""")


def test_migration_does_not_expand_suppression_or_authority():
    text = MIGRATION.read_text().lower()
    inherited = Path(
        "migrations/empiredb/024_outbound_provider_event_ingest.sql"
    ).read_text().lower()

    assert text.count(
        "insert into public.outbound_suppressions"
    ) == inherited.count(
        "insert into public.outbound_suppressions"
    )
    assert "grant " not in text
    assert "create role" not in text
    assert "daily_cap" not in text
    assert "recognize_bsc_revenue" not in text
    assert "propose_bsc_payment_request" not in text
    assert "approve_bsc_payment_request" not in text
