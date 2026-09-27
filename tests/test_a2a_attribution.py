from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.a2a_attribution import (
    A2ACommercialAttributionEvidence,
    review_a2a_commercial_attribution,
)
from empire_os.a2a_commerce_api import create_a2a_commerce_router
from empire_os.a2a_settle_bridge import main as legacy_settle_main


def complete_evidence(**overrides):
    values = {
        "intent_id": "intent-1",
        "negotiation_id": "negotiation-1",
        "agent_id": "agent-buyer-1",
        "manual_handoff_ref": "handoff:1",
        "fulfilment_order_ref": "fulfilment:order:1",
        "payment_request_ref": "bsc:request:1",
        "verified_payment_ref": "bsc:payment:1",
        "commercial_outcome_ref": "outcome:1",
        "recognized_revenue_ref": "revenue:recognized:1",
        "realized_gp_cents": 4200,
    }
    values.update(overrides)
    return A2ACommercialAttributionEvidence(**values)


def test_full_observed_chain_is_attribution_ready_without_authority():
    review = review_a2a_commercial_attribution(complete_evidence())
    assert review.revenue_attribution_ready is True
    assert review.gross_profit_attribution_ready is True
    assert review.blockers == ()
    assert review.realized_gp_cents == 4200
    assert review.execution_authority == "none"
    assert review.payment_authority is False
    assert review.revenue_mutation is False
    assert review.accounting_mutation is False


def test_verified_payment_alone_is_not_revenue():
    review = review_a2a_commercial_attribution(
        complete_evidence(
            commercial_outcome_ref=None,
            recognized_revenue_ref=None,
            realized_gp_cents=None,
        )
    )
    assert review.revenue_attribution_ready is False
    assert "commercial_outcome_evidence_missing" in review.blockers
    assert "recognized_revenue_evidence_missing" in review.blockers


def test_recognized_revenue_without_verified_payment_is_blocked():
    review = review_a2a_commercial_attribution(
        complete_evidence(verified_payment_ref=None)
    )
    assert review.revenue_attribution_ready is False
    assert "verified_payment_evidence_missing" in review.blockers


def test_revenue_can_be_attributed_while_gp_remains_unknown():
    review = review_a2a_commercial_attribution(
        complete_evidence(realized_gp_cents=None)
    )
    assert review.revenue_attribution_ready is True
    assert review.gross_profit_attribution_ready is False
    assert "realized_gross_profit_evidence_missing" in review.blockers


def test_api_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_a2a_commerce_router())
    response = TestClient(app).post(
        "/v1/a2a-commerce/attribution/preview",
        json={
            "intent_id": "intent-1",
            "negotiation_id": "negotiation-1",
            "agent_id": "agent-buyer-1",
            "manual_handoff_ref": "handoff:1",
            "fulfilment_order_ref": "fulfilment:order:1",
            "payment_request_ref": "bsc:request:1",
            "verified_payment_ref": "bsc:payment:1",
            "commercial_outcome_ref": "outcome:1",
            "recognized_revenue_ref": "revenue:recognized:1",
            "realized_gp_cents": 4200,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["payment_authority"] is False
    assert body["revenue_mutation"] is False
    assert body["accounting_mutation"] is False
    assert body["attribution"]["revenue_attribution_ready"] is True


def test_empty_identity_is_rejected():
    app = FastAPI()
    app.include_router(create_a2a_commerce_router())
    response = TestClient(app).post(
        "/v1/a2a-commerce/attribution/preview",
        json={
            "intent_id": "",
            "negotiation_id": "negotiation-1",
            "agent_id": "agent-buyer-1",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "intent_id required"


def test_legacy_solana_usdc_settlement_bridge_is_hard_retired(capsys):
    assert legacy_settle_main() == 2
    assert "retired_legacy_a2a_solana_usdc_settlement" in capsys.readouterr().err
