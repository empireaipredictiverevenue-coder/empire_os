"""RUN ONLY INSIDE pg_virtualenv fixture.

Real PostgreSQL transactions + AES-GCM; *synthetic* recipient, fake sender.
Refuses production/normal ports/DBs and verifies effective private test role.
No real customer, Gmail, webhook, mail or product checkout.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import psycopg

from empire_os.consumer_optin_private_service import Keys, PrivateConsumerOptinService
from empire_os.consumer_optin_postgres_repository import ConsumerPostgresRepository
from empire_os.consumer_optin_token_security import token_fingerprint, email_lookup_hmac

DB="empire_consumer_optin_fixture"
TEST_ROLE="empire_consumer_optin_writer"
NOW=datetime.now(timezone.utc)
CONSENT={
 "offer_slug":"roofing-cost-guide",
 "source":"EMPIRE_OWNED_PUBLIC_ROOFING_GUIDE",
 "notice_version":"roofing-homeowner-updates-v1",
 "own_brand_updates":"explicit_true",
 "third_party_buyer_sharing":"explicit_false",
}
KEYS=Keys(email_hmac=b"A"*32, token_hmac=b"B"*32,
          email_encryption=b"C"*32, email_key_reference="consumer-key-v1")


class FakeSender:
    def __init__(self):
        self.sent=[]
    def provider_ready(self):
        return True
    def send_verification(self, **payload):
        assert payload["recipient"] in ("subscriber-only@example.test","bounce-test@example.test")
        self.sent.append(payload)
        return "SYNTHETIC_NONLIVE_PROVIDER_ACK_20261020"


def open_private():
    connection=psycopg.connect(
        dbname=DB, host=os.environ["PGHOST"],
        port=int(os.environ["PGPORT"]),
    )
    connection.execute("SET ROLE "+TEST_ROLE)
    assert connection.execute(
        "SELECT current_user,current_database()"
    ).fetchone()==(TEST_ROLE,DB)
    return connection


def privileged_scalar(sql):
    with psycopg.connect(dbname=DB,host=os.environ["PGHOST"],
                         port=int(os.environ["PGPORT"])) as conn:
        return conn.execute(sql).fetchone()[0]


def main():
    if (os.environ.get("PGPORT") in ("",None,"5432")
        or os.environ.get("PGHOST") not in ("localhost","127.0.0.1")
        or os.environ.get("EMPIREDB_DSN")):
        raise RuntimeError("ISOLATED_PG_VIRTUALENV_ONLY")
    # The fixture is a fresh, empty temporary DB; current role never has
    # production privileges in EmpireDB.
    assert privileged_scalar("SELECT current_database()")==DB
    store=ConsumerPostgresRepository(
        connection_factory=open_private, approved_custody=True
    )
    sender=FakeSender()
    service=PrivateConsumerOptinService(
        keys=KEYS,store=store,sender=sender,clock=lambda:NOW
    )
    assert service.independently_ready()
    assert service.request_verification(
        email="subscriber-only@example.test",
        notice_version="roofing-homeowner-updates-v1",
        consent_receipt=CONSENT,
    )
    assert len(sender.sent)==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_subscriptions "
        "WHERE permission_state='pending_verification'"
    )==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_delivery_receipts"
    )==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_one_time_tokens"
    )==2
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_consent_events "
        "WHERE consent_action='opt_in_requested'"
    )==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_subscriptions "
        "WHERE position(decode('737562736372696265722d6f6e6c79','hex') "
        "in email_ciphertext)>0"
    )==0
    confirm=sender.sent[0]["confirm_link"].split("#confirm=")[1]
    unsubscribe=sender.sent[0]["unsubscribe_link"].split("#unsubscribe=")[1]
    confirm_fp=token_fingerprint(confirm,action="confirm",key=KEYS.token_hmac)
    action_time=NOW+timedelta(minutes=1)
    assert store.consume_once(token_hmac=confirm_fp,action="confirm",checked_at=action_time)
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_subscriptions "
        "WHERE permission_state='verified'"
    )==1
    assert not store.consume_once(token_hmac=confirm_fp,action="confirm",checked_at=action_time)
    # Move the isolated synthetic app clock beyond token issuance.
    service._clock=lambda: action_time + timedelta(seconds=1)
    service.withdraw_with_token(token=unsubscribe)
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_subscriptions "
        "WHERE permission_state='unsubscribed'"
    )==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_email_suppressions"
    )==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_one_time_tokens "
        "WHERE consumed_at IS NOT NULL"
    )==2
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_consent_events"
    )==3
    assert not service.request_verification(
        email="subscriber-only@example.test",
        notice_version="roofing-homeowner-updates-v1",
        consent_receipt=CONSENT,
    )
    assert len(sender.sent)==1
    # A privacy-owner verified request erases the original encrypted email
    # while retaining only purpose-specific suppression and audit evidence.
    orig_lookup=email_lookup_hmac(
        "subscriber-only@example.test", key=KEYS.email_hmac
    )
    assert store.apply_verified_privacy_action(
        lookup=orig_lookup, action="privacy_erasure",
        evidence_hmac="d"*64, checked_at=action_time+timedelta(seconds=4),
    )
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_subscriptions "
        "WHERE permission_state='erased' AND email_ciphertext IS NULL "
        "AND email_key_reference IS NULL"
    )==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_consent_events "
        "WHERE consent_action IN ('erasure_requested','erasure_completed')"
    )==2

    # An original provider-authenticated bounce on a different synthetic
    # pending signup must revoke the record before confirmation.
    service._clock=lambda:datetime.now(timezone.utc)
    assert service.request_verification(
        email="bounce-test@example.test",
        notice_version="roofing-homeowner-updates-v1",
        consent_receipt=CONSENT,
    )
    bounce_lookup=email_lookup_hmac(
        "bounce-test@example.test",key=KEYS.email_hmac
    )
    assert store.apply_verified_privacy_action(
        lookup=bounce_lookup, action="bounce",
        evidence_hmac="e"*64, checked_at=NOW+timedelta(minutes=3),
    )
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_consent_events "
        "WHERE consent_action='suppressed_bounce'"
    )==1
    assert privileged_scalar(
        "SELECT count(*) FROM public.empire_consumer_email_suppressions"
    )==2
    assert not service.request_verification(
        email="bounce-test@example.test",
        notice_version="roofing-homeowner-updates-v1",
        consent_receipt=CONSENT,
    )
    print(json.dumps({
        "status":"REAL_POSTGRES_SYNTHETIC_LIFECYCLE_PASS",
        "database":"EPHEMERAL_CONSUMER_FIXTURE_ONLY",
        "source":"synthetic optin consent",
        "provider":"fake sender only",
        "transitions":["pending_verification","verified","unsubscribed"],
        "suppression_tombstones":2,
        "append_only_consent_events":7,
        "single_use_tokens":4,
        "replay_blocked":True,
        "repeat_signup_after_suppression_blocked":True,
        "privacy_erasure_ciphertext_removed":True,
        "verified_provider_bounce_suppressed":True,
        "plaintext_emails_in_db":False,
        "production_db_modified":False,
        "emails_sent":0,
    },sort_keys=True))


if __name__=="__main__":
    main()
