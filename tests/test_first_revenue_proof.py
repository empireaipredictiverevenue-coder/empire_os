from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.first_revenue_api import create_first_revenue_router
from empire_os.first_revenue_proof import (
    FirstRevenueEvidence,
    assess_first_revenue_readiness,
)


def evidence(**overrides):
    values = {
        "buyer_identity_verified": True,
        "commercial_terms_verified": True,
        "human_approval_recorded": True,
        "outbound_intent_approved": True,
        "send_evidence_verified": False,
        "delivery_evidence_verified": False,
        "agreement_evidence_verified": False,
        "usdt_bsc_payment_verified": False,
        "fulfilment_delivery_verified": False,
        "outcome_evidence_verified": False,
        "revenue_recognized": False,
        "evidence_refs": ("buyer:b1", "approval:a1"),
    }
    values.update(overrides)
    return FirstRevenueEvidence(**values)


def test_outbound_readiness_is_separate_from_revenue_proof():
    result = assess_first_revenue_readiness(evidence())
    assert result.ready_for_outbound is True
    assert result.ready_for_payment_acceptance is False
    assert result.first_revenue_proven is False
    assert "send_evidence_missing" in result.blockers


def test_payment_readiness_requires_delivery_and_agreement():
    result = assess_first_revenue_readiness(
        evidence(
            send_evidence_verified=True,
            delivery_evidence_verified=True,
            agreement_evidence_verified=True,
        )
    )
    assert result.ready_for_payment_acceptance is True
    assert result.ready_for_fulfilment is False
    assert "usdt_bsc_payment_not_verified" in result.blockers


def test_verified_payment_unlocks_fulfilment_readiness_only():
    result = assess_first_revenue_readiness(
        evidence(
            send_evidence_verified=True,
            delivery_evidence_verified=True,
            agreement_evidence_verified=True,
            usdt_bsc_payment_verified=True,
        )
    )
    assert result.ready_for_fulfilment is True
    assert result.ready_for_outcome_recognition is False
    assert result.first_revenue_proven is False


def test_full_real_evidence_chain_proves_first_revenue():
    result = assess_first_revenue_readiness(
        evidence(
            send_evidence_verified=True,
            delivery_evidence_verified=True,
            agreement_evidence_verified=True,
            usdt_bsc_payment_verified=True,
            fulfilment_delivery_verified=True,
            outcome_evidence_verified=True,
            revenue_recognized=True,
        )
    )
    assert result.ready_for_outcome_recognition is True
    assert result.first_revenue_proven is True
    assert result.blockers == ()
    assert result.execution_authority == "none"


def test_api_preview_never_executes_commercial_actions():
    app = FastAPI()
    app.include_router(create_first_revenue_router())
    client = TestClient(app)
    response = client.post(
        "/v1/first-revenue/readiness/preview",
        json={
            "buyer_identity_verified": True,
            "commercial_terms_verified": True,
            "human_approval_recorded": True,
            "outbound_intent_approved": True,
            "evidence_refs": ["buyer:b1", "approval:a1"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["outbound_execution"] is False
    assert body["payment_execution"] is False
    assert body["revenue_mutation"] is False
