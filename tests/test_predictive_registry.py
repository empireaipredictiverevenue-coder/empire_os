from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.predictive_api import create_predictive_router
from empire_os.predictive_registry_transport import (
    PostgresPredictiveRegistryRpc,
    PredictiveRegistryTransportError,
    RpcPredictiveRegistryRepository,
)


class FakeRepository:
    def __init__(self):
        self.rows = {}

    def record(self, item):
        item.validate()
        if item.forecast_key in self.rows:
            return {
                "status": "existing",
                "forecast_id": self.rows[item.forecast_key]["forecast_id"],
            }
        row = {
            "forecast_id": f"forecast-{len(self.rows)+1}",
            "metric": item.forecast.metric,
            "direction": item.forecast.direction,
            "model_name": item.model_name,
            "model_version": item.model_version,
        }
        self.rows[item.forecast_key] = row
        return {"status": "recorded", **row}

    def list_forecasts(self, *, limit):
        return list(self.rows.values())[:limit]


def client(repo=None):
    app = FastAPI()
    app.include_router(create_predictive_router(repo))
    return TestClient(app)


def preview_points(n=7):
    return [
        {
            "observed_date": f"2026-09-{day:02d}",
            "value": float(100 + day * 5),
            "source": "canonical_daily_actual",
        }
        for day in range(1, n + 1)
    ]


def register_body(n=7):
    return {
        "forecast_key": "revenue-global-7d-v1",
        "model_name": "directional-linear",
        "model_version": "1.0.0",
        "dimension_key": "global",
        "preview": {
            "metric": "revenue_cents",
            "horizon_days": 7,
            "points": preview_points(n),
        },
        "evidence": {"dataset": "daily_actuals"},
    }


def test_unbound_registry_fails_closed():
    response = client().post(
        "/v1/predictive/forecast/register",
        json=register_body(),
    )
    assert response.status_code == 503


def test_evidence_backed_forecast_registers_without_execution():
    repo = FakeRepository()
    response = client(repo).post(
        "/v1/predictive/forecast/register",
        json=register_body(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recorded"
    assert body["execution_authority"] == "none"
    assert body["commercial_execution"] is False
    assert body["forecast"]["available"] is True
    assert body["forecast"]["sample_count"] == 7


def test_insufficient_history_is_not_persisted():
    repo = FakeRepository()
    response = client(repo).post(
        "/v1/predictive/forecast/register",
        json=register_body(6),
    )
    assert response.status_code == 422
    assert "only available forecasts" in response.json()["detail"]
    assert repo.rows == {}


def test_registry_is_idempotent_and_read_only():
    repo = FakeRepository()
    c = client(repo)
    first = c.post("/v1/predictive/forecast/register", json=register_body())
    second = c.post("/v1/predictive/forecast/register", json=register_body())
    listing = c.get("/v1/predictive/forecasts")
    assert first.status_code == 200
    assert second.json()["status"] == "existing"
    assert listing.status_code == 200
    assert listing.json()["read_only"] is True
    assert listing.json()["execution_authority"] == "none"
    assert listing.json()["count"] == 1


def test_rpc_repository_maps_model_and_provenance():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "forecast_id": "f1"}

    repo = RpcPredictiveRegistryRepository(rpc)
    app = FastAPI()
    class Wrapper:
        def record(self, item):
            return repo.record(item)
        def list_forecasts(self, *, limit):
            return []
    app.include_router(create_predictive_router(Wrapper()))
    response = TestClient(app).post(
        "/v1/predictive/forecast/register",
        json=register_body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_model_name"] == "directional-linear"
    assert params["p_model_version"] == "1.0.0"
    assert params["p_sample_count"] == 7


def test_transport_rejects_commercial_execution_rpc_before_connect():
    rpc = PostgresPredictiveRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        PredictiveRegistryTransportError,
        match="cannot execute",
    ):
        rpc("allocate_capital_from_forecast", {})
