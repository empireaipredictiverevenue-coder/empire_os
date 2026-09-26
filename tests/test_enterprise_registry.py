from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.enterprise_api import create_enterprise_router
from empire_os.enterprise_registry import EnterpriseReadinessRecord
from empire_os.enterprise_registry_transport import (
    EnterpriseRegistryTransportError,
    PostgresEnterpriseRegistryRpc,
    RpcEnterpriseRegistryRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record(self, item: EnterpriseReadinessRecord):
        item.validate()
        if item.readiness_key in self.rows:
            return {
                "status": "existing",
                "registry_id": self.rows[item.readiness_key]["registry_id"],
            }
        row = {
            "registry_id": f"registry-{len(self.rows) + 1}",
            "readiness_key": item.readiness_key,
        }
        self.rows[item.readiness_key] = row
        return {"status": "recorded", **row}

    def list_readiness(self, *, limit):
        return list(self.rows.values())[:limit]


def client(registry=None):
    app = FastAPI()
    app.include_router(create_enterprise_router(registry=registry))
    return TestClient(app)


def body():
    return {
        "readiness_key": "enterprise-2026-09-v1",
        "controls": [{
            "control_key": "tenant_row_isolation",
            "family": "data_isolation",
            "tenant_key": "tenant-1",
            "status": "pass",
            "evidence_refs": ["rls:test"],
            "observed_at": "2026-09-19T23:55:00+00:00",
            "source": "control_probe",
        }],
        "slos": [{
            "service_key": "public-gateway",
            "metric": "availability",
            "target": 0.99,
            "observed": 0.995,
            "window": "30d",
            "observed_at": "2026-09-19T23:55:00+00:00",
            "source": "slo_probe",
        }],
        "evidence": {"source": "canonical_enterprise_observations"},
    }


def test_unbound_registry_fails_closed():
    response = client().post("/v1/enterprise/readiness/register", json=body())
    assert response.status_code == 503


def test_readiness_registers_without_control_mutation():
    response = client(FakeRegistry()).post(
        "/v1/enterprise/readiness/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["execution_authority"] == "none"
    assert data["control_mutation"] is False
    assert data["infrastructure_mutation"] is False
    assert data["identity_mutation"] is False


def test_registry_is_idempotent_and_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/enterprise/readiness/register", json=body())
    second = c.post("/v1/enterprise/readiness/register", json=body())
    listing = c.get("/v1/enterprise/readiness/history")
    assert first.status_code == 200
    assert second.json()["status"] == "existing"
    assert listing.status_code == 200
    assert listing.json()["read_only"] is True
    assert listing.json()["count"] == 1


def test_registry_requires_evidence():
    payload = body()
    payload["evidence"] = {}
    response = client(FakeRegistry()).post(
        "/v1/enterprise/readiness/register",
        json=payload,
    )
    assert response.status_code == 422


def test_failed_control_is_preserved_as_blocker():
    payload = body()
    payload["controls"][0]["status"] = "fail"
    response = client(FakeRegistry()).post(
        "/v1/enterprise/readiness/register",
        json=payload,
    )
    assert response.status_code == 200
    review = response.json()["readiness_record"]["review"]
    assert review["ready_for_enterprise_review"] is False
    assert "control_failures_present" in review["blockers"]


def test_rpc_repository_maps_observed_evidence():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "registry_id": "r1"}

    repo = RpcEnterpriseRegistryRepository(rpc)
    app = FastAPI()

    class Wrapper:
        def record(self, item):
            return repo.record(item)
        def list_readiness(self, *, limit):
            return []

    app.include_router(create_enterprise_router(registry=Wrapper()))
    response = TestClient(app).post(
        "/v1/enterprise/readiness/register",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_control_passes"] == 1
    assert params["p_slo_passes"] == 1
    assert params["p_evidence"]["source"] == "canonical_enterprise_observations"


def test_transport_rejects_control_mutation_rpc_before_connect():
    rpc = PostgresEnterpriseRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        EnterpriseRegistryTransportError,
        match="cannot execute",
    ):
        rpc("mutate_enterprise_control", {})
