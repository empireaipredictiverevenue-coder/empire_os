from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.first_revenue_api import create_first_revenue_router


def client():
    app = FastAPI()
    app.include_router(create_first_revenue_router())
    return TestClient(app)


def canonical_chain():
    return {
        "buyer": {
            "buyer_id": "buyer-1",
            "identity_verified_at": "2026-09-19T18:00:00+00:00",
            "commercial_terms_verified_at": "2026-09-19T18:05:00+00:00",
        },
        "outbound_intent": {
            "intent_id": "intent-1",
            "status": "approved",
            "approved_by": "operator-1",
            "approved_at": "2026-09-19T18:10:00+00:00",
        },
        "provider_events": [
            {
                "event_id": "sent-1",
                "event_type": "sent",
                "provider_verified": True,
            },
            {
                "event_id": "delivered-1",
                "event_type": "delivered",
                "signature_verified": True,
            },
        ],
        "agreement": {
            "agreement_id": "agreement-1",
            "status": "signed",
            "signed_at": "2026-09-19T18:20:00+00:00",
        },
        "payment": {
            "payment_id": "payment-1",
            "status": "verified",
            "chain": "bsc",
            "asset": "USDT",
            "verified_at": "2026-09-19T18:30:00+00:00",
        },
        "fulfilment": {
            "fulfilment_order_id": "order-1",
            "state": "delivered",
            "delivered_at": "2026-09-19T18:40:00+00:00",
        },
        "outcome": {
            "outcome_id": "outcome-1",
            "recorded_at": "2026-09-19T18:50:00+00:00",
        },
        "revenue_event": {
            "event_id": "rev-1",
            "event_type": "revenue_recognized",
            "actual_revenue": True,
            "amount_cents": 25000,
        },
    }


def test_canonical_evidence_endpoint_proves_full_chain_only():
    response = client().post(
        "/v1/first-revenue/readiness/from-canonical-evidence",
        json=canonical_chain(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["readiness"]["first_revenue_proven"] is True
    assert body["compiled_evidence"]["usdt_bsc_payment_verified"] is True
    assert body["execution_authority"] == "none"
    assert body["payment_execution"] is False
    assert body["revenue_mutation"] is False


def test_wrong_chain_stays_blocked():
    payload = canonical_chain()
    payload["payment"] = {
        "payment_id": "payment-1",
        "status": "verified",
        "chain": "solana",
        "asset": "USDC",
        "verified_at": "2026-09-19T18:30:00+00:00",
    }
    response = client().post(
        "/v1/first-revenue/readiness/from-canonical-evidence",
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["compiled_evidence"]["usdt_bsc_payment_verified"] is False
    assert body["readiness"]["first_revenue_proven"] is False
    assert (
        "usdt_bsc_payment_not_verified"
        in body["readiness"]["blockers"]
    )


def test_unverified_provider_delivery_stays_blocked():
    payload = canonical_chain()
    payload["provider_events"] = [{
        "event_id": "delivered-1",
        "event_type": "delivered",
        "provider_verified": False,
        "signature_verified": False,
    }]
    response = client().post(
        "/v1/first-revenue/readiness/from-canonical-evidence",
        json=payload,
    )
    body = response.json()
    assert body["compiled_evidence"]["send_evidence_verified"] is False
    assert body["compiled_evidence"]["delivery_evidence_verified"] is False
    assert body["readiness"]["first_revenue_proven"] is False


def test_empty_evidence_never_proves_revenue():
    response = client().post(
        "/v1/first-revenue/readiness/from-canonical-evidence",
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["readiness"]["first_revenue_proven"] is False
    assert body["compiled_evidence"]["evidence_refs"] == ["evidence:none"]
