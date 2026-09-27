from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_readiness import assess_close_readiness


def ready_row():
    return {
        "prospect_id": "prospect-1",
        "conversation_id": "conversation-1",
        "conversation_state": "engaged",
        "closer_case_id": "case-1",
        "closer_state": "proposal_ready",
        "price_cents": 25000,
        "buyer_id": "buyer-1",
        "buyer_activation_state": "activated",
        "buyer_available_capacity": 3,
        "buyer_capacity_verified_at": "2026-09-20T10:00:00+00:00",
        "fulfilment_order_id": "order-1",
        "fulfilment_state": "accepted",
    }


class FakeRepository:
    def prospect(self, prospect_id):
        return ready_row() if prospect_id == "prospect-1" else None

    def prospects(self, *, limit):
        return [ready_row()][:limit]

    def buyers(self, *, limit):
        return []


def test_complete_observed_state_is_review_ready():
    result = assess_close_readiness(ready_row())
    assert result.ready_for_operator_close_review is True
    assert result.blockers == ()
    assert result.execution_authority == "none"
    assert result.follow_up_execution is False
    assert result.payment_execution is False
    assert result.crm_mutation is False


def test_missing_verified_capacity_blocks_close_review():
    row = ready_row()
    row["buyer_capacity_verified_at"] = None
    result = assess_close_readiness(row)
    assert result.ready_for_operator_close_review is False
    assert "verified_buyer_capacity_missing" in result.blockers


def test_missing_price_and_fulfilment_are_explicit_blockers():
    row = ready_row()
    row["price_cents"] = None
    row["fulfilment_order_id"] = None
    row["fulfilment_state"] = None
    result = assess_close_readiness(row)
    assert "verified_commercial_price_missing" in result.blockers
    assert "fulfilment_readiness_not_verified" in result.blockers


def test_api_close_readiness_is_read_only():
    app = FastAPI()
    app.include_router(create_revenue_crm_router(FakeRepository()))
    response = TestClient(app).get(
        "/v1/revenue-crm/prospects/prospect-1/close-readiness"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"
    assert body["payment_execution"] is False
    assert body["crm_mutation"] is False
    assert body["readiness"]["ready_for_operator_close_review"] is True
