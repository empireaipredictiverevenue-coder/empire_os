#!/usr/bin/env python3
"""One-shot ORIGINAL ASTRA signed gateway -> 060 restricted DB custody, synthetic only.

Executes ONLY with pg_virtualenv's ephemeral PostgreSQL socket/port and
empire_timer_fixture database. Uses ephemeral Ed25519 keys, entirely
fictional consent/device, no provider/sender network calls or real people.
Does NOT create a webhook, grant runtime writes, or validate genuine consent.
"""
from __future__ import annotations

import base64
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import psycopg

from empire_os.prime_flagship_notification_gateway_shadow import (
    OriginalNotificationGatewayShadow,NotificationGatewayHold,
    PROVIDER,PROVIDER_SCHEMA,PROVIDER_AUDIENCE,PROVIDER_DOMAIN,
    OWNER_SCHEMA,OWNER_AUDIENCE,OWNER_DOMAIN,_signed_bytes,
)

SCHEMA="empire.prime.synthetic_signed_callback_pg059_fixture.v1"
TENANT="123e4567-e89b-42d3-a456-426614174000"


def dg(t: str) -> str:
    return sha256(("fictional-only:"+t).encode()).hexdigest()


def _public(private: Ed25519PrivateKey)->bytes:
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _signed(private: Ed25519PrivateKey, payload: dict, domain: bytes, kid: str)->dict:
    return {
        "kid":kid,"payload":payload,
        "signature":base64.urlsafe_b64encode(
            private.sign(_signed_bytes(payload,domain)),
        ).rstrip(b"=").decode("ascii"),
    }


def _safe_connection()->psycopg.Connection:
    # No query or connection to the main 5432 server is allowed. The parent
    # shell fixture separately verifies the temporary PostgreSQL datadir.
    port=os.environ.get("PGPORT","")
    host=os.environ.get("PGHOST","")
    if (not port.isdigit() or int(port)<5433
        or host not in ("localhost","127.0.0.1","::1")
        or os.environ.get("EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED")!="ephemeral"
        or os.environ.get("PGDATABASE")!="empire_timer_fixture"):
        raise RuntimeError("REFUSED_NON_EPHEMERAL_SIGNED_GATEWAY_DB_TARGET")
    db=psycopg.connect(host=host,port=int(port),dbname="empire_timer_fixture")
    # Verify the *server itself*, not only the caller-supplied environment:
    # never perform fixture writes on an unexpected PostgreSQL instance.
    row=db.execute("SHOW data_directory").fetchone()
    datadir=(row[0].decode("utf-8") if isinstance(row[0],bytes)
             else row[0]) if row else ""
    if (not isinstance(datadir,str)
        or not datadir.startswith("/tmp/pg_virtualenv.")
        or not datadir.endswith("/data/18/regress")):
        db.close()
        raise RuntimeError("REFUSED_NON_TEMPORARY_SIGNED_GATEWAY_DB_CLUSTER")
    return db


def _actual_fixture_login() -> psycopg.Connection:
    """Connect using a distinct disposable SCRAM-authenticated DB identity.

    No SET ROLE or privileged connection can be used for custody writes.
    Cluster/datadir verification is performed by _safe_connection() before
    this is reachable; port and DB are independently constrained here.
    """
    port=os.environ.get("PGPORT","")
    secret=os.environ.get("EMPIRE_FIXTURE_LOGIN_PASSWORD","")
    if (not port.isdigit() or int(port)<5433
        or os.environ.get("EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED")!="ephemeral"
        or os.environ.get("PGDATABASE")!="empire_timer_fixture"
        or len(secret)<32):
        raise RuntimeError("REFUSED_UNAUTHORISED_FIXTURE_LOGIN")
    writer=psycopg.connect(
        host="127.0.0.1",port=int(port),dbname="empire_timer_fixture",
        user="timer_fixture_gateway_login",password=secret,
        connect_timeout=3,
    )
    row=writer.execute("""SELECT session_user,current_user,
        current_database(),inet_server_port()""").fetchone()
    names=[x.decode("ascii") if isinstance(x,bytes) else x for x in row]
    if names!=["timer_fixture_gateway_login",
               "timer_fixture_gateway_login","empire_timer_fixture",int(port)]:
        writer.close()
        raise RuntimeError("REFUSED_UNEXPECTED_ACTUAL_FIXTURE_LOGIN_IDENTITY")
    privileges=writer.execute("""SELECT
        has_table_privilege(current_user,
          'public.empire_prime_timer_provider_receipts','SELECT'),
        has_table_privilege(current_user,
          'public.empire_prime_timer_provider_receipts','INSERT'),
        has_function_privilege(current_user,
          'public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz)',
          'EXECUTE')""").fetchone()
    if tuple(privileges)!=(False,False,True):
        writer.close()
        raise RuntimeError("REFUSED_UNEXPECTED_FIXTURE_WRITER_PRIVILEGES")
    return writer


def _actual_fixture_identity_reader()->psycopg.Connection:
    """SCRAM authenticated independent read-only, synthetic one-tenant scope.

    Never inherits the writer, migrator, or fixture admin session. No production
    Identity/consent authority is created by this test login.
    """
    port=os.environ.get("PGPORT","")
    secret=os.environ.get("EMPIRE_FIXTURE_READER_PASSWORD","")
    if (not port.isdigit() or int(port)<5433
        or os.environ.get("PGDATABASE")!="empire_timer_fixture"
        or os.environ.get("EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED")!="ephemeral"
        or len(secret)<32):
        raise RuntimeError("REFUSED_UNAUTHORISED_FIXTURE_IDENTITY_READER")
    conn=psycopg.connect(
        host="127.0.0.1",port=int(port),dbname="empire_timer_fixture",
        user="timer_fixture_identity_reader_login",password=secret,
        connect_timeout=3,
    )
    row=conn.execute("""SELECT session_user,current_user,current_database(),
        inet_server_port()""").fetchone()
    current=[x.decode("ascii") if isinstance(x,bytes) else x for x in row]
    if current!=["timer_fixture_identity_reader_login",
                 "timer_fixture_identity_reader_login","empire_timer_fixture",int(port)]:
        conn.close()
        raise RuntimeError("REFUSED_UNEXPECTED_ACTUAL_FIXTURE_READER_IDENTITY")
    rights=conn.execute("""SELECT
       has_table_privilege(current_user,
         'public.empire_prime_timer_provider_receipts','INSERT'),
       has_table_privilege(current_user,
         'public.empire_prime_timer_provider_receipts','UPDATE'),
       has_function_privilege(current_user,
         'public.empire_prime_timer_receipt_record_held(uuid,text,text,text,text,text,text,text,text,timestamptz)',
         'EXECUTE')""").fetchone()
    if tuple(rights)!=(False,False,False):
        conn.close()
        raise RuntimeError("REFUSED_FIXTURE_READER_WRITE_OR_EXECUTE_PRIVILEGE")
    return conn


def main()->int:
    with _safe_connection() as db:
        with db.cursor() as cur:
            # The fixture's synthetic authorization source, separate from
            # real EmpireDB or real original Identity/Privacy owners.
            now=datetime.now(timezone.utc)
            created=now-timedelta(seconds=15)
            timer=dg("timer");claim=dg("claimed-event");source=dg("source")
            device=dg("device");actor=dg("actor");consent=dg("consent")
            receipt_1=dg("provider-accept-receipt")
            nonce_1=dg("provider-accept-nonce")
            reference=dg("delivery-reference")
            cur.execute("""INSERT INTO public.empire_prime_voice_timer_requests
                (tenant_id,timer_digest,actor_digest,source_attestation_digest,
                 consent_evidence_digest,policy_revision,duration_seconds,
                 created_at,due_at)
                 VALUES (%s,%s,%s,%s,%s,'pilot.v1',3,%s,%s)""",
                (TENANT,timer,actor,source,consent,created,
                 created+timedelta(seconds=3)))
            cur.execute("""INSERT INTO public.empire_prime_voice_timer_events
                (tenant_id,timer_digest,seq,event_digest,event_kind,
                 occurred_at,source_attestation_digest)
                 VALUES (%s,%s,1,%s,'TIMER_CREATED',%s,%s)""",
                (TENANT,timer,dg("create-event"),created,source))
            cur.execute("""SELECT seq FROM
                public.empire_prime_voice_timer_transition_held
                (%s,%s,'DISPATCH_CLAIMED',%s,%s)""",
                (TENANT,timer,claim,source))
            assert cur.fetchone()[0]==2
            cur.execute("""INSERT INTO fixture_authorised_device
                (tenant_id,timer_digest,actor_digest,device_digest,
                 consent_digest,active)
                VALUES (%s,%s,%s,%s,%s,true)""",
                (TENANT,timer,actor,device,consent))
    provider_private=Ed25519PrivateKey.generate()
    consent_private=Ed25519PrivateKey.generate()
    def authority_reader_scope(tenant_id,timer_digest,device_digest,at):
        with _actual_fixture_identity_reader() as db:
            row=db.execute("""SELECT 1 FROM fixture_authorised_device
                WHERE tenant_id=%s AND timer_digest=%s AND device_digest=%s AND active""",
                (tenant_id,timer_digest,device_digest)).fetchone()
            return row is not None
    def authority_reader_consent(tenant_id,actor_digest,device_digest,consent_digest,at):
        with _actual_fixture_identity_reader() as db:
            return db.execute("""SELECT 1 FROM fixture_authorised_device
                WHERE tenant_id=%s AND actor_digest=%s AND device_digest=%s
                  AND consent_digest=%s AND active""",
                (tenant_id,actor_digest,device_digest,consent_digest)).fetchone() is not None
    def authority_reader_claim(tenant_id,timer_digest,claim_digest,at):
        with _actual_fixture_identity_reader() as db:
            return db.execute("""SELECT 1 FROM public.empire_prime_voice_timer_events
                WHERE tenant_id=%s AND timer_digest=%s AND seq=2
                  AND event_kind='DISPATCH_CLAIMED' AND event_digest=%s""",
                (tenant_id,timer_digest,claim_digest)).fetchone() is not None
    def authority_reader_nonce(provider_code,nonce_digest,at):
        with _actual_fixture_identity_reader() as db:
            return db.execute("""SELECT 1 FROM public.empire_prime_timer_provider_receipts
                WHERE provider_code=%s AND callback_nonce_digest=%s""",
                (provider_code,nonce_digest)).fetchone() is None
    def authority_reader_prior(tenant_id,timer_digest,reference_digest,at):
        with _actual_fixture_identity_reader() as db:
            return db.execute("""SELECT 1 FROM public.empire_prime_timer_provider_receipts
                WHERE tenant_id=%s AND timer_digest=%s AND callback_seq=1
                  AND callback_stage='ACCEPTED' AND delivery_reference_digest=%s""",
                (tenant_id,timer_digest,reference_digest)).fetchone() is not None
    gate=OriginalNotificationGatewayShadow(
        provider_keys={"fixture_provider_key":_public(provider_private)},
        identity_owner_keys={"fixture_identity_key":_public(consent_private)},
        scope_current=authority_reader_scope,
        consent_current=authority_reader_consent,
        claim_current=authority_reader_claim,
        callback_nonce_unseen=authority_reader_nonce,
        prior_provider_acceptance=authority_reader_prior,
    )
    observations=[]
    def count()->int:
        with _safe_connection() as db:
            return db.execute(
                "SELECT count(*) FROM public.empire_prime_timer_provider_receipts"
            ).fetchone()[0]
    def callback(stage: str, number: int, *, invalid_sig=False, owner_revoked=False):
        at=datetime.now(timezone.utc)
        p={
            "schema_version":PROVIDER_SCHEMA,"audience":PROVIDER_AUDIENCE,
            "provider_code":PROVIDER,"tenant_id":TENANT,
            "timer_digest":timer,"claim_event_digest":claim,
            "delivery_reference_digest":reference,"device_digest":device,
            "callback_nonce_digest":dg("nonce-"+str(number)),
            "receipt_digest":dg("receipt-"+str(number)),
            "callback_stage":stage,"provider_reported_at":at.isoformat(),
            "synthetic_only":True,
        }
        o={
            "schema_version":OWNER_SCHEMA,"audience":OWNER_AUDIENCE,
            "tenant_id":TENANT,"timer_digest":timer,"claim_event_digest":claim,
            "actor_digest":actor,"device_digest":device,
            "consent_evidence_digest":consent,
            "consent_decision":(
                "REVOKED" if owner_revoked else "ACTIVE_EXPLICIT_TEST_OPT_IN"
            ),
            "issued_at":(at-timedelta(seconds=3)).isoformat(),
            "expires_at":(at+timedelta(seconds=90)).isoformat(),
            "nonce_digest":dg("owner-nonce-"+str(number)),
            "synthetic_only":True,
        }
        pe=_signed(provider_private,p,PROVIDER_DOMAIN,"fixture_provider_key")
        oe=_signed(consent_private,o,OWNER_DOMAIN,"fixture_identity_key")
        if invalid_sig:
            # Valid base64 characters, invalid signature; original gateway
            # must hold BEFORE writing to PostgreSQL.
            pe["signature"]=oe["signature"]
        return p,pe,oe

    def ingest(envelope,owner)->bool:
        # Gateway holds if signature, original scoped claim, current consent
        # or nonce custody check fails. This method cannot be used outside
        # the explicitly verified disposable fixture.
        reviewed=gate.review(
            provider_envelope=envelope,consent_owner_envelope=owner,
            tenant_id=TENANT,as_of=datetime.now(timezone.utc),
        )
        assert reviewed["execution_authority"]=="none"
        assert reviewed["real_provider_authenticated"] is False
        # Derive database values ONLY from the exact signed, verified payload;
        # never accept a separate caller-supplied record after verification.
        payload=envelope["payload"]
        owner_payload=owner["payload"]
        with _actual_fixture_identity_reader() as db:
            # This separate SCRAM login can read only its tenant's bounded
            # original timer metadata and synthetic consent fields via RLS.
            # Recheck and lock the CURRENT row in this same transaction,
            # closing the window between a preflight lookup and the INSERT.
            # No SELECT FOR SHARE directly: that requires excessive table
            # privilege. Narrow fixture-only definer checks session_user,
            # tenant and active consent before locking its fake consent row.
            consent_row=db.execute("""SELECT public.fixture_lock_current_test_consent(
                %s,%s,%s,%s,%s)""",(TENANT,payload["timer_digest"],
                owner_payload["actor_digest"],payload["device_digest"],
                owner_payload["consent_evidence_digest"])).fetchone()
            if consent_row is None or consent_row[0] is not True:
                raise NotificationGatewayHold(
                    "SYNTHETIC_IN_TRANSACTION_CONSENT_REVOKED"
                )
            # Atomic writer is ultimately arbitrated by 059 unique keys and
            # source/claim/order triggers, not just nonce reader preflight.
            source_db=db.execute("""SELECT source_attestation_digest FROM
                public.empire_prime_voice_timer_requests
                WHERE tenant_id=%s AND timer_digest=%s""",
                (TENANT,payload["timer_digest"])).fetchone()
            if source_db is None:
                raise RuntimeError("SYNTHETIC_REQUEST_SOURCE_READBACK_REQUIRED")
            # Psycopg's metadata result may be byte-oriented under this
            # fixture's raw-text resolver. Convert only the verified
            # original 64-character ASCII hex source value.
            source_value=(source_db[0].decode("ascii") if isinstance(source_db[0],bytes)
                          else source_db[0])
            if not isinstance(source_value,str) or len(source_value)!=64:
                raise RuntimeError("SYNTHETIC_SOURCE_DIGEST_FORMAT_INVALID")
            # The independent fixture connection authenticates via SCRAM
            # as its OWN LOGIN with no elevated privileges. The separate
            # identity/consent SELECT FOR SHARE lock remains held during the
            # restricted writer's complete transaction; this is still only
            # a fictional fixture Identity reader, not production authority.
            with _actual_fixture_login() as writer:
                stored=writer.execute("""SELECT held_receipt_seq,held_status FROM
                public.empire_prime_timer_receipt_record_held(
                   %s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (TENANT,payload["timer_digest"],payload["provider_code"],
                 payload["callback_nonce_digest"],payload["receipt_digest"],
                 payload["claim_event_digest"],payload["delivery_reference_digest"],
                 source_value,payload["callback_stage"],
                 datetime.fromisoformat(payload["provider_reported_at"]))).fetchone()
            if stored is None or stored[0] not in (1,2):
                raise RuntimeError("RESTRICTED_FIXTURE_RECEIPT_WRITER_DID_NOT_COMMIT")
            status=(stored[1].decode("ascii") if isinstance(stored[1],bytes)
                    else stored[1])
            if status!="HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED":
                raise RuntimeError("RESTRICTED_FIXTURE_RECEIPT_STATUS_UNEXPECTED")
        return True

    p1,e1,o1=callback("ACCEPTED",1)
    assert ingest(e1,o1)
    assert count()==1
    observations.append("VALID_SIGNED_ACCEPTED_CALLBACK_PERSISTED")

    # Simulate service restart with independent PostgreSQL connections.
    try:
        ingest(e1,o1)
        raise AssertionError("replayed callback unexpectedly passed")
    except NotificationGatewayHold as exc:
        assert "nonce_replay_refused" in str(exc)
    assert count()==1
    observations.append("RECONNECT_REPLAY_REJECTED_WITHOUT_SECOND_WRITE")

    p2,e2,o2=callback("DELIVERED",2,invalid_sig=True)
    try:
        ingest(e2,o2)
        raise AssertionError("bad signature accepted")
    except NotificationGatewayHold as exc:
        assert "signature_invalid" in str(exc)
    assert count()==1
    observations.append("FORGED_PROVIDER_SIGNATURE_ZERO_WRITES")

    p3,e3,o3=callback("DELIVERED",3,owner_revoked=True)
    try:
        ingest(e3,o3)
        raise AssertionError("revoked consent accepted")
    except NotificationGatewayHold as exc:
        assert "user_opt_in_not_active" in str(exc)
    assert count()==1
    observations.append("REVOKED_OWNER_CONSENT_ZERO_WRITES")

    # Independent fixture revocation via a real PostgreSQL transaction;
    # unchanged signatures must not be allowed after revocation.
    p4,e4,o4=callback("DELIVERED",4)
    with _safe_connection() as db:
        db.execute("""UPDATE fixture_authorised_device SET active=false
            WHERE tenant_id=%s AND timer_digest=%s""",(TENANT,timer))
    try:
        ingest(e4,o4)
        raise AssertionError("disconnected original consent accepted")
    except NotificationGatewayHold as exc:
        assert ("scope_unverified" in str(exc) or "consent_current_unverified" in str(exc))
    assert count()==1
    observations.append("DB_CONSENT_REVOCATION_PREVENTED_WRITE")

    # Fresh independent DB transaction restores this FICTIONAL fixture consent.
    with _safe_connection() as db:
        db.execute("""UPDATE fixture_authorised_device SET active=true
            WHERE tenant_id=%s AND timer_digest=%s""",(TENANT,timer))
    assert ingest(e4,o4)
    assert count()==2
    observations.append("SIGNED_DELIVERED_REPORT_ORDERED_WITH_PREVIOUS_ACCEPTED")
    with _safe_connection() as db:
        stages=db.execute("""SELECT callback_stage FROM
            public.empire_prime_timer_provider_receipts
            WHERE tenant_id=%s AND timer_digest=%s ORDER BY callback_seq""",
            (TENANT,timer)).fetchall()
    assert [(x[0].decode("ascii") if isinstance(x[0],bytes) else x[0])
            for x in stages]==["ACCEPTED","DELIVERED"]

    result={
        "schema_version":SCHEMA,
        "status":"SIGNED_SYNTHETIC_CALLBACKS_PERSISTED_IN_TEMP_POSTGRES",
        "checks":observations,"checks_passed":len(observations),
        "receipt_rows_verified":count(),
        "independent_database_connections_used":True,
        "real_provider_authenticated":False,
        "real_consent_verified":False,
        "real_device_delivered":False,
        "production_empiredb_writes":False,
        "live_sender_activated":False,
        "execution_authority":"fixture_only",
    }
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
