from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.capital_api import create_capital_router


class FakeRepository:
    def __init__(self):
        self.rows = [{
            "candidate_key": "candidate-1",
            "risk_adjusted_score": 1.2,
            "confidence": 0.8,
            "recommendation_only": True,
            "execution_authority": "none",
        }]

    def recommendations(self, *, limit):
        return self.rows[:limit]

    def recommendation(self, candidate_key):
        return next(
            (
                row for row in self.rows
                if row["candidate_key"] == candidate_key
            ),
            None,
        )


def client(repository=None):
    app = FastAPI()
    app.include_router(create_capital_router(repository))
    return TestClient(app)


def test_health_is_recommendation_only():
    response = client().get("/v1/capital/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    assert body["funds_movement"] is False
    assert body["budget_mutation"] is False


def test_recommendation_list_is_bounded_and_non_executing():
    response = client(FakeRepository()).get(
        "/v1/capital/recommendations?limit=10"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["limit"] == 10
    assert body["execution_authority"] == "none"
    assert body["funds_movement"] is False


def test_recommendation_detail_is_read_only():
    response = client(FakeRepository()).get(
        "/v1/capital/recommendations/candidate-1"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["candidate_key"] == "candidate-1"
    assert body["recommendation_only"] is True
    assert body["budget_mutation"] is False


def test_missing_repository_fails_closed():
    response = client().get("/v1/capital/recommendations")
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "capital_review_repository_not_activated"
    )


def test_unknown_candidate_returns_404():
    response = client(FakeRepository()).get(
        "/v1/capital/recommendations/missing"
    )
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "capital_recommendation_not_found"
    )
