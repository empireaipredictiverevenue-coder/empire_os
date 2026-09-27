from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.outreach_api import create_outreach_router


def client():
    app = FastAPI()
    app.include_router(create_outreach_router())
    return TestClient(app)


def test_health_exposes_zero_execution_authority():
    body = client().get("/v1/outreach/health").json()
    assert body["mode"] == "OBSERVE"
    assert body["send_enabled"] is False
    assert body["voice_dial_enabled"] is False
    assert body["execution_authority"] == "none"


def test_packet_preview_is_review_only():
    response = client().post(
        "/v1/outreach/packet/preview",
        json={
            "account": {
                "account_id": "acct-1",
                "business_name": "Northstar Roofing",
                "contact_name": "Jane Smith",
                "contact_title": "Owner",
            },
            "contact_plan": {
                "outreach_ready": True,
                "preferred_email": "jane@northstar.example",
            },
            "context": {
                "outreach_ready": True,
                "bound_to_decision_maker": True,
                "suppressed": False,
                "offer_key": "territory-seat",
                "corridor_key": "roofing:manchester:exclusive",
                "territory": "Manchester",
            },
            "signals": [{
                "signal_type": "permit",
                "summary": "Recent evidence-backed permit activity in the target territory.",
                "source": "permit-radar",
                "observed_at": "2026-09-19T20:00:00+00:00",
                "confidence": 0.9,
                "evidence_ref": "permit:123",
            }],
            "proof_refs": ["proof:permit:123"],
            "predicted_economics": {
                "prediction_ref": "pred-1",
                "expected_revenue_cents": 100000,
                "expected_cost_cents": 25000,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["send_enabled"] is False
    assert body["review_ready"] is True
    assert body["predicted_economics"]["expected_gross_profit_cents"] == 75000


def test_missing_account_identity_is_rejected():
    response = client().post(
        "/v1/outreach/packet/preview",
        json={
            "account": {},
            "contact_plan": {},
            "context": {},
        },
    )
    assert response.status_code == 422


def test_reply_preview_never_executes():
    body = client().post(
        "/v1/outreach/reply-next-action/preview",
        json={"classification": "positive"},
    ).json()
    assert body["recommended_action"] == "closer_review"
    assert body["automatic_send"] is False
    assert body["execution_authority"] == "none"
