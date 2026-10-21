"""Real PostgreSQL 18 private-login authority fixture; NO live operations.

Runs only inside pg_virtualenv on fixture DB and ephemeral port. The connection
injection deliberately ignores the synthetic production-format sample DSN.
"""
from __future__ import annotations

import json
import os

import psycopg

import empire_os.consumer_optin_connection_custody as custody
from empire_os.consumer_optin_suppression_reader import ConsumerPrivateSuppressionReader
from empire_os.consumer_optin_private_service import (
    Keys, PrivateConsumerOptinService
)
from empire_os.consumer_optin_postgres_repository import ConsumerPostgresRepository

DB="empire_consumer_optin_fixture"


def ephemeral_connection(*_args,**_kwargs):
    return psycopg.connect(
        dbname=DB,host=os.environ["PGHOST"],port=int(os.environ["PGPORT"]),
        user=custody.LOGIN,connect_timeout=5,
        password="synthetic_fake_secret_for_fixture_only_2026"
    )


def main():
    if (
        os.environ.get("PGHOST") not in ("localhost","127.0.0.1")
        or not str(os.environ.get("PGPORT","")).isdecimal()
        or int(os.environ["PGPORT"]) <= 5432
        or os.environ.get("EMPIREDB_DSN")
    ):
        raise RuntimeError("ONLY_EPHEMERAL_PGVIRTUALENV_FIXTURE")
    # This override is strictly contained within a disposable test process;
    # the source module used in production remains pinned to EmpireDB.
    custody.DATABASE=DB
    sample=(
        "host=127.0.0.1 port=5432 dbname="+DB+" "
        "user="+custody.LOGIN+" password=synthetic_fake_secret_for_fixture_only_2026"
    )
    factory=custody.PrivateConsumerConnectionFactory(
        dsn=sample,owner_authorized=True,connect=ephemeral_connection
    )
    with factory() as private:
        assert private.execute(
            "SELECT session_user,current_user,current_database()"
        ).fetchone()==(custody.LOGIN,custody.WRITER,DB)
        count=private.execute(
            "SELECT count(*) FROM public.empire_consumer_subscriptions"
        ).fetchone()[0]
        assert count==0
        # No customer records are inserted by the identity probe.
    reader=ConsumerPrivateSuppressionReader(
        connect=factory,lookup_key=b"K"*32,
        approved_private_custody=True,
    )
    assert reader("nobody-registered@example.test") is False

    # Exercise the real repository through SCRAM + restricted role.
    # The only sender is an in-memory fake and all contacts are synthetic.
    class SyntheticSender:
        def __init__(self):
            self.sent=[]
        def provider_ready(self):
            return True
        def send_verification(self, **kw):
            if reader(kw["recipient"]) is not True:
                return None
            self.sent.append(kw)
            return "PRIVATE_LOGIN_SYNTHETIC_PROVIDER_ACCEPTANCE"

    sender=SyntheticSender()
    keys=Keys(
        email_hmac=b"A"*32,token_hmac=b"B"*32,
        email_encryption=b"C"*32,email_key_reference="consumer-key-v1"
    )
    scoped_reader=ConsumerPrivateSuppressionReader(
        connect=factory, lookup_key=keys.email_hmac,
        approved_private_custody=True,
    )
    reader=scoped_reader
    store=ConsumerPostgresRepository(
        connection_factory=factory, approved_custody=True
    )
    svc=PrivateConsumerOptinService(
        keys=keys,store=store,sender=sender
    )
    consent=dict(
        offer_slug="roofing-cost-guide",
        source="EMPIRE_OWNED_PUBLIC_ROOFING_GUIDE",
        notice_version="roofing-homeowner-updates-v1",
        own_brand_updates="explicit_true",
        third_party_buyer_sharing="explicit_false",
    )
    assert svc.request_verification(
        email="private-login-test@example.test",
        notice_version="roofing-homeowner-updates-v1",
        consent_receipt=consent,
    )
    assert len(sender.sent)==1
    confirm=sender.sent[0]["confirm_link"].split("#confirm=",1)[1]
    unsubscribe=sender.sent[0]["unsubscribe_link"].split("#unsubscribe=",1)[1]
    svc.confirm_with_token(token=confirm)
    svc.withdraw_with_token(token=unsubscribe)
    with factory() as private:
        assert private.execute(
            "SELECT count(*) FROM public.empire_consumer_subscriptions "
            "WHERE permission_state='unsubscribed'"
        ).fetchone()[0]==1
        assert private.execute(
            "SELECT count(*) FROM public.empire_consumer_email_suppressions"
        ).fetchone()[0]==1
        assert private.execute(
            "SELECT count(*) FROM public.empire_consumer_consent_events"
        ).fetchone()[0]==3
    assert not svc.request_verification(
        email="private-login-test@example.test",
        notice_version="roofing-homeowner-updates-v1",
        consent_receipt=consent,
    )
    assert len(sender.sent)==1

    # Dropping the ability to assume the writer role must prevent connections.
    with psycopg.connect(
        dbname=DB,host=os.environ["PGHOST"],port=int(os.environ["PGPORT"])
    ) as admin:
        admin.execute("REVOKE "+custody.WRITER+" FROM "+custody.LOGIN)
    try:
        conn=factory()
        conn.close()
    except (psycopg.Error, RuntimeError):
        pass
    else:
        raise AssertionError("UNAUTHORISED_PRIVATE_WRITER_ROLE_ACCEPTED")
    print(json.dumps({
        "status":"REAL_POSTGRES_PRIVATE_LOGIN_CUSTODY_PASS",
        "database":"TEMPORARY_FIXTURE_ONLY",
        "isolated_login":True,
        "set_role_required":True,
        "writer_membership_revocation_blocks":True,
        "synthetic_confirm_and_unsubscribe":True,
        "suppressed_resignup_blocked":True,
        "synthetic_test_subscription_rows":1,
        "real_customer_records_written":0,
        "production_database_touched":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
