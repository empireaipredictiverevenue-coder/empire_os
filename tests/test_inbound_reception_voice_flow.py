"""Contract tests for signed multi-turn receptionist, independent of live routing."""
from datetime import datetime, timezone
from hashlib import sha256
import json

import jwt
import pytest
from fastapi.testclient import TestClient

from empire_os.inbound_provider_contract import InboundNumberRoute
from empire_os.inbound_reception_call_flow import (
    InboundReceptionCallEngine, build_ncco, extract_input, intent_from_speech,
)
from empire_os.inbound_reception_voice_api import create_inbound_reception_voice_app
from empire_os.inbound_revenue_recovery import TenantReceptionProfile


API = "https://reception.example.test/v1/inbound-reception/vonage/input"
SECRET = "synthetic-signature-secret-for-local-tests-only"
KEY = "synthetic-vonage-api-key"
APP = "synthetic-vonage-app-id"
ROOT = "/v1/inbound-reception/vonage"
CALL = "call-12345678"


def make_engine():
    return InboundReceptionCallEngine(
        routes=(InboundNumberRoute(
            tenant_id="alpha", business_name="Example Dental",
            e164_number="+442012345678", number_ownership_verified=True,
            inbound_enabled=True,
        ),),
        profiles={"alpha": TenantReceptionProfile(
            tenant_id="alpha", business_name="Example Dental",
            vertical="professional_services",
            services=("dental consultation", "teeth cleaning"),
            booking_integration_verified=False,
            human_transfer_configured=False,
            callback_capture_allowed=False,
        )},
        event_url=API,
    )


def signed(body: dict, nonce="test-signed-webhook-1", *, secret=SECRET):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    claims = {
        "iss": "Vonage", "api_key": KEY, "application_id": APP,
        "jti": nonce, "iat": int(datetime.now(timezone.utc).timestamp()),
        "payload_hash": sha256(raw).hexdigest(),
    }
    return raw, {
        "Authorization": "Bearer " + jwt.encode(claims, secret, algorithm="HS256"),
        "Content-Type": "application/json",
    }


def payload(**updates):
    data = {"to": "442012345678", "uuid": CALL}
    data.update(updates)
    return data


def test_signed_answer_speech_reply_appointment_not_falsely_booked():
    client = TestClient(create_inbound_reception_voice_app(
        engine=make_engine(), signature_secret=SECRET, api_key=KEY,
        application_id=APP, enabled=True,
    ))
    raw, headers = signed(payload())
    answer = client.post(ROOT + "/answer", content=raw, headers=headers)
    assert answer.status_code == 200
    actions = answer.json()
    assert [x["action"] for x in actions] == ["talk", "input"]
    assert "AI receptionist" in actions[0]["text"]
    assert actions[1]["eventUrl"] == [API]
    assert actions[1]["speech"]["saveAudio"] is False
    assert client.post(ROOT + "/answer", content=raw, headers=headers).json() == actions

    raw, headers = signed(payload(speech={"results":[
        {"text": "I need to book an appointment", "confidence": 0.95},
    ]}), nonce="test-signed-webhook-2")
    booked = client.post(ROOT + "/input", content=raw, headers=headers)
    assert booked.status_code == 200
    assert [x["action"] for x in booked.json()] == ["talk", "input"]
    assert "cannot confirm a time yet" in booked.json()[0]["text"]
    assert "What service do you need?" in booked.json()[0]["text"]
    assert client.post(ROOT + "/input", content=raw, headers=headers).json() == booked.json()


def test_optout_is_not_upsold_or_outbound():
    e = make_engine()
    e.answer(payload())
    flow = e.reply(payload(dtmf={"digits": "9"}))
    assert len(flow) == 1
    assert "stop this conversation" in flow[0]["text"]


def test_human_fallback_does_not_claim_live_transfer():
    e = make_engine()
    e.answer(payload())
    flow = e.reply(payload(dtmf={"digits": "0"}))
    assert "would you like to request a callback" in flow[0]["text"].lower()
    assert "have not placed a booking" in flow[0]["text"]
    assert all(a["action"] != "connect" for a in flow)


def test_silence_bounded_at_three_turns_no_spam_or_lead_capture():
    e = make_engine()
    e.answer(payload())
    silent = payload(speech={"results": []})
    assert len(e.reply(silent)) == 2
    assert len(e.reply(silent)) == 2
    last = e.reply(silent)
    assert len(last) == 1
    assert e.sessions[CALL].closed
    assert "haven't booked anything" in last[0]["text"]
    assert len(e.reply(silent)) == 1


def test_fails_closed_without_signed_webhook_or_enabled_did():
    client = TestClient(create_inbound_reception_voice_app(
        engine=make_engine(), signature_secret=SECRET, api_key=KEY,
        application_id=APP, enabled=True,
    ))
    assert client.post(ROOT + "/answer", json=payload()).status_code == 401
    raw, headers = signed(payload(to="441111111111"))
    assert client.post(ROOT + "/answer", content=raw, headers=headers).status_code == 422
    raw, headers = signed(payload(tenant_id="beta"), nonce="other-jti")
    assert client.post(ROOT + "/answer", content=raw, headers=headers).status_code == 422
    assert client.get("/health").json()["booking_live"] is False


def test_wrong_signature_and_tampered_body_never_mutate_session():
    engine = make_engine()
    client = TestClient(create_inbound_reception_voice_app(
        engine=engine, signature_secret=SECRET, api_key=KEY,
        application_id=APP, enabled=True,
    ))
    raw, headers = signed(payload(), secret="not-the-right-signature-secret-32-bytes")
    assert client.post(ROOT + "/answer", content=raw, headers=headers).status_code == 401
    raw, headers = signed(payload())
    assert client.post(ROOT + "/answer", content=raw + b" ", headers=headers).status_code == 401
    assert engine.sessions == {}


def test_repeated_jti_with_changed_valid_body_rejected_without_second_turn():
    engine = make_engine()
    client = TestClient(create_inbound_reception_voice_app(
        engine=engine, signature_secret=SECRET, api_key=KEY,
        application_id=APP, enabled=True,
    ))
    raw, headers = signed(payload())
    assert client.post(ROOT + "/answer", content=raw, headers=headers).status_code == 200
    changed, changed_headers = signed(payload(uuid="other-1234567"), nonce="test-signed-webhook-1")
    assert client.post(ROOT + "/answer", content=changed, headers=changed_headers).status_code == 409
    assert len(engine.sessions) == 1


def test_dark_app_returns_404_even_with_valid_signature():
    client = TestClient(create_inbound_reception_voice_app(
        engine=make_engine(), signature_secret=SECRET, api_key=KEY,
        application_id=APP,
    ))
    raw, headers = signed(payload())
    assert client.post(ROOT + "/answer", content=raw, headers=headers).status_code == 404
    assert client.get("/health").json()["state"] == "disabled"


@pytest.mark.parametrize("text, expected", [
    ("please STOP messaging", "opt_out"),
    ("there is an emergency", "emergency"),
    ("I need to speak to a person", "human"),
    ("book an appointment", "book"),
    ("can you call me back", "callback"),
    ("how much is it", "unknown"),
    ("roof leak", "unknown"),
])
def test_intent_is_conservative(text, expected):
    assert intent_from_speech(text) == expected


def test_low_confidence_speech_is_not_invented():
    assert extract_input({"speech":{"results":[
        {"text":"book now", "confidence":"0.13"}
    ]}}) == "unknown"
    assert extract_input({"speech":{"error":"recognition_failed", "results":[
        {"text":"appointment","confidence":0.99}
    ]}}) == "unknown"


def test_cross_tenant_did_and_call_id_session_fails():
    e = make_engine()
    e.answer(payload())
    with pytest.raises(ValueError, match="unregistered_inbound"):
        e.reply(payload(to="447123456789", dtmf={"digits":"1"}))


def test_ncco_rejects_insecure_event_webhooks():
    with pytest.raises(ValueError, match="requires_explicit_https"):
        build_ncco("Hello", "http://local.test/v1/inbound-reception/vonage/input")
    with pytest.raises(ValueError, match="requires_explicit_https"):
        build_ncco("Hello", "https://example.test/attacker")



def customer_says(text, *, confidence=0.97, **other):
    return payload(
        speech={"results": [{"text": text, "confidence": confidence}]},
        **other,
    )


def test_multiturn_appointment_prepares_private_scoped_enquiry_no_outbound():
    from dataclasses import asdict
    engine = make_engine()
    engine.answer(payload())
    assert len(engine.reply(customer_says("book an appointment"))) == 2
    assert len(engine.reply(customer_says("I need teeth cleaning"))) == 2
    assert len(engine.reply(payload(dtmf={"digits": "2"}))) == 2
    assert len(engine.reply(customer_says("yes you may contact me"))) == 1
    record, = engine.review_handoffs_for_tenant("alpha")
    assert record.enquiry_type == "appointment"
    assert record.requested_service == "teeth_cleaning"
    assert record.preferred_time_window == "afternoon"
    assert record.caller_consented_to_review is True
    assert record.crm_write_performed is False
    assert record.outbound_authorized is False
    assert record.appointment_confirmed is False
    assert record.contact_identity_included is False
    assert record.status == "PENDING_HUMAN_REVIEW_NOT_SUBMITTED"
    assert len(record.enquiry_id) == 64
    assert "I need teeth cleaning" not in str(asdict(record))
    assert "yes you may contact me" not in str(asdict(record))
    assert len(engine.reply(customer_says("yes you may contact me"))) == 1
    assert len(engine.review_handoffs_for_tenant("alpha")) == 1


def test_declined_followup_consent_creates_no_crm_handoff():
    engine = make_engine()
    engine.answer(payload())
    engine.reply(payload(dtmf={"digits": "1"}))
    engine.reply(customer_says("dental consultation"))
    engine.reply(customer_says("anytime"))
    final = engine.reply(payload(dtmf={"digits": "2"}))
    assert len(final) == 1
    assert "won't prepare this enquiry" in final[0]["text"]
    assert engine.sessions[CALL].closed
    assert engine.review_handoffs_for_tenant("alpha") == ()


def test_unprompted_or_premature_yes_never_authorizes_handoff():
    engine = make_engine()
    engine.answer(payload())
    assert len(engine.reply(customer_says("yes"))) == 2
    engine.reply(customer_says("appointment"))
    assert engine.review_handoffs_for_tenant("alpha") == ()
    # Explicit consent cannot substitute for an approved service selection.
    assert len(engine.reply(customer_says("yes you may contact me"))) == 2
    assert engine.review_handoffs_for_tenant("alpha") == ()


@pytest.mark.parametrize("interrupt", [
    "stop", "I want to opt out", "I need to speak to a person",
    "this is an emergency",
])
def test_optout_emergency_human_interrupt_before_handoff(interrupt):
    engine = make_engine()
    engine.answer(payload())
    engine.reply(customer_says("book an appointment"))
    engine.reply(customer_says("teeth cleaning"))
    ended = engine.reply(customer_says(interrupt))
    assert len(ended) == 1
    assert engine.sessions[CALL].closed
    assert engine.sessions[CALL].requested_service == ""
    assert engine.review_handoffs_for_tenant("alpha") == ()


def test_unverified_service_never_claims_to_recognize_it():
    engine = make_engine()
    engine.answer(payload())
    engine.reply(customer_says("book an appointment"))
    for i in range(2):
        assert len(engine.reply(customer_says("expensive medicine and legal advice"))) == 2
    assert len(engine.reply(customer_says("expensive medicine and legal advice"))) == 1
    assert engine.sessions[CALL].closed
    assert engine.review_handoffs_for_tenant("alpha") == ()


def test_invalid_or_ambiguous_preference_no_draft():
    engine = make_engine()
    engine.answer(payload())
    engine.reply(customer_says("book an appointment"))
    engine.reply(customer_says("teeth cleaning"))
    assert len(engine.reply(customer_says("morning or evening"))) == 2
    assert engine.sessions[CALL].intake_stage == "window"
    assert engine.review_handoffs_for_tenant("alpha") == ()


def test_review_handoffs_never_leak_to_wrong_tenant():
    from empire_os.inbound_provider_contract import InboundNumberRoute
    profile_a = TenantReceptionProfile(
        tenant_id="alpha", business_name="Alpha Dental",
        services=("teeth cleaning",),
    )
    profile_b = TenantReceptionProfile(
        tenant_id="beta", business_name="Beta Roofing",
        services=("roof inspection",),
    )
    engine = InboundReceptionCallEngine(
        routes=(
            InboundNumberRoute(
                tenant_id="alpha", business_name=profile_a.business_name,
                e164_number="+442012345678",
                number_ownership_verified=True, inbound_enabled=True,
            ),
            InboundNumberRoute(
                tenant_id="beta", business_name=profile_b.business_name,
                e164_number="+442099999888",
                number_ownership_verified=True, inbound_enabled=True,
            ),
        ),
        profiles={"alpha": profile_a, "beta": profile_b},
        event_url=API,
    )
    engine.answer(payload())
    engine.reply(customer_says("appointment"))
    engine.reply(customer_says("teeth cleaning"))
    engine.reply(customer_says("morning"))
    engine.reply(customer_says("yes you may contact me"))
    assert len(engine.review_handoffs_for_tenant("alpha")) == 1
    assert engine.review_handoffs_for_tenant("beta") == ()
    with pytest.raises(ValueError, match="unregistered_reception_tenant"):
        engine.review_handoffs_for_tenant("third-party")
