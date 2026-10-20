"""Transactional sender contract, fully mocked HTTP, zero real emails."""
from uuid import UUID
import pytest

from empire_os.consumer_optin_resend_sender import ResendConsumerConfirmationSender

CONFIRM = "https://empire-ai.co.uk/roofing/email-preferences#confirm=" + "A"*43
STOP = "https://empire-ai.co.uk/roofing/email-preferences#unsubscribe=" + "B"*43
TEST_KEY = "re_SYNTHETIC_PRIVATE_MOCK_ONLY_00000000"
ACCEPTED = str(UUID("77a27fae-0f72-4f0b-9bdb-6a3ce0b40b4d"))
EMAIL = "synthetic-person@example.test"


def ready_sender(*, suppressed=False, verified=True, approved=True):
    seen=[]
    checks=[]
    def check(address):
        checks.append(address)
        return not suppressed
    def post(**kwargs):
        seen.append(kwargs)
        return {"id":ACCEPTED}
    adapter=ResendConsumerConfirmationSender(
        api_key=TEST_KEY,
        verified_sender_domain=verified,
        owner_approved_consumer_confirmation=approved,
        current_suppression_clear=check,
        provider=post,
    )
    return adapter,seen,checks


def test_verified_domain_approved_mock_provider_exact_transactional_message():
    sender,sends,checks=ready_sender()
    assert sender.provider_ready()
    receipt=sender.send_verification(
        recipient=EMAIL,confirm_link=CONFIRM,unsubscribe_link=STOP
    )
    assert receipt==ACCEPTED
    assert checks==[EMAIL]
    assert len(sends)==1
    send=sends[0]
    assert send["key"]==TEST_KEY
    assert "synthetic-person" not in send["dedupe_key"]
    assert send["dedupe_key"].startswith("roofing-confirm/")
    p=send["payload"]
    assert p["from"]=="Empire AI <updates@mail.empire-ai.co.uk>"
    assert p["reply_to"]=="reply@mail.empire-ai.co.uk"
    assert p["to"]==[EMAIL]
    assert "Confirm" in p["subject"]
    assert "#confirm=" in p["text"]
    assert "#unsubscribe=" in p["text"]
    assert "contractors" in p["html"]
    assert len(p["tags"])==1
    assert "recipient" not in p["tags"][0]


def test_original_provider_rights_or_owner_approval_cannot_be_guessed():
    for config in ({"verified":False},{"approved":False}):
        sender,sends,checks=ready_sender(**config)
        assert not sender.provider_ready()
        assert sender.send_verification(
            recipient=EMAIL,confirm_link=CONFIRM,unsubscribe_link=STOP
        ) is None
        assert sends==[] and checks==[]


def test_suppressed_person_cannot_reach_provider():
    sender,sends,checks=ready_sender(suppressed=True)
    assert sender.send_verification(
        recipient=EMAIL,confirm_link=CONFIRM,unsubscribe_link=STOP
    ) is None
    assert sends==[]
    assert checks==[EMAIL]


def test_suppression_lookup_failure_fails_closed():
    sender,sends,checks=ready_sender()
    def bad_lookup(_):
        raise RuntimeError("CONNECTION_FAILED")
    sender.current_suppression_clear=bad_lookup
    assert sender.send_verification(
        recipient=EMAIL,confirm_link=CONFIRM,unsubscribe_link=STOP
    ) is None
    assert sends==[]


def test_bad_link_or_unknown_recipient_never_transmitted():
    sender,sends,checks=ready_sender()
    with pytest.raises(ValueError):
        sender.send_verification(
            recipient=EMAIL,
            confirm_link="https://attacker.invalid/confirm#"+"A"*43,
            unsubscribe_link=STOP,
        )
    with pytest.raises(ValueError):
        sender.send_verification(
            recipient="invalid\naddress@example.test",
            confirm_link=CONFIRM,unsubscribe_link=STOP,
        )
    assert sends==[]


def test_provider_failures_or_bad_receipt_do_not_claim_delivery():
    sender,sends,checks=ready_sender()
    def bad_provider(**kwargs):
        raise RuntimeError("NO_NETWORK")
    sender.provider=bad_provider
    assert sender.send_verification(
        recipient=EMAIL,confirm_link=CONFIRM,unsubscribe_link=STOP
    ) is None
    sender.provider=lambda **_: {"id":"not-a-valid-id"}
    assert sender.send_verification(
        recipient=EMAIL,confirm_link=CONFIRM,unsubscribe_link=STOP
    ) is None


def test_key_never_appears_in_sender_repr():
    sender,_,_=ready_sender()
    assert TEST_KEY not in repr(sender)


def test_secret_domain_validation_and_suppression_callback_required():
    sender,_,_=ready_sender()
    sender.sender_address="attacker@external.example"
    assert not sender.provider_ready()
    sender.sender_address="updates@mail.empire-ai.co.uk"
    sender.current_suppression_clear=None
    assert not sender.provider_ready()
    sender.current_suppression_clear=lambda _:True
    sender.api_key="invalid"
    assert not sender.provider_ready()

def test_private_subscriber_service_can_use_governed_resend_mock_only():
    from datetime import datetime, timezone
    from empire_os.consumer_optin_private_service import Keys, PrivateConsumerOptinService
    from tests.test_consumer_optin_private_backend_20261020 import FakeStore
    keys=Keys(email_hmac=b"A"*32,token_hmac=b"B"*32,
              email_encryption=b"C"*32,email_key_reference="consumer-key-v1")
    store=FakeStore()
    sender,requests,checks=ready_sender()
    svc=PrivateConsumerOptinService(
        keys=keys,store=store,sender=sender,
        clock=lambda:datetime(2026,10,20,20,0,tzinfo=timezone.utc))
    consent={
        "offer_slug":"roofing-cost-guide",
        "source":"EMPIRE_OWNED_PUBLIC_ROOFING_GUIDE",
        "notice_version":"roofing-homeowner-updates-v1",
        "own_brand_updates":"explicit_true",
        "third_party_buyer_sharing":"explicit_false",
    }
    assert svc.independently_ready()
    assert svc.request_verification(
        email=EMAIL,notice_version="roofing-homeowner-updates-v1",
        consent_receipt=consent,
    )
    assert len(requests)==1 and checks==[EMAIL]
    assert len(store.provider)==1
    assert len(store.provider[0]["provider_receipt"])==64
    assert ACCEPTED not in str(store.provider)


def test_sender_confirmation_requires_no_fake_app_key():
    sender,requests,checks=ready_sender()
    sender.api_key=""
    assert not sender.provider_ready()
    assert sender.send_verification(
        recipient=EMAIL,confirm_link=CONFIRM,unsubscribe_link=STOP
    ) is None
    assert requests==[] and checks==[]
