"""Founder-corrected address, one authority and fail-closed existing outbound gates."""

from inspect import signature

from empire_os import business_contact_identity as identity
from empire_os import (
    closer_reply_draft,
    conversation_value,
    gtm_pipeline_worker,
    gtm_standing_bridge,
    outbound_governor,
)
from empire_os.outbound_governor import _body_checks
from empire_os.outbound_provider import (
    OutboundProviderError,
    build_resend_send,
)
import pytest


CORRECT = "68 Wentbridge Road, Bolton, BL1 2QR, UK"
OBSOLETE = "31 St Thomas St, Bolton, BL1 2QR, UK"


def test_confirmed_founder_trading_address_is_single_authority():
    assert identity.POSTAL_ADDRESS == CORRECT
    for module in (
        closer_reply_draft,
        conversation_value,
        gtm_pipeline_worker,
        gtm_standing_bridge,
        outbound_governor,
    ):
        assert module.POSTAL_ADDRESS == CORRECT
    assert signature(build_resend_send).parameters["required_postal_footer"].default == CORRECT


def test_governor_rejects_old_address_even_with_opt_out():
    assert "missing_approved_postal_footer" in _body_checks(
        "Hello. Reply opt out. " + OBSOLETE
    )
    assert _body_checks("Hello. Reply opt out. " + CORRECT) == []


def test_governor_accepts_correct_multiline_address():
    assert _body_checks(
        "Hello. Reply opt out. 68 Wentbridge Road\nBolton\nBL1 2QR\nUK"
    ) == []


def test_provider_rejects_old_footer_using_existing_authorized_contract(monkeypatch):
    monkeypatch.setattr(
        "empire_os.outbound_provider.require_no_commercial_hold",
        lambda _: None,
    )
    claim = {
        "decision": "authorized_send",
        "intent_id": "00000000-0000-0000-0000-000000000001",
        "channel": "email",
        "recipient": "buyer@example.com",
        "subject": "Address validity",
        "body_text": "Hello. Reply opt out. " + OBSOLETE,
        "actual_revenue": False,
    }
    options = {
        "sender": "Phil <phil@mail.empire-ai.co.uk>",
        "reply_to": "reply@mail.empire-ai.co.uk",
    }
    with pytest.raises(OutboundProviderError, match="approved postal footer required"):
        build_resend_send(claim, **options)
    claim["body_text"] = "Hello. Reply opt out. " + CORRECT
    assert build_resend_send(claim, **options)["text"].endswith(CORRECT)
