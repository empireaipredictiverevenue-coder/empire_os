from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_retention import (
    RevenueCrmRetentionEvidence,
    assess_retention_expansion_readiness,
)


def evidence(**overrides):
    values = {
        "buyer_id": "buyer-1",
        "buyer_activated": True,
        "buyer_evidence_ref": "buyer:buyer-1",
        "payment_verified": True,
        "payment_evidence_ref": "payment:usdt-bsc:1",
        "fulfilment_delivered": True,
        "fulfilment_evidence_ref": "fulfilment:order-1",
        "outcome_observed": True,
        "outcome_success_verified": True,
        "outcome_evidence_ref": "outcome:order-1",
        "buyer_available_capacity": 4,
        "capacity_evidence_ref": "capacity:buyer-1",
    }
    values.update(overrides)
    return RevenueCrmRetentionEvidence(**values)


def test_complete_real_evidence_is_retention_and_expansion_ready():
    result = assess_retention_expansion_readiness(evidence())
    assert result.retention_review_ready is True
    assert result.expansion_review_ready is True
    assert result.retention_blockers == ()
    assert result.expansion_blockers == ()
    assert result.execution_authority == "none"
    assert result.follow_up_execution is False
    assert result.payment_execution is False
    assert result.crm_mutation is False
    assert result.offer_mutation is False


def test_unknown_outcome_success_preserves_unknown_expansion_state():
    result = assess_retention_expansion_readiness(
        evidence(outcome_success_verified=None)
    )
    assert result.retention_review_ready is True
    assert result.expansion_review_ready is False
    assert result.expansion_blockers == ("successful_outcome_unknown",)


def test_missing_payment_blocks_retention_and_expansion():
    result = assess_retention_expansion_readiness(
        evidence(
            payment_verified=False,
            payment_evidence_ref=None,
        )
    )
    assert result.retention_review_ready is False
    assert result.expansion_review_ready is False
    assert "verified_payment_evidence_missing" in result.retention_blockers
    assert "verified_payment_evidence_missing" in result.expansion_blockers


def test_missing_capacity_blocks_expansion_only():
    result = assess_retention_expansion_readiness(
        evidence(
            buyer_available_capacity=None,
            capacity_evidence_ref=None,
        )
    )
    assert result.retention_review_ready is True
    assert result.expansion_review_ready is False
    assert result.expansion_blockers == (
        "verified_buyer_capacity_missing",
    )


def test_zero_verified_capacity_blocks_expansion():
    result = assess_retention_expansion_readiness(
        evidence(buyer_available_capacity=0)
    )
    assert result.retention_review_ready is True
    assert result.expansion_review_ready is False
    assert result.expansion_blockers == ("buyer_capacity_not_available",)


def test_unsuccessful_observed_outcome_does_not_enable_expansion():
    result = assess_retention_expansion_readiness(
        evidence(outcome_success_verified=False)
    )
    assert result.retention_review_ready is True
    assert result.expansion_review_ready is False
    assert result.expansion_blockers == (
        "successful_outcome_not_verified",
    )


def test_api_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_revenue_crm_router())
    response = TestClient(app).post(
        "/v1/revenue-crm/retention-expansion/preview",
        json={
            "buyer_id": "buyer-1",
            "buyer_activated": True,
            "buyer_evidence_ref": "buyer:buyer-1",
            "payment_verified": True,
            "payment_evidence_ref": "payment:usdt-bsc:1",
            "fulfilment_delivered": True,
            "fulfilment_evidence_ref": "fulfilment:order-1",
            "outcome_observed": True,
            "outcome_success_verified": True,
            "outcome_evidence_ref": "outcome:order-1",
            "buyer_available_capacity": 4,
            "capacity_evidence_ref": "capacity:buyer-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"
    assert body["follow_up_execution"] is False
    assert body["payment_execution"] is False
    assert body["crm_mutation"] is False
    assert body["offer_mutation"] is False
    assert body["readiness"]["retention_review_ready"] is True
    assert body["readiness"]["expansion_review_ready"] is True


def test_api_rejects_negative_capacity():
    app = FastAPI()
    app.include_router(create_revenue_crm_router())
    response = TestClient(app).post(
        "/v1/revenue-crm/retention-expansion/preview",
        json={
            "buyer_id": "buyer-1",
            "buyer_activated": True,
            "buyer_evidence_ref": "buyer:buyer-1",
            "payment_verified": True,
            "payment_evidence_ref": "payment:1",
            "fulfilment_delivered": True,
            "fulfilment_evidence_ref": "fulfilment:1",
            "outcome_observed": True,
            "outcome_success_verified": True,
            "outcome_evidence_ref": "outcome:1",
            "buyer_available_capacity": -1,
            "capacity_evidence_ref": "capacity:1",
        },
    )
    assert response.status_code == 422
