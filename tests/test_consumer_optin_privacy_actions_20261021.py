"""Synthetic-only privacy-action transaction contract.

The actual PostgreSQL ephemeral lifecycle remains a separate required test.
No customer data, actual provider webhook, or production mutation.
"""
from datetime import datetime, timezone

from empire_os.consumer_optin_postgres_repository import ConsumerPostgresRepository
from tests.test_consumer_optin_postgres_repository_20261020 import Factory, H1, H2

NOW = datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc)


def statements(connection):
    return "\n".join(sql for sql, _ in connection.statements)


def test_unapproved_private_writer_never_opens_connection():
    factory = Factory("pending")
    repo = ConsumerPostgresRepository(connection_factory=factory)
    assert repo.apply_verified_privacy_action(
        lookup=H1, action="bounce", evidence_hmac=H2, checked_at=NOW
    ) is False
    assert factory.calls == []


def test_validated_bounce_requires_suppression_token_revocation_and_audit():
    factory = Factory("pending")
    repo = ConsumerPostgresRepository(
        connection_factory=factory, approved_custody=True
    )
    assert repo.apply_verified_privacy_action(
        lookup=H1, action="bounce", evidence_hmac=H2, checked_at=NOW
    )
    connection = factory.calls[0]
    assert connection.committed
    statements_text = statements(connection)
    assert "pg_advisory_xact_lock" in statements_text
    assert "FOR UPDATE" in statements_text
    assert "empire_consumer_email_suppressions" in statements_text
    assert "permission_state='unsubscribed'" in statements_text
    assert "SET consumed_at=clock_timestamp()" in statements_text
    assert any(
        "suppressed_bounce" in params and "VERIFIED_PROVIDER_EVENT" in params
        for sql, params in connection.statements if "INSERT INTO public.empire_consumer_consent_events" in sql
    )


def test_owner_erasure_zeroes_ciphertext_and_keeps_audit_and_suppression():
    factory = Factory("already-verified")
    repo = ConsumerPostgresRepository(
        connection_factory=factory, approved_custody=True
    )
    assert repo.apply_verified_privacy_action(
        lookup=H1, action="privacy_erasure",
        evidence_hmac=H2, checked_at=NOW
    )
    connection = factory.calls[0]
    statements_text = statements(connection)
    assert "permission_state='erased',email_ciphertext=NULL" in statements_text
    assert "email_key_reference=NULL" in statements_text
    assert "privacy_request" in str(connection.statements)
    audit = [
        params for sql, params in connection.statements
        if "INSERT INTO public.empire_consumer_consent_events" in sql
    ]
    assert len(audit) == 2
    assert {"erasure_requested", "erasure_completed"} == {
        params[1] for params in audit
    }


def test_invalid_privacy_action_cannot_open_transaction():
    factory = Factory("pending")
    repo = ConsumerPostgresRepository(
        connection_factory=factory, approved_custody=True
    )
    assert not repo.apply_verified_privacy_action(
        lookup=H1, action="resubscribe", evidence_hmac=H2,
        checked_at=NOW
    )
    assert factory.calls == []
