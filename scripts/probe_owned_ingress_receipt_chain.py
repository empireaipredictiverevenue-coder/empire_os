"""Offline sovereign mail-ingress receipt chain smoke. No real mailbox/MTA.

Generate an EPHEMERAL, test-only Ed25519 key, synthesize an original MIME
reply, use owner-injected fake log & canonical binder, atomically reserve the
receipt, verify with JEV Wave 10 and destroy the temp replay directory.
No secret files, sender, network, DNS or production database access.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from empire_os.owned_ingress_receipt_producer import (
    prepare_owned_ingress_receipt, ProtectedIngressReplayStore,
)
from empire_os.jev_gtm_signed_transport_review import inspect_signed_ingress_receipts
from empire_os.jev_gtm_mailbox_header_review import review_owned_mailbox_headers
from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider


def fixture_smoke() -> dict:
    """Full source -> signed receipt -> Wave 10 read-only consumer, no I/O elsewhere."""
    tenant=str(UUID(int=71))
    intent=str(UUID(int=81))
    now=datetime(2026,10,14,13,tzinfo=timezone.utc)
    original_id="<offline-reply@buyer.example>"
    parent_id="<offline-sent@mail.empire-ai.co.uk>"
    envelope=f"reply+{intent}@mail.empire-ai.co.uk"
    key=b"OFFLINE-ONLY-SEPARATE-HMAC-KEY-00000000000000000"
    private=Ed25519PrivateKey.generate()
    subject="PRIVATE TEST RECIPIENT - DO NOT EMIT"
    buyer=EmailMessage()
    buyer["Message-ID"]=original_id
    buyer["In-Reply-To"]=parent_id
    buyer["From"]="private@buyer.example"
    buyer["To"]=envelope
    buyer["Subject"]=subject
    buyer.set_content("PRIVATE SAMPLE BODY - NEVER RETURN")
    raw=buyer.as_bytes(policy=SMTP)
    outbound=EmailMessage()
    outbound["From"]="phil@mail.empire-ai.co.uk"
    outbound["To"]="buyer@example.invalid"
    outbound["Message-ID"]=parent_id
    outbound.set_content("PRIVATE SENT BODY")

    class OwnedFixture(OwnedIMAPMailboxProvider):
        def __init__(self):
            super().__init__(host="offline.invalid",username="offline@example.invalid",password="ephemeral")
        def list_received(self,*,limit):
            return [self._extract(
                raw,identity="imap:inbox:101:10",direction="inbox",
                server_internal_date=now.isoformat()
            )]
        def list_sent(self,*,limit):
            return [self._extract(
                outbound.as_bytes(policy=SMTP),
                identity="imap:sent:101:9",direction="sent",
                server_internal_date=now.isoformat()
            )]
        def readiness(self):
            return {"configured":True}

    with tempfile.TemporaryDirectory(prefix="owned-ingress-offline-") as folder:
        private_dir=Path(folder)/"replay"
        private_dir.mkdir(mode=0o700)
        os.chmod(private_dir,0o700)
        replay=ProtectedIngressReplayStore(private_dir)
        def source(queue,digest):
            return {
                "mta_queue_id":queue,"raw_message_sha256":digest,
                "received_at":int(now.timestamp())-12,
                "source":"postfix_trusted_ingress_log",
                "authenticated_local_peer":True,
                "trusted_authentication_result":"dmarc_aligned_pass",
                "independent_evidence_id":"FIXTURE20261014",
            }
        def binding(identity):
            return {"tenant_id":tenant,"intent_id":identity,"scope_verified":True}
        signed=prepare_owned_ingress_receipt(
            raw_message=raw,envelope_recipient=envelope,
            mta_queue_id="ABCDEF1234",trusted_mta_evidence=source,
            canonical_intent_binding=binding,reserve_unique_event=replay.reserve_once,
            signer=private,key_id="offline-test-only",issued_at=now,
        )
        header_review=review_owned_mailbox_headers(OwnedFixture(),key=key,limit=1)
        verified=inspect_signed_ingress_receipts(
            header_review,[signed],expected_tenant_id=tenant,
            pinned_ingress_keys={"offline-test-only":private.public_key()},
            operator_hmac_key=key,as_of=now,
        )
        replay_refused = False
        try:
            prepare_owned_ingress_receipt(
                raw_message=raw,envelope_recipient=envelope,
                mta_queue_id="ABCDEF1234",trusted_mta_evidence=source,
                canonical_intent_binding=binding,reserve_unique_event=replay.reserve_once,
                signer=private,key_id="offline-test-only",issued_at=now,
            )
        except ValueError:
            replay_refused=True
        matched=verified["signed_assertions_matched_to_imap_headers"]==1
        return {
            "schema_version":"empire.owned_ingress_offline_gauntlet.v1",
            "status":"OFFLINE_END_TO_END_PASS" if matched and replay_refused else "OFFLINE_FAILED",
            "synthetic_only":True,
            "ephemeral_test_signing_key_used":True,
            "actual_smtp_delivery_seen":False,
            "postfix_deployed":False,
            "live_ingress_key_provisioned":False,
            "original_smtp_provider_independently_verified":False,
            "canonical_buyer_identity_verified":False,
            "signed_receipt_consumer_validated":matched,
            "durable_replay_prevented":replay_refused,
            "buyer_reply_count_verified":None,
            "recognized_revenue":None,
            "sender_contact_clearance_verified":False,
            "actual_mail_sent":False,
            "dns_changed":False,
            "database_writes":False,
            "network_calls":0,
            "execution_authority":"none",
        }


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="First-party ingress fixture only")
    parser.add_argument("--fixture-smoke",action="store_true")
    args=parser.parse_args(argv)
    if not args.fixture_smoke:
        print(json.dumps({
            "status":"NO_LIVE_INGRESS_PROBE_AUTHORIZED",
            "network_calls":0,"actual_mail_sent":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 0
    outcome=fixture_smoke()
    print(json.dumps(outcome,sort_keys=True))
    return 0 if outcome["status"]=="OFFLINE_END_TO_END_PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
