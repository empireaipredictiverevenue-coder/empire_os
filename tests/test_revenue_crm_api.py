from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import (
    create_revenue_crm_router,
    derive_next_action,
)


class FakeRepository:
    def __init__(self):
        self.prospect_rows = [{
            "prospect_id": "prospect-1",
            "conversation_id": "conversation-1",
            "conversation_state": "engaged",
            "conversation_updated_at": "2026-09-19T20:50:00+00:00",
            "closer_case_id": None,
            "closer_state": None,
            "closer_updated_at": None,
            "fulfilment_order_id": None,
            "fulfilment_state": None,
            "fulfilment_updated_at": None,
        }]
        self.buyer_rows = [{
            "buyer_id": "buyer-1",
            "available_capacity": 4,
        }]

    def prospects(self, *, limit):
        return self.prospect_rows[:limit]

    def buyers(self, *, limit):
        return self.buyer_rows[:limit]

    def prospect(self, prospect_id):
        return next(
            (
                row for row in self.prospect_rows
                if row["prospect_id"] == prospect_id
            ),
            None,
        )


def client(repository=None):
    app = FastAPI()
    app.include_router(
        create_revenue_crm_router(repository or FakeRepository())
    )
    return TestClient(app)


def test_read_endpoints_are_bounded_and_read_only():
    response = client().get("/v1/revenue-crm/prospects?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["source"] == "canonical_revenue_crm_repository"
    assert body["count"] == 1
    assert body["limit"] == 10


def test_buyer_read_endpoint_exposes_observed_capacity():
    response = client().get("/v1/revenue-crm/buyers")
    assert response.status_code == 200
    assert response.json()["items"][0]["available_capacity"] == 4


def test_next_action_cites_canonical_conversation_record():
    response = client().get(
        "/v1/revenue-crm/prospects/prospect-1/next-action"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "review_engaged_conversation"
    assert body["execution_authority"] == "none"
    assert body["approval_required"] is True
    assert body["evidence"] == [{
        "kind": "conversation",
        "record_id": "conversation-1",
        "state": "engaged",
        "observed_at": "2026-09-19T20:50:00+00:00",
        "detail": None,
    }]


def test_state_without_canonical_record_id_does_not_recommend():
    result = derive_next_action({
        "conversation_state": "engaged",
        "conversation_id": None,
        "closer_state": None,
        "fulfilment_state": None,
    })
    assert result.available is False
    assert result.action is None
    assert result.reason == "insufficient_observed_evidence"


def test_closer_action_cites_case_id_and_observed_time():
    result = derive_next_action({
        "closer_case_id": "case-1",
        "closer_state": "awaiting_payment",
        "closer_updated_at": "2026-09-19T20:55:00+00:00",
    })
    assert result.action == "review_payment_status"
    ref = result.evidence[0]
    assert ref.kind == "closer_case"
    assert ref.record_id == "case-1"
    assert ref.observed_at == "2026-09-19T20:55:00+00:00"


def test_verified_buyer_capacity_can_support_review():
    result = derive_next_action({
        "buyer_id": "buyer-1",
        "buyer_activation_state": "activated",
        "buyer_available_capacity": 3,
        "buyer_capacity_verified_at": "2026-09-19T20:58:00+00:00",
    })
    assert result.action == "review_buyer_capacity"
    assert result.evidence[0].detail == "available_capacity:3"


def test_unverified_or_unknown_buyer_capacity_does_not_recommend():
    unknown = derive_next_action({
        "buyer_id": "buyer-1",
        "buyer_activation_state": "activated",
        "buyer_available_capacity": None,
        "buyer_capacity_verified_at": None,
    })
    unverified = derive_next_action({
        "buyer_id": "buyer-1",
        "buyer_activation_state": "activated",
        "buyer_available_capacity": 3,
        "buyer_capacity_verified_at": None,
    })
    assert unknown.available is False
    assert unverified.available is False


def test_unknown_prospect_returns_404():
    response = client().get(
        "/v1/revenue-crm/prospects/missing/next-action"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "prospect_not_found"


def test_health_is_observe_only():
    app = FastAPI()
    app.include_router(create_revenue_crm_router())
    response = TestClient(app).get("/v1/revenue-crm/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"
    assert body["follow_up_execution"] is False
    assert body["payment_execution"] is False
    assert body["repository_available"] is False


def test_missing_repository_fails_closed():
    app = FastAPI()
    app.include_router(create_revenue_crm_router())
    response = TestClient(app).get("/v1/revenue-crm/prospects")
    assert response.status_code == 503
    assert response.json()["detail"] == "revenue_crm_repository_not_activated"
