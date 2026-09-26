from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.revenue_os_api import create_revenue_os_router
from empire_os.revenue_os_registry import RevenueOsRegistryRecord
from empire_os.revenue_os_registry_transport import (
    PostgresRevenueOsRegistryRpc,
    RevenueOsRegistryTransportError,
    RpcRevenueOsRegistryRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record(self, item: RevenueOsRegistryRecord):
        item.validate()
        key = item.packet.packet_key
        if key in self.rows:
            return {
                "status": "existing",
                "packet_id": self.rows[key]["packet_id"],
            }
        row = {
            "packet_id": f"packet-{len(self.rows) + 1}",
            "packet_key": key,
        }
        self.rows[key] = row
        return {"status": "recorded", **row}


def client(registry=None):
    app = FastAPI()
    app.include_router(create_revenue_os_router(registry=registry))
    return TestClient(app)


def body():
    return {
        "packet_key": "packet-1",
        "astra_decision": {
            "workstream": "buyer_allocation",
            "recommended_job_type": "plan_controlled_allocation",
        },
        "predictive_forecast": {"direction": "up"},
        "capital_recommendation": {"candidate_id": "candidate-1"},
        "demand_plan_ref": "demand-1",
        "enterprise_blockers": [],
        "evidence_refs": ["astra:1", "forecast:1", "capital:1"],
        "evidence": {"source": "canonical_phase18_inputs"},
    }


def test_unbound_registry_fails_closed():
    response = client().post("/v1/revenue-os/packets/register", json=body())
    assert response.status_code == 503


def test_complete_packet_registers_without_execution():
    response = client(FakeRegistry()).post(
        "/v1/revenue-os/packets/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["mode"] == "OBSERVE"
    assert data["side_effects"] == "none"
    assert data["execution_authority"] == "none"
    assert data["spend_execution"] is False
    assert data["outreach_execution"] is False
    assert data["payment_execution"] is False
    assert data["allocation_execution"] is False
    assert data["deployment_execution"] is False
    assert (
        data["registry_record"]["readiness"]["ready_for_operator_review"]
        is True
    )


def test_incomplete_packet_can_be_recorded_with_blockers():
    payload = body()
    payload["predictive_forecast"] = None
    response = client(FakeRegistry()).post(
        "/v1/revenue-os/packets/register",
        json=payload,
    )
    assert response.status_code == 200
    readiness = response.json()["registry_record"]["readiness"]
    assert readiness["ready_for_operator_review"] is False
    assert "forecast_direction_missing" in readiness["blockers"]


def test_registry_is_idempotent():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/revenue-os/packets/register", json=body())
    second = c.post("/v1/revenue-os/packets/register", json=body())
    assert first.status_code == 200
    assert second.json()["status"] == "existing"


def test_registry_requires_evidence():
    payload = body()
    payload["evidence"] = {}
    response = client(FakeRegistry()).post(
        "/v1/revenue-os/packets/register",
        json=payload,
    )
    assert response.status_code == 422


def test_rpc_repository_maps_packet_and_readiness():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "packet_id": "p1"}

    repo = RpcRevenueOsRegistryRepository(rpc)
    app = FastAPI()

    class Wrapper:
        def record(self, item):
            return repo.record(item)

    app.include_router(create_revenue_os_router(registry=Wrapper()))
    response = TestClient(app).post(
        "/v1/revenue-os/packets/register",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_recommended_workstream"] == "buyer_allocation"
    assert params["p_ready_for_operator_review"] is True
    assert params["p_evidence"]["source"] == "canonical_phase18_inputs"


def test_transport_rejects_execution_rpc_before_connect():
    rpc = PostgresRevenueOsRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        RevenueOsRegistryTransportError,
        match="cannot execute",
    ):
        rpc("execute_revenue_packet", {})
