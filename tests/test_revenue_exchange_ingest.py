from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.revenue_exchange_api import create_revenue_exchange_router
from empire_os.revenue_exchange_transport import (
    PostgresRevenueExchangeRpc,
    RevenueExchangeTransportError,
    RpcRevenueExchangeRepository,
)


class FakeIngestRepository:
    def __init__(self):
        self.rows = {}

    def append(self, item):
        item.validate()
        if item.observation_key in self.rows:
            return {
                "status": "existing",
                "observation_id": self.rows[item.observation_key],
            }
        obs_id = f"obs-{len(self.rows) + 1}"
        self.rows[item.observation_key] = obs_id
        return {"status": "recorded", "observation_id": obs_id}


def client(repo=None):
    app = FastAPI()
    app.include_router(create_revenue_exchange_router(
        ingest_repository=repo
    ))
    return TestClient(app)


def body():
    return {
        "observation_key": "roofing-london-2026-09-19T2100",
        "row": {
            "niche": "roofing",
            "metro": "London",
            "qualified_inventory_count": 12,
            "active_buyer_capacity": 8,
            "verified_price_per_lead_cents": [12000, 15000],
            "observed_at": "2026-09-19T21:00:00+00:00",
            "source": "canonical_market_snapshot",
        },
        "evidence": {
            "inventory_source": "canonical_prospects",
            "capacity_source": "canonical_buyers",
        },
    }


def test_unbound_ingest_fails_closed():
    response = client().post(
        "/v1/revenue-exchange/observations/ingest",
        json=body(),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "revenue_exchange_ingest_not_activated"
    )


def test_market_observation_records_without_commercial_authority():
    response = client(FakeIngestRepository()).post(
        "/v1/revenue-exchange/observations/ingest",
        json=body(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "recorded"
    assert payload["allocation_authority"] == "none"
    assert payload["pricing_authority"] == "none"
    assert payload["settlement_authority"] == "none"


def test_market_observation_is_idempotent():
    repo = FakeIngestRepository()
    c = client(repo)
    first = c.post(
        "/v1/revenue-exchange/observations/ingest",
        json=body(),
    )
    second = c.post(
        "/v1/revenue-exchange/observations/ingest",
        json=body(),
    )
    assert first.status_code == 200
    assert second.json()["status"] == "existing"
    assert len(repo.rows) == 1


def test_invalid_verified_price_is_rejected():
    payload = body()
    payload["row"]["verified_price_per_lead_cents"] = [0]
    response = client(FakeIngestRepository()).post(
        "/v1/revenue-exchange/observations/ingest",
        json=payload,
    )
    assert response.status_code == 422
    assert "verified prices must be positive" in response.json()["detail"]


def test_rpc_repository_preserves_source_and_evidence():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "observation_id": "obs-1"}

    repo = RpcRevenueExchangeRepository(rpc)
    app = FastAPI()
    app.include_router(create_revenue_exchange_router(
        ingest_repository=repo
    ))
    response = TestClient(app).post(
        "/v1/revenue-exchange/observations/ingest",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_source"] == "canonical_market_snapshot"
    assert params["p_verified_price_per_lead_cents"] == [12000, 15000]
    assert params["p_evidence"]["capacity_source"] == "canonical_buyers"


def test_transport_rejects_allocation_rpc_before_connect():
    rpc = PostgresRevenueExchangeRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        RevenueExchangeTransportError,
        match="cannot execute",
    ):
        rpc("allocate_revenue_exchange_inventory", {})
