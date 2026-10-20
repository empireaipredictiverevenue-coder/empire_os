"""Synthetic-only opt-in lifecycle; no real mail, customer records or DB."""
from datetime import datetime, timezone

import pytest

from empire_os.consumer_optin_private_service import (
    Keys, PrivateConsumerOptinService, encrypt_email, decrypt_email,
)
from empire_os.consumer_optin_token_security import token_fingerprint

NOW = datetime(2026,10,20,20,0,tzinfo=timezone.utc)
KEYS = Keys(email_hmac=b"A"*32,token_hmac=b"B"*32,
            email_encryption=b"C"*32,email_key_reference="consumer-key-v1")
CONSENT = dict(offer_slug="roofing-cost-guide",
    source="EMPIRE_OWNED_PUBLIC_ROOFING_GUIDE",
    notice_version="roofing-homeowner-updates-v1",
    own_brand_updates="explicit_true",third_party_buyer_sharing="explicit_false")


class FakeStore:
    def __init__(self):
        self.writable=True
        self.token_service=True
        self.pending={}
        self.confirmed=[]
        self.withdrew=[]
        self.provider=[]
        self.claims=[]
        self.suppressed=set()
        self.confirm_hmac=None
        self.unsubscribe_hmac=None
    def signup_writable(self):return self.writable
    def token_processing_writable(self):return self.token_service
    def begin_pending(self,**kw):
        if kw["lookup"] in self.suppressed or self.pending.get(kw["lookup"],{}).get("state")=="verified":
            return False
        self.pending[kw["lookup"]]={"state":"pending",**kw}
        self.confirm_hmac=kw["confirm_hmac"]
        self.unsubscribe_hmac=kw["unsubscribe_hmac"]
        return True
    def claim_confirmation_send(self,**kw):
        if kw["lookup"] in self.suppressed:
            return False
        if kw["confirm_hmac"] in self.claims:
            return False
        self.claims.append(kw["confirm_hmac"])
        return True
    def record_confirmation_delivery(self,**kw):
        self.provider.append(kw)
        return True
    def consume_once(self,**kw):
        fingerprint=kw["token_hmac"]
        if kw["action"]=="confirm":
            if fingerprint!=self.confirm_hmac or not self.provider:return False
            self.confirmed.append(fingerprint)
        else:
            if fingerprint!=self.unsubscribe_hmac:return False
            self.withdrew.append(fingerprint)
            self.suppressed.add(next(iter(self.pending)))
        return True


class FakeSender:
    def __init__(self):
        self.ready=True
        self.sent=[]
        self.receipt="SYNTHETIC_PROVIDER_ACCEPTED_MESSAGE_ID"
    def provider_ready(self):return self.ready
    def send_verification(self,**kw):
        self.sent.append(kw)
        return self.receipt


def service(store=None,sender=None,keys=KEYS):
    store=store or FakeStore()
    sender=sender or FakeSender()
    return PrivateConsumerOptinService(
        keys=keys,store=store,sender=sender,clock=lambda:NOW
    ),store,sender


def request(svc,consent=CONSENT):
    return svc.request_verification(email="only-synthetic@example.test",
        notice_version="roofing-homeowner-updates-v1",consent_receipt=consent)


def test_real_authenticated_encryption_no_plaintext_and_tamper_rejection():
    encrypted=encrypt_email("synthetic+label@example.TEST",keys=KEYS,nonce=b"q"*12)
    assert b"synthetic" not in encrypted
    assert decrypt_email(encrypted,keys=KEYS)=="synthetic+label@example.test"
    corrupt=bytearray(encrypted);corrupt[-1]^=1
    with pytest.raises(Exception):decrypt_email(bytes(corrupt),keys=KEYS)


def test_weak_or_reused_keys_not_accepted():
    for keys in (
        Keys(b"A"*32,b"A"*32,b"C"*32,"consumer-key-v1"),
        Keys(b"A"*10,b"B"*32,b"C"*32,"consumer-key-v1"),
    ):
        with pytest.raises(ValueError):service(keys=keys)


def test_private_first_party_signup_to_synthetic_store_and_sender():
    svc,store,sender=service()
    assert request(svc)
    assert len(sender.sent)==1
    assert sender.sent[0]["recipient"]=="only-synthetic@example.test"
    assert "#confirm=" in sender.sent[0]["confirm_link"]
    assert "#unsubscribe=" in sender.sent[0]["unsubscribe_link"]
    assert "?confirm=" not in sender.sent[0]["confirm_link"]
    original=next(iter(store.pending.values()))
    assert b"only-synthetic" not in original["ciphertext"]
    assert len(original["lookup"])==64 and len(original["capture_digest"])==64
    assert len(store.provider[0]["provider_receipt"])==64
    assert "SYNTHETIC_PROVIDER" not in str(store.provider)


def test_token_confirmation_and_withdrawal_never_grant_buyer_lease():
    svc,store,sender=service()
    assert request(svc)
    confirm=sender.sent[0]["confirm_link"].split("#confirm=",1)[1]
    unsub=sender.sent[0]["unsubscribe_link"].split("#unsubscribe=",1)[1]
    svc.confirm_with_token(token=confirm)
    svc.withdraw_with_token(token=unsub)
    assert store.confirmed==[token_fingerprint(confirm,action="confirm",key=KEYS.token_hmac)]
    assert store.withdrew==[token_fingerprint(unsub,action="unsubscribe",key=KEYS.token_hmac)]
    assert len(store.suppressed)==1
    assert not request(svc)
    assert len(sender.sent)==1


def test_pause_new_signups_but_not_withdrawals():
    svc,store,sender=service()
    assert request(svc)
    sender.ready=False
    store.writable=False
    assert not svc.independently_ready()
    assert svc.can_service_withdrawals()
    svc.withdraw_with_token(token=sender.sent[0]["unsubscribe_link"].split("#unsubscribe=",1)[1])
    assert len(store.withdrew)==1


def test_unapproved_consent_must_not_save_or_send():
    for change in (
        {"third_party_buyer_sharing":"explicit_true"},
        {"own_brand_updates":"explicit_false"},
        {"notice_version":"wrong-notice"},
        {"source":"SCRAPED_PERSONAL_EMAIL"},
    ):
        svc,store,sender=service()
        assert not request(svc,{**CONSENT,**change})
        assert not store.pending and not sender.sent


def test_sender_not_ready_holds_before_persistence():
    svc,store,sender=service()
    sender.ready=False
    assert not request(svc)
    assert not store.pending


def test_receipt_required_not_same_as_confirmed_subscriber():
    svc,store,sender=service()
    sender.receipt=None
    assert not request(svc)
    assert store.pending
    assert not store.provider and not store.confirmed


def test_no_default_live_backend_constructor():
    with pytest.raises(TypeError):
        PrivateConsumerOptinService(keys=KEYS)

def test_live_suppression_between_pending_record_and_email_claim_blocks_send():
    class RacingStore(FakeStore):
        def claim_confirmation_send(self,**kwargs):
            self.suppressed.add(kwargs["lookup"])
            return super().claim_confirmation_send(**kwargs)
    svc,store,sender=service(store=RacingStore())
    assert not request(svc)
    assert store.pending
    assert sender.sent==[]


def test_two_distinct_optins_have_independent_original_choice_evidence():
    svc,store,sender=service()
    assert request(svc)
    first=next(iter(store.pending.values()))["capture_digest"]
    # A newly initiated consent creates a fresh token and separate
    # immutable record even with the same user and notice version.
    assert request(svc)
    second=next(iter(store.pending.values()))["capture_digest"]
    assert first!=second
