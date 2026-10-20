"""Synthetic PostgreSQL transaction-contract tests, zero live DB access."""
from datetime import datetime, timedelta, timezone

import pytest
from empire_os.consumer_optin_postgres_repository import ConsumerPostgresRepository

NOW = datetime(2026,10,20,20,tzinfo=timezone.utc)
H1 = "a"*64
H2 = "b"*64
H3 = "c"*64
H4 = "d"*64
ROW_ID = "synthetic-private-subscription-uuid"
PREPARED = dict(
    lookup=H1, ciphertext=b"x"*64,key_ref="consumer-key-v1",
    capture_digest=H2, confirm_hmac=H3,
    confirm_expires=NOW+timedelta(hours=2),
    unsubscribe_hmac=H4,
    unsubscribe_expires=NOW+timedelta(days=30),
)

class Cursor:
    def __init__(self, value=None):self.value=value
    def fetchone(self):return self.value

class Connection:
    def __init__(self, scenario="fresh"):
        self.statements=[]
        self.scenario=scenario
        self.committed=False
        self.rolled_back=False
    def __enter__(self):return self
    def __exit__(self,typ,exception,tb):
        self.committed=typ is None
        self.rolled_back=typ is not None
    def execute(self,statement,params=()):
        self.statements.append((statement,params))
        if "FROM public.empire_consumer_email_suppressions" in statement:
            return Cursor((1,) if self.scenario=="suppressed" else None)
        if "SELECT subscription_id, permission_state" in statement:
            return Cursor((ROW_ID,"pending_verification") if self.scenario=="pending" else
                (ROW_ID,"verified") if self.scenario=="already-verified" else None)
        if "INSERT INTO public.empire_consumer_subscriptions" in statement:
            return Cursor((ROW_ID,))
        if "SELECT s.subscription_id FROM public.empire_consumer_subscriptions s" in statement:
            return Cursor((ROW_ID,) if self.scenario=="pending" else None)
        if "SET send_claimed_at=clock_timestamp()" in statement:
            return Cursor((H3,))
        if "SELECT t.subscription_id,s.email_lookup_hmac" in statement:
            return Cursor((ROW_ID,H1) if self.scenario!="missing-token" else None)
        if "SELECT t.expires_at,t.consumed_at,s.permission_state" in statement:
            return Cursor((NOW+timedelta(hours=1),
                NOW if self.scenario=="already-consumed" else None,
                "pending_verification" if self.scenario in ("confirm-delivered","confirm-undelivered")
                else "verified"))
        if "FROM public.empire_consumer_delivery_receipts" in statement:
            return Cursor((1,) if self.scenario=="confirm-delivered" else None)
        return Cursor(None)


class Factory:
    def __init__(self,scenario="fresh"):
        self.calls=[]
        self.scenario=scenario
    def __call__(self):
        c=Connection(self.scenario)
        self.calls.append(c)
        return c


def statements(conn):
    return "\n".join(query for query,_ in conn.statements)


def test_default_cannot_open_a_database_connection_or_write():
    factory=Factory()
    repo=ConsumerPostgresRepository(connection_factory=factory)
    assert repo.signup_writable() is False
    assert repo.token_processing_writable() is False
    assert repo.begin_pending(**PREPARED) is False
    assert repo.consume_once(token_hmac=H3,action="confirm",checked_at=NOW) is False
    assert factory.calls==[]


def test_pending_signup_is_one_transaction_with_hmac_serialisation_and_receipt():
    factory=Factory()
    repo=ConsumerPostgresRepository(connection_factory=factory,approved_custody=True)
    assert repo.begin_pending(**PREPARED)
    assert len(factory.calls)==1
    c=factory.calls[0]
    assert c.committed and not c.rolled_back
    sql=statements(c)
    for snippet in (
        "pg_advisory_xact_lock", "FROM public.empire_consumer_email_suppressions",
        "FOR UPDATE", "INSERT INTO public.empire_consumer_subscriptions",
        "INSERT INTO public.empire_consumer_consent_events",
        "INSERT INTO public.empire_consumer_one_time_tokens",
    ):
        assert snippet in sql
    assert sql.count("INSERT INTO public.empire_consumer_one_time_tokens")==2
    assert "only-synthetic@example.test" not in str(c.statements)


def test_suppressed_person_is_refused_before_any_insert():
    f=Factory("suppressed")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.begin_pending(**PREPARED) is False
    sql=statements(f.calls[0])
    assert "INSERT INTO" not in sql
    assert f.calls[0].committed


def test_already_verified_person_does_not_regain_pending_permission():
    f=Factory("already-verified")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.begin_pending(**PREPARED) is False
    assert "UPDATE public.empire_consumer_subscriptions" not in statements(f.calls[0])


def test_repeat_pending_invalidates_earlier_one_time_tokens():
    f=Factory("pending")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.begin_pending(**PREPARED)
    assert "UPDATE public.empire_consumer_one_time_tokens" in statements(f.calls[0])


def test_mail_provider_delivery_receipt_is_privately_stored_hmac_only():
    f=Factory("pending")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.record_confirmation_delivery(
        lookup=H1,confirm_hmac=H3,provider_receipt=H4)
    sql=statements(f.calls[0])
    assert "INSERT INTO public.empire_consumer_delivery_receipts" in sql
    assert "FOR UPDATE OF s,t" in sql


def test_no_confirmation_if_provider_never_accepted_email():
    f=Factory("confirm-undelivered")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.consume_once(token_hmac=H3,action="confirm",checked_at=NOW) is False
    assert "permission_state='verified'" not in statements(f.calls[0])


def test_confirmed_email_uses_atomic_token_and_state_transition():
    f=Factory("confirm-delivered")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.consume_once(token_hmac=H3,action="confirm",checked_at=NOW)
    c=f.calls[0]
    sql=statements(c)
    assert c.committed
    assert "pg_advisory_xact_lock" in sql
    assert "FOR UPDATE OF s,t" in sql
    assert "permission_state='verified'" in sql
    assert any("INSERT INTO public.empire_consumer_consent_events" in q
               and "opt_in_verified" in params
               for q, params in c.statements)
    assert "consumed_at=%s" in sql


def test_unsubscribe_records_tombstone_and_revocation_under_same_lock():
    f=Factory("unsubscribe")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.consume_once(token_hmac=H4,action="unsubscribe",checked_at=NOW)
    c=f.calls[0]
    sql=statements(c)
    assert c.committed
    assert "INSERT INTO public.empire_consumer_email_suppressions" in sql
    assert "permission_state='unsubscribed'" in sql
    assert "UPDATE public.empire_consumer_one_time_tokens SET consumed_at=%s" in sql
    assert "AUTHENTICATED_WITHDRAWAL" in str(c.statements)


def test_replayed_token_cannot_create_another_event():
    f=Factory("already-consumed")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.consume_once(token_hmac=H3,action="confirm",checked_at=NOW) is False
    assert "INSERT INTO public.empire_consumer_consent_events" not in statements(f.calls[0])


def test_unknown_token_and_invalid_digest_refused():
    f=Factory("missing-token")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.consume_once(token_hmac=H3,action="confirm",checked_at=NOW) is False
    assert "INSERT INTO" not in statements(f.calls[0])
    with pytest.raises(ValueError):
        repo.consume_once(token_hmac="not-a-keyed-hmac",action="confirm",checked_at=NOW)

def test_confirmation_send_claim_is_once_and_suppression_rechecked():
    f=Factory("pending")
    repo=ConsumerPostgresRepository(connection_factory=f,approved_custody=True)
    assert repo.claim_confirmation_send(lookup=H1,confirm_hmac=H3)
    sql=statements(f.calls[0])
    assert "pg_advisory_xact_lock" in sql
    assert "FROM public.empire_consumer_email_suppressions" in sql
    assert "t.send_claimed_at IS NULL" in sql
    assert "SET send_claimed_at=clock_timestamp()" in sql
    denied=Factory("suppressed")
    blocked=ConsumerPostgresRepository(connection_factory=denied,approved_custody=True)
    assert not blocked.claim_confirmation_send(lookup=H1,confirm_hmac=H3)
    assert "SET send_claimed_at" not in statements(denied.calls[0])
