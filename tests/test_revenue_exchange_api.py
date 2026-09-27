from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_exchange_api import create_revenue_exchange_router


class FakeRepository:
    def observations(self, *, limit):
        return [{
            "niche": "roofing",
            "metro": "London",
            "qualified_inventory_count": 20,
            "active_buyer_capacity": 10,
            "verified_price_per_lead_cents": [7500, 10000, 12500],
            "observed_at": "2026-09-19T18:40:00+00:00",
            "source": "canonical_exchange_projection",
        }][:limit]


def client(repository=None):
    app = FastAPI()
    app.include_router(create_revenue_exchange_router(repository))
    return TestClient(app)


def test_health_is_observe_only():
    response = client().get("/v1/revenue-exchange/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["allocation_authority"] == "none"
    assert body["settlement_authority"] == "none"
    assert body["pricing_authority"] == "none"


def test_market_read_returns_observed_assessment():
    response = client(FakeRepository()).get(
        "/v1/revenue-exchange/markets?limit=10"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["allocation_authority"] == "none"
    item = body["items"][0]
    assert item["assessment"]["market_state"] == "inventory_heavy"
    assert item["assessment"]["supply_demand_ratio"] == 2.0
    assert item["snapshot"]["observed_price_floor_cents"] == 7500
    assert item["snapshot"]["observed_price_ceiling_cents"] == 12500


def test_missing_repository_fails_closed():
    response = client().get("/v1/revenue-exchange/markets")
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "revenue_exchange_repository_not_activated"
    )


def test_zero_capacity_stays_explicit():
    class ZeroCapacityRepository(FakeRepository):
        def observations(self, *, limit):
            rows = list(super().observations(limit=limit))
            rows[0]["active_buyer_capacity"] = 0
            return rows

    response = client(ZeroCapacityRepository()).get(
        "/v1/revenue-exchange/markets"
    )
    assert response.status_code == 200
    assessment = response.json()["items"][0]["assessment"]
    assert assessment["market_state"] == "no_verified_capacity"
    assert assessment["supply_demand_ratio"] is None
