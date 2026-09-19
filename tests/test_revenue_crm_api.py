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
            "conversation_state": "engaged",
            "closer_state": None,
            "fulfilment_state": None,
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


def test_next_action_is_evidence_backed_and_non_executing():
    response = client().get(
        "/v1/revenue-crm/prospects/prospect-1/next-action"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "review_engaged_conversation"
    assert body["evidence"] == ["conversation_state:engaged"]
    assert body["execution_authority"] == "none"
    assert body["approval_required"] is True


def test_unknown_state_does_not_invent_next_action():
    result = derive_next_action({
        "conversation_state": None,
        "closer_state": None,
        "fulfilment_state": None,
    })
    assert result.available is False
    assert result.action is None
    assert result.reason == "insufficient_observed_evidence"


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
    assert (
        response.json()["detail"]
        == "revenue_crm_repository_not_activated"
    )
