"""Run a synthetic signed two-webhook AI receptionist demonstration.

No external network, phone number lease, live webhook, customer contact,
recording, calendar access or monetary action. Prints only synthetic dialogue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import sys

from fastapi.testclient import TestClient

from empire_os.inbound_provider_contract import InboundNumberRoute
from empire_os.inbound_reception_call_flow import InboundReceptionCallEngine
from empire_os.inbound_reception_voice_api import create_inbound_reception_voice_app
from empire_os.inbound_reception_recovery_bridge import project_reception_recovery_review
from empire_os.inbound_revenue_recovery import TenantReceptionProfile

SIGNATURE_SECRET = "local-demo-synthetic-voice-signature-32-bytes"
API_KEY = "local-demo-key"
APPLICATION = "local-demo-app"
CALL_ID = "synthetic-voice-call-20261020"
DID = "+442099998888"
EVENT_URL = "https://synthetic.example.test/v1/inbound-reception/vonage/input"


def run_demo(intent: str = "appointment") -> dict:
    if intent not in ("appointment", "callback", "human", "stop", "unknown"):
        raise ValueError("demo_intent_not_permitted")
    from jwt import encode
    route = InboundNumberRoute(
        tenant_id="synthetic-demo-business",
        e164_number=DID, business_name="Empire Reception Demo",
        number_ownership_verified=True, inbound_enabled=True,
    )
    profile = TenantReceptionProfile(
        tenant_id=route.tenant_id,
        business_name=route.business_name,
        callback_capture_allowed=False, booking_integration_verified=False,
        human_transfer_configured=False,
        services=("roofing", "roof inspection", "gutter repair"),
    )
    engine = InboundReceptionCallEngine(
        (route,), {route.tenant_id: profile}, event_url=EVENT_URL,
    )
    app = create_inbound_reception_voice_app(
        engine=engine, signature_secret=SIGNATURE_SECRET,
        api_key=API_KEY, application_id=APPLICATION, enabled=True,
    )
    client = TestClient(app)

    def post(stage: str, data: dict, jti: str) -> list:
        raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        token = encode({
            "iss": "Vonage", "api_key": API_KEY,
            "application_id": APPLICATION, "jti": jti,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "payload_hash": sha256(raw).hexdigest(),
        }, SIGNATURE_SECRET, algorithm="HS256")
        response = client.post(
            "/v1/inbound-reception/vonage/" + stage,
            content=raw, headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            },
        )
        if response.status_code != 200:
            raise RuntimeError("synthetic_signed_demo_webhook_failed")
        return response.json()

    first = post("answer", {"to": DID, "uuid": CALL_ID}, "synthetic-answer-jti")
    speech = {
        "appointment": "I'd like to book an appointment",
        "callback": "Could you call me back?",
        "human": "I need to speak to a person",
        "stop": "I want to opt out and stop",
        "unknown": "I need a complicated quote with special prices",
    }[intent]
    second = post("input", {
        "to": DID, "uuid": CALL_ID,
        "speech": {"results": [{"text": speech, "confidence": 0.98}]},
    }, "synthetic-input-jti")
    steps = [a["action"] for a in first] + [a["action"] for a in second]
    closing = second
    if intent in ("appointment", "callback"):
        for index, customer_utterance in enumerate(
            ("roofing", "tomorrow morning", "yes, you may contact me"), start=2
        ):
            closing = post("input", {
                "to": DID, "uuid": CALL_ID,
                "speech": {"results": [
                    {"text": customer_utterance, "confidence": 0.98}
                ]},
            }, "synthetic-input-jti-" + str(index))
            steps.extend(a["action"] for a in closing)
    handoffs = engine.review_handoffs_for_tenant(route.tenant_id)
    recovery_review = project_reception_recovery_review(route.tenant_id, handoffs)
    return {
        "schema": "empire.ai-receptionist.signed-call-demo.v1",
        "status": "PASS_SYNTHETIC_SIGNED_WEBHOOK_CONVERSATION",
        "intent_synthetic": intent,
        "assistant_greeting": first[0]["text"],
        "caller_synthetic_speech": speech,
        "assistant_reply": closing[0]["text"],
        "review_draft_created": bool(handoffs),
        "review_draft_service": handoffs[0].requested_service if handoffs else None,
        "review_draft_window": handoffs[0].preferred_time_window if handoffs else None,
        "human_review_required": True,
        "reception_recovery_bridge_status": "READ_ONLY_OFFLINE_PROJECTION",
        "recovery_bridge_enquiry_count": recovery_review["enquiry_drafts_count"],
        "recovery_bridge_missed_calls": recovery_review["recovery_scorecard"]["missed_calls"],
        "recovery_bridge_verified_recovered_calls":
            recovery_review["recovery_scorecard"]["verified_recovered_calls"],
        "recovery_bridge_new_crm_prospects": recovery_review["new_crm_prospects"],
        "crm_write_performed": False,
        "steps": steps,
        "inbound_phone_call_completed": False,
        "voice_provider_connected": False,
        "appointment_booked": False,
        "callback_placed": False,
        "contact_recorded": False,
        "actual_revenue": False,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "--synthetic-only":
        print(json.dumps({"status": "HELD_SYNTHETIC_ONLY_FLAG_REQUIRED"}))
        return 2
    result = run_demo(argv[1])
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
