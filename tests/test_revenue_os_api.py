from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_os_api import create_revenue_os_router


class FakeRepository:
    def __init__(self):
        self.rows = [{
            "packet_key": "packet-1",
            "recommended_workstream": "buyer_allocation",
            "recommended_job_type": "plan_controlled_allocation",
            "forecast_direction": "up",
            "capital_candidate_id": "candidate-1",
            "demand_plan_ref": "demand-1",
            "enterprise_blockers": [],
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
        }]

    def packets(self, *, limit):
        return self.rows[:limit]

    def packet(self, packet_key):
        return next(
            (row for row in self.rows if row["packet_key"] == packet_key),
            None,
        )


def client(repository=None):
    app = FastAPI()
    app.include_router(create_revenue_os_router(repository))
    return TestClient(app)


def test_health_exposes_observe_only_contract():
    response = client().get("/v1/revenue-os/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    assert body["repository_available"] is False


def test_board_is_bounded_and_read_only():
    response = client(FakeRepository()).get(
        "/v1/revenue-os/board?limit=10"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["limit"] == 10
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["items"][0]["packet_key"] == "packet-1"


def test_packet_detail_preserves_observe_only_fields():
    response = client(FakeRepository()).get(
        "/v1/revenue-os/packets/packet-1"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["packet"]["execution_authority"] == "none"


def test_missing_repository_fails_closed():
    response = client().get("/v1/revenue-os/board")
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "revenue_os_repository_not_activated"
    )


def test_unknown_packet_returns_404():
    response = client(FakeRepository()).get(
        "/v1/revenue-os/packets/missing"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "revenue_os_packet_not_found"
