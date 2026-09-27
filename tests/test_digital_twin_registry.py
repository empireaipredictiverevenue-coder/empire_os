from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.digital_twin_api import create_digital_twin_router
from empire_os.digital_twin_registry import DigitalTwinRegistryRecord
from empire_os.digital_twin_registry_transport import (
    DigitalTwinRegistryTransportError,
    PostgresDigitalTwinRegistryRpc,
    RpcDigitalTwinRegistryRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record(self, item: DigitalTwinRegistryRecord):
        item.validate()
        if item.scenario_key in self.rows:
            return {
                "status": "existing",
                "scenario_id": self.rows[item.scenario_key]["scenario_id"],
            }
        row = {
            "scenario_id": f"scenario-{len(self.rows) + 1}",
            "scenario_key": item.scenario_key,
            "projected_revenue_cents": (
                item.comparison.scenario.projected_revenue_cents
            ),
        }
        self.rows[item.scenario_key] = row
        return {"status": "recorded", **row}

    def list_scenarios(self, *, limit):
        return list(self.rows.values())[:limit]


def client(repo=None):
    app = FastAPI()
    app.include_router(create_digital_twin_router(repo))
    return TestClient(app)


def body():
    return {
        "scenario_key": "roofing-london-demand-up-v1",
        "baseline": {
            "niche": "roofing",
            "metro": "London",
            "observed_demand_units": 100,
            "observed_capacity_units": 80,
            "observed_price_per_unit_cents": 10000,
            "observed_at": "2026-09-19T20:00:00+00:00",
            "evidence_ref": "exchange:roofing-london:2026-09-19",
        },
        "scenario": {
            "scenario_id": "scenario-1",
            "demand_multiplier": 1.2,
            "capacity_multiplier": 1.1,
            "price_multiplier": 1.0,
        },
        "evidence": {"source": "canonical_market_observations"},
    }


def test_unbound_registry_fails_closed():
    response = client().post(
        "/v1/digital-twin/scenarios/register",
        json=body(),
    )
    assert response.status_code == 503


def test_simulation_registers_without_execution():
    response = client(FakeRegistry()).post(
        "/v1/digital-twin/scenarios/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["mode"] == "SIMULATION"
    assert data["simulation_only"] is True
    assert data["actual_revenue"] is False
    assert data["execution_authority"] == "none"
    assert data["capital_execution"] is False
    assert data["campaign_execution"] is False
    assert data["pricing_execution"] is False


def test_registry_is_idempotent_and_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post(
        "/v1/digital-twin/scenarios/register",
        json=body(),
    )
    second = c.post(
        "/v1/digital-twin/scenarios/register",
        json=body(),
    )
    listing = c.get("/v1/digital-twin/scenarios")
    assert first.status_code == 200
    assert second.json()["status"] == "existing"
    assert listing.status_code == 200
    assert listing.json()["read_only"] is True
    assert listing.json()["simulation_only"] is True
    assert listing.json()["count"] == 1


def test_registry_requires_evidence():
    payload = body()
    payload["evidence"] = {}
    response = client(FakeRegistry()).post(
        "/v1/digital-twin/scenarios/register",
        json=payload,
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]


def test_rpc_repository_maps_baseline_and_simulation_result():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "scenario_id": "s1"}

    repo = RpcDigitalTwinRegistryRepository(rpc)
    app = FastAPI()

    class Wrapper:
        def record(self, item):
            return repo.record(item)

        def list_scenarios(self, *, limit):
            return []

    app.include_router(create_digital_twin_router(Wrapper()))
    response = TestClient(app).post(
        "/v1/digital-twin/scenarios/register",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_baseline_evidence_ref"].startswith("exchange:")
    assert params["p_projected_revenue_cents"] > 0
    assert params["p_evidence"]["source"] == (
        "canonical_market_observations"
    )


def test_transport_rejects_execution_rpc_before_connect():
    rpc = PostgresDigitalTwinRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        DigitalTwinRegistryTransportError,
        match="cannot execute",
    ):
        rpc("execute_digital_twin_scenario", {})
