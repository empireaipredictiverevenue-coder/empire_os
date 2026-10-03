from pathlib import Path


MIGRATION = Path(
    "migrations/empiredb/"
    "033_reply_conversation_canonicalization.sql"
)

WEBHOOK = Path("empire_os/resend_webhook_app.py")


def sql():
    return MIGRATION.read_text()


def test_033_is_atomic_existing_reply_upgrade():
    source = sql()

    assert "CREATE OR REPLACE FUNCTION public.ingest_outbound_reply" in source
    assert "SECURITY INVOKER" in source
    assert "public.outbound_replies" in source
    assert "public.empire_conversations" in source
    assert "public.empire_conversation_events" in source
    assert "'email.received'" in source


def test_033_requires_real_provider_hash():
    source = sql()

    assert "payload_sha256" in source
    assert "provider event payload mismatch" in source
    assert "'provider','resend'" in source
    assert "'untrusted_content',true" in source
    assert "'executable',false" in source


def test_033_preserves_non_revenue_truth():
    source = sql()

    assert "'actual_revenue',false" in source

    forbidden = (
        "approve_bsc_payment_request",
        "record_bsc_payment_evidence",
        "commercial_terms_approve",
        "fulfilment_order",
    )

    for token in forbidden:
        assert token not in source


def test_033_bounds_reply_ingest_rls_to_email_intent():
    source = sql()

    assert (
        "reply_ingest_email_conversation_insert"
        in source
    )

    assert "channel = 'email'" in source
    assert "outbound_intent_id IS NOT NULL" in source

    assert (
        "GRANT SELECT, INSERT, UPDATE"
        in source
    )

    assert (
        "GRANT SELECT, INSERT"
        in source
    )


def test_033_has_one_email_conversation_per_intent():
    source = sql()

    assert (
        "uq_empire_email_conversation_outbound_intent"
        in source
    )


def test_webhook_hashes_exact_raw_request_bytes():
    source = WEBHOOK.read_text()

    assert (
        "hashlib.sha256(raw_bytes).hexdigest()"
        in source
    )

    assert '"payload_sha256": payload_sha256' in source
    assert '"executable": False' in source
