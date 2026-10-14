"""First-party original-message intake: synthetic end-to-end signer/verifier gauntlet.

Never calls a public SMTP server. Uses ephemeral Ed25519 keys, test-only
owner MTA callbacks and a fake atomic event reservoir. Confirms no outbound,
DNS, DB, OAuth, Postfix or private credential handling.
"""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.policy import SMTP
from hashlib import sha256
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from empire_os.owned_ingress_receipt_producer import (
    prepare_owned_ingress_receipt, fixture_contract_summary,
    MAX_ORIGINAL_BYTES, MAX_HEADER_BYTES,
)
from empire_os.jev_gtm_signed_transport_review import inspect_signed_ingress_receipts
from empire_os.jev_gtm_mailbox_header_review import review_owned_mailbox_headers
from empire_os.owned_imap_mailbox import OwnedIMAPMailboxProvider

NOW = datetime(2026, 10, 14, 13, tzinfo=timezone.utc)
TENANT = str(UUID(int=7))
INTENT = str(UUID(int=11))
RECIPIENT = f"reply+{INTENT}@mail.empire-ai.co.uk"
PARENT = "<original-sent@mail.empire-ai.co.uk>"
MID = "<reply-from-buyer@company.example>"
KEY = b"separate-local-review-hmac-key-00000000000000000000"
SIGNER = Ed25519PrivateKey.generate()
KEY_ID = "sovereign-mta-v1"


def fixture_raw(**headers):
    msg = EmailMessage()
    msg["From"] = headers.pop("From", "public-contact@company.example")
    msg["To"] = headers.pop("To", RECIPIENT)
    msg["Message-ID"] = headers.pop("Message-ID", MID)
    if "In-Reply-To" not in headers:
        msg["In-Reply-To"] = PARENT
    for key, value in headers.items():
        msg[key] = value
    msg["Subject"] = "Private price request that must not leak"
    msg.set_content("PRIVATE BUYER MESSAGE content, not verified intent")
    return msg.as_bytes(policy=SMTP)


class FakeOwnedMailbox(OwnedIMAPMailboxProvider):
    def __init__(self, raw):
        super().__init__(
            host="mail.empire-ai.co.uk", username="phil@mail.empire-ai.co.uk",
            password="offline-fake-password",
        )
        self.raw = raw
    def list_received(self, *, limit):
        row = self._extract(
            self.raw, identity="imap:inbox:99:12", direction="inbox",
            server_internal_date=NOW.isoformat(),
        )
        return [row]
    def list_sent(self, *, limit):
        original = EmailMessage()
        original["From"] = "phil@mail.empire-ai.co.uk"
        original["To"] = "private-company-contact@example.invalid"
        original["Message-ID"] = PARENT
        original.set_content("Private sent offer")
        row = self._extract(
            original.as_bytes(policy=SMTP),
            identity="imap:sent:99:11", direction="sent",
            server_internal_date=NOW.isoformat(),
        )
        return [row]


class FakeOwner:
    def __init__(self):
        self.reserved = set()
        self.calls = []
        self.auth_result = "dmarc_aligned_pass"
        self.current_tenant = TENANT
        self.match_digest = True
        self.verified = True
    def inspect(self, queue, digest):
        self.calls.append("mta")
        return {
            "mta_queue_id": queue,
            "raw_message_sha256": digest if self.match_digest else "0"*64,
            "received_at": int(NOW.timestamp())-15,
            "source": "postfix_trusted_ingress_log",
            "authenticated_local_peer": self.verified,
            "trusted_authentication_result": self.auth_result,
            "independent_evidence_id": "EVIDENCE123",
        }
    def bind(self, intent):
        self.calls.append("binder")
        return {
            "tenant_id": self.current_tenant, "intent_id": intent,
            "scope_verified": True,
        }
    def reserve(self, event, digest):
        self.calls.append("reserve")
        if event in self.reserved:
            return False
        self.reserved.add(event)
        return True


def sign(*, raw=None, recipient=RECIPIENT, queue="ABCD1234",
         owner=None, issue=NOW, signer=SIGNER):
    owner = owner or FakeOwner()
    return prepare_owned_ingress_receipt(
        raw_message=fixture_raw() if raw is None else raw,
        envelope_recipient=recipient,
        mta_queue_id=queue,
        trusted_mta_evidence=owner.inspect,
        canonical_intent_binding=owner.bind,
        reserve_unique_event=owner.reserve,
        signer=signer, key_id=KEY_ID, issued_at=issue,
    )


def test_ephemeral_owner_pipeline_creates_real_ed25519_receipt_for_wave10_verifier():
    raw = fixture_raw()
    owner = FakeOwner()
    signed = sign(raw=raw, owner=owner)
    inbox = review_owned_mailbox_headers(FakeOwnedMailbox(raw), key=KEY)
    report = inspect_signed_ingress_receipts(
        inbox, [signed], expected_tenant_id=TENANT,
        pinned_ingress_keys={KEY_ID: SIGNER.public_key()},
        operator_hmac_key=KEY, as_of=NOW,
    )
    assert owner.calls == ["mta", "binder", "reserve"]
    assert signed["claims"]["raw_message_sha256"] == sha256(raw).hexdigest()
    assert report["signed_assertions_matched_to_imap_headers"] == 1
    assert report["rows"][0]["signed_transport_assertion_valid"] is True
    assert report["trusted_ingress_producer_live_deployment_audited"] is False
    assert report["original_smtp_provider_authentication_independently_proven"] is False
    assert report["canonical_tenant_contact_binding_verified"] is False
    assert report["buyer_reply_count_verified"] is None
    assert report["outbound_authorized"] is False
    assert report["database_mutations"] is False
    assert report["mailbox_mutations"] is False
    summary = fixture_contract_summary(signed)
    assert summary["cryptographic_envelope_formed"] is True
    assert summary["actual_postfix_ingress_seen"] is False
    assert summary["producer_deployed"] is False
    assert summary["verified_buyer_reply_count"] is None
    assert summary["dns_modified"] is False
    assert summary["mail_sent"] is False
    assert "PRIVATE BUYER MESSAGE" not in repr(summary)
    assert MID not in repr(summary)
    assert INTENT not in repr(summary)


def test_signed_receipt_replay_cannot_mint_second_proof():
    owner = FakeOwner()
    first = sign(owner=owner)
    with pytest.raises(ValueError, match="replay"):
        sign(owner=owner)
    assert first["schema_version"] == "empire.jev.signed_ingress_observation.v1"


def test_not_a_listener_or_outbound_service():
    from empire_os import owned_ingress_receipt_producer as producer
    assert not hasattr(producer, "app")
    assert not hasattr(producer, "serve")
    assert not hasattr(producer, "send_email")
    assert not hasattr(producer, "load_private_key")


@pytest.mark.parametrize("untrusted_recipient", [
    "victim@example.com", "reply@example.com",
    "reply+invalid@mail.empire-ai.co.uk",
    "reply+00000000-0000-0000-0000-00000000000B@mail.empire-ai.co.uk",
    "reply+00000000-0000-0000-0000-00000000000b@other.example",
    "reply+00000000-0000-0000-0000-00000000000b@mail.empire-ai.co.uk\r\nBcc:evil",
])
def test_restricted_envelope_recipient_rejects_catch_all(untrusted_recipient):
    owner = FakeOwner()
    with pytest.raises(ValueError, match="envelope"):
        sign(recipient=untrusted_recipient, owner=owner)
    assert owner.calls == []


def test_invalid_queue_id_cannot_reach_mta():
    owner=FakeOwner()
    with pytest.raises(ValueError, match="queue"):
        sign(queue="../etc/passwd",owner=owner)
    assert owner.calls == []


def test_no_smtp_trust_from_sender_supplied_authentication_results_mime():
    raw=fixture_raw(**{
        "Authentication-Results": "mail.empire-ai.co.uk; dmarc=pass (spoofed)",
    })
    owner=FakeOwner()
    owner.auth_result="dmarc_fail"
    with pytest.raises(ValueError,match="MTA provenance"):
        sign(raw=raw,owner=owner)
    assert owner.calls == ["mta"]


def test_cannot_sign_with_missing_or_wrong_mta_proof():
    for field,value in (
        ("verified",False), ("match_digest",False),
        ("auth_result","smtp_accepted_only"),
    ):
        owner=FakeOwner()
        setattr(owner,field,value)
        with pytest.raises(ValueError,match="MTA provenance"):
            sign(owner=owner)
        assert "binder" not in owner.calls
        assert "reserve" not in owner.calls


def test_canonical_tenant_uuid_must_be_bound_by_dedicated_owner():
    owner=FakeOwner()
    owner.current_tenant="not-uuid"
    with pytest.raises(ValueError,match="canonical identity"):
        sign(owner=owner)
    assert owner.calls == ["mta","binder"]


def test_wrong_or_future_timestamps_are_rejected_before_replay_reserve():
    owner=FakeOwner()
    with pytest.raises(ValueError,match="time outside signing boundary"):
        sign(owner=owner, issue=NOW+timedelta(minutes=7))
    assert "reserve" not in owner.calls


@pytest.mark.parametrize("bad", [b"", b"\x00"*(MAX_ORIGINAL_BYTES+1), b"x"*100])
def test_message_size_and_missing_headers_denied(bad):
    owner=FakeOwner()
    with pytest.raises(ValueError):
        sign(owner=owner,raw=bad)
    assert owner.calls == []


def test_duplicate_original_rfc_message_id_header_denied():
    raw=fixture_raw().replace(
        b"Message-ID: " + MID.encode() + b"\r\n",
        b"Message-ID: " + MID.encode() + b"\r\nMessage-ID: <duplicate@sender.example>\r\n"
    )
    owner=FakeOwner()
    with pytest.raises(ValueError,match="singular"):
        sign(raw=raw,owner=owner)
    assert owner.calls==[]


def test_private_signature_key_must_be_explicitly_injected():
    owner=FakeOwner()
    with pytest.raises(ValueError,match="signer"):
        sign(owner=owner,signer=None)
    assert owner.calls==[]


def test_forged_mta_readonly_callbacks_cannot_prove_live_deployment():
    signed=sign()
    summary=fixture_contract_summary(signed)
    assert summary["actual_postfix_ingress_seen"] is False
    assert summary["original_smtp_source_audited"] is False
    assert summary["canonical_buyer_identity_proven"] is False
    assert summary["outbound_authorized"] is False


def test_real_durable_private_replay_store_is_atomic_across_instances(tmp_path):
    import os
    from empire_os.owned_ingress_receipt_producer import ProtectedIngressReplayStore
    private=tmp_path / "private-ingress-replays"
    private.mkdir(mode=0o700)
    os.chmod(private,0o700)
    a=ProtectedIngressReplayStore(private)
    b=ProtectedIngressReplayStore(private)
    event=str(UUID(int=100))
    digest=sha256(b"test-only-ingress").hexdigest()
    assert a.reserve_once(event,digest) is True
    assert b.reserve_once(event,digest) is False
    paths=list(private.iterdir())
    assert len(paths)==1
    assert paths[0].name == event+".seen"
    assert paths[0].stat().st_mode & 0o777 == 0o600
    assert paths[0].read_text()==digest+"\n"


def test_replay_store_rejects_world_readable_directory(tmp_path):
    import os
    from empire_os.owned_ingress_receipt_producer import ProtectedIngressReplayStore
    root=tmp_path/"unsafe"
    root.mkdir()
    os.chmod(root,0o755)
    with pytest.raises(ValueError,match="ownership or mode"):
        ProtectedIngressReplayStore(root).reserve_once(
            str(UUID(int=99)),sha256(b"fixture").hexdigest()
        )
    assert list(root.iterdir())==[]


def test_replay_store_rejects_symlink_to_private_directory(tmp_path):
    import os
    from empire_os.owned_ingress_receipt_producer import ProtectedIngressReplayStore
    root=tmp_path/"owner-root"
    root.mkdir(mode=0o700)
    os.chmod(root,0o700)
    alias=tmp_path/"alias"
    alias.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError,match="ownership or mode"):
        ProtectedIngressReplayStore(alias).reserve_once(
            str(UUID(int=100)),sha256(b"fixture").hexdigest()
        )
    assert list(root.iterdir())==[]


def test_replay_store_requires_provisioned_root_and_valid_digest(tmp_path):
    from empire_os.owned_ingress_receipt_producer import ProtectedIngressReplayStore
    missing=tmp_path/"not-provisioned"
    store=ProtectedIngressReplayStore(missing)
    with pytest.raises(ValueError,match="digest"):
        store.reserve_once(str(UUID(int=200)),"not-a-digest")
    with pytest.raises(ValueError,match="unavailable"):
        store.reserve_once(str(UUID(int=200)),sha256(b"fixture").hexdigest())


def test_owner_receipt_signer_can_use_durable_replay_reservation(tmp_path):
    import os
    from empire_os.owned_ingress_receipt_producer import ProtectedIngressReplayStore
    path=tmp_path/"protected"
    path.mkdir(mode=0o700)
    os.chmod(path,0o700)
    owner=FakeOwner()
    durable=ProtectedIngressReplayStore(path)
    packet=prepare_owned_ingress_receipt(
        raw_message=fixture_raw(),envelope_recipient=RECIPIENT,
        mta_queue_id="ABCD1234",trusted_mta_evidence=owner.inspect,
        canonical_intent_binding=owner.bind,
        reserve_unique_event=durable.reserve_once,
        signer=SIGNER,key_id=KEY_ID,issued_at=NOW,
    )
    assert packet["schema_version"]=="empire.jev.signed_ingress_observation.v1"
    with pytest.raises(ValueError,match="replay"):
        prepare_owned_ingress_receipt(
            raw_message=fixture_raw(),envelope_recipient=RECIPIENT,
            mta_queue_id="ABCD1234",trusted_mta_evidence=owner.inspect,
            canonical_intent_binding=owner.bind,
            reserve_unique_event=ProtectedIngressReplayStore(path).reserve_once,
            signer=SIGNER,key_id=KEY_ID,issued_at=NOW,
        )
