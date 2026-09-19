from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.demand_api import create_demand_router
from empire_os.demand_registry import DemandRegistryRecord
from empire_os.demand_registry_transport import (
    DemandRegistryTransportError,
    PostgresDemandRegistryRpc,
    RpcDemandRegistryRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record(self, item: DemandRegistryRecord):
        item.validate()
        if item.plan.plan_id in self.rows:
            return {
                "status": "existing",
                "registry_id": self.rows[item.plan.plan_id]["registry_id"],
            }
        row = {
            "registry_id": f"registry-{len(self.rows) + 1}",
            "plan_id": item.plan.plan_id,
            "channel": item.plan.channel,
        }
        self.rows[item.plan.plan_id] = row
        return {"status": "recorded", **row}

    def list_plans(self, *, limit):
        return list(self.rows.values())[:limit]


def client(repo=None):
    app = FastAPI()
    app.include_router(create_demand_router(repo))
    return TestClient(app)


def body():
    return {
        "plan_id": "plan-1",
        "channel": "aeo",
        "objective": "Increase qualified roofing discovery",
        "audience": "UK roofing contractors",
        "evidence_refs": ["search-gap:1", "crm:2", "ads:3"],
        "success_metric": "qualified_inbound_conversations",
        "observed_demand_signals": 10,
        "verified_audience_size": 2000,
        "qualified_inbound_events": 8,
        "historical_conversion_rate": 0.15,
        "observed_cost_cents": 5000,
        "evidence": {"source": "canonical_demand_observations"},
    }


def test_unbound_registry_fails_closed():
    response = client().post("/v1/demand/plans/register", json=body())
    assert response.status_code == 503


def test_review_ready_plan_registers_without_execution():
    response = client(FakeRegistry()).post(
        "/v1/demand/plans/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["execution_authority"] == "none"
    assert data["publishing_enabled"] is False
    assert data["outbound_enabled"] is False
    assert data["ad_spend_enabled"] is False
    assert data["provider_activation_enabled"] is False


def test_not_ready_plan_is_not_persisted():
    repo = FakeRegistry()
    payload = body()
    payload["observed_demand_signals"] = 0
    response = client(repo).post(
        "/v1/demand/plans/register",
        json=payload,
    )
    assert response.status_code == 422
    assert "only review-ready" in response.json()["detail"]
    assert repo.rows == {}


def test_registry_is_idempotent_and_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/demand/plans/register", json=body())
    second = c.post("/v1/demand/plans/register", json=body())
    listing = c.get("/v1/demand/plans")
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
        "/v1/demand/plans/register",
        json=payload,
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]


def test_rpc_repository_maps_readiness_and_evidence():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "registry_id": "r1"}

    repo = RpcDemandRegistryRepository(rpc)
    app = FastAPI()

    class Wrapper:
        def record(self, item):
            return repo.record(item)

        def list_plans(self, *, limit):
            return []

    app.include_router(create_demand_router(Wrapper()))
    response = TestClient(app).post(
        "/v1/demand/plans/register",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_evidence_score"] >= 0.5
    assert params["p_readiness_reason"] == (
        "evidence_sufficient_for_operator_review"
    )
    assert params["p_evidence"]["source"] == (
        "canonical_demand_observations"
    )


def test_transport_rejects_publish_rpc_before_connect():
    rpc = PostgresDemandRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        DemandRegistryTransportError,
        match="cannot execute",
    ):
        rpc("publish_demand_plan", {})
