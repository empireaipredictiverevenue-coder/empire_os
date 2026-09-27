from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.capital_api import create_capital_router
from empire_os.capital_registry import CapitalReviewRecord
from empire_os.capital_registry_transport import (
    CapitalRegistryTransportError,
    PostgresCapitalRegistryRpc,
    RpcCapitalRegistryRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record(self, item: CapitalReviewRecord):
        item.validate()
        if item.review_key in self.rows:
            return {
                "status": "existing",
                "review_id": self.rows[item.review_key]["review_id"],
            }
        row = {
            "review_id": f"review-{len(self.rows) + 1}",
            "review_key": item.review_key,
            "candidate_id": item.candidate.candidate_id,
            "review_eligible": item.review.review_eligible,
        }
        self.rows[item.review_key] = row
        return {"status": "recorded", **row}

    def list_reviews(self, *, limit):
        return list(self.rows.values())[:limit]


def client(registry=None):
    app = FastAPI()
    app.include_router(create_capital_router(registry=registry))
    return TestClient(app)


def body():
    return {
        "review_key": "candidate-1-policy-v1",
        "candidate_id": "candidate-1",
        "expected_return_cents": 30000,
        "required_capital_cents": 10000,
        "downside_loss_cents": 2000,
        "confidence": 0.8,
        "time_to_revenue_days": 30,
        "evidence_refs": ["forecast:f1", "market:m1"],
        "minimum_confidence": 0.5,
        "maximum_downside_ratio": 1.0,
        "minimum_risk_adjusted_score": 0.0,
        "evidence": {"source": "canonical_capital_evidence"},
    }


def test_unbound_registry_fails_closed():
    response = client().post("/v1/capital/reviews/register", json=body())
    assert response.status_code == 503


def test_review_registers_without_funds_authority():
    response = client(FakeRegistry()).post(
        "/v1/capital/reviews/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["recommendation_only"] is True
    assert data["execution_authority"] == "none"
    assert data["funds_movement"] is False
    assert data["budget_mutation"] is False


def test_registry_is_idempotent_and_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/capital/reviews/register", json=body())
    second = c.post("/v1/capital/reviews/register", json=body())
    listing = c.get("/v1/capital/reviews")
    assert first.status_code == 200
    assert second.json()["status"] == "existing"
    assert listing.status_code == 200
    assert listing.json()["read_only"] is True
    assert listing.json()["execution_authority"] == "none"
    assert listing.json()["count"] == 1


def test_registry_requires_evidence():
    payload = body()
    payload["evidence"] = {}
    response = client(FakeRegistry()).post(
        "/v1/capital/reviews/register",
        json=payload,
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]


def test_blocked_candidate_can_be_recorded_for_review_history():
    payload = body()
    payload["confidence"] = 0.2
    response = client(FakeRegistry()).post(
        "/v1/capital/reviews/register",
        json=payload,
    )
    assert response.status_code == 200
    review = response.json()["review_record"]["review"]
    assert review["review_eligible"] is False
    assert "confidence_below_policy" in review["blockers"]


def test_rpc_repository_maps_policy_and_review():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "review_id": "r1"}

    repo = RpcCapitalRegistryRepository(rpc)
    app = FastAPI()

    class Wrapper:
        def record(self, item):
            return repo.record(item)

        def list_reviews(self, *, limit):
            return []

    app.include_router(create_capital_router(registry=Wrapper()))
    response = TestClient(app).post(
        "/v1/capital/reviews/register",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_review_eligible"] is True
    assert params["p_minimum_confidence"] == 0.5
    assert params["p_evidence"]["source"] == "canonical_capital_evidence"


def test_transport_rejects_funds_execution_rpc_before_connect():
    rpc = PostgresCapitalRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        CapitalRegistryTransportError,
        match="cannot execute",
    ):
        rpc("move_capital", {})
