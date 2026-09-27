from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.saas_api import create_saas_router
from empire_os.saas_registry import SaasReadinessRecord
from empire_os.saas_registry_transport import (
    PostgresSaasRegistryRpc,
    RpcSaasRegistryRepository,
    SaasRegistryTransportError,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record(self, item: SaasReadinessRecord):
        item.validate()
        if item.readiness_key in self.rows:
            return {
                "status": "existing",
                "registry_id": self.rows[item.readiness_key]["registry_id"],
            }
        row = {
            "registry_id": f"registry-{len(self.rows) + 1}",
            "readiness_key": item.readiness_key,
            "tenant_id": item.snapshot.tenant_id,
        }
        self.rows[item.readiness_key] = row
        return {"status": "recorded", **row}

    def list_readiness(self, *, limit):
        return list(self.rows.values())[:limit]


def client(registry=None):
    app = FastAPI()
    app.include_router(create_saas_router(registry=registry))
    return TestClient(app)


def body():
    return {
        "readiness_key": "tenant-1-2026-09-v1",
        "tenant_id": "tenant-1",
        "active_members": 5,
        "observed_monthly_usage": 400,
        "observed_usage_limit": 1000,
        "active_subscription": True,
        "tenant_isolation_verified": True,
        "white_label_requested": False,
        "white_label_configured": False,
        "evidence_refs": ["usage:u1", "subscription:s1", "isolation:i1"],
        "evidence": {"source": "canonical_tenant_observations"},
    }


def test_unbound_registry_fails_closed():
    response = client().post(
        "/v1/saas/scale-readiness/register",
        json=body(),
    )
    assert response.status_code == 503


def test_review_ready_tenant_registers_without_provisioning():
    response = client(FakeRegistry()).post(
        "/v1/saas/scale-readiness/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["execution_authority"] == "none"
    assert data["provisioning_execution"] is False
    assert data["billing_execution"] is False
    assert data["api_key_issuance"] is False
    assert data["subscription_mutation"] is False


def test_missing_scale_evidence_is_not_registered():
    repo = FakeRegistry()
    payload = body()
    payload["active_subscription"] = False
    response = client(repo).post(
        "/v1/saas/scale-readiness/register",
        json=payload,
    )
    assert response.status_code == 422
    assert "only review-ready" in response.json()["detail"]
    assert repo.rows == {}


def test_registry_is_idempotent_and_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/saas/scale-readiness/register", json=body())
    second = c.post("/v1/saas/scale-readiness/register", json=body())
    listing = c.get("/v1/saas/scale-readiness")
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
        "/v1/saas/scale-readiness/register",
        json=payload,
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]


def test_rpc_repository_maps_tenant_readiness():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "registry_id": "r1"}

    repo = RpcSaasRegistryRepository(rpc)
    app = FastAPI()

    class Wrapper:
        def record(self, item):
            return repo.record(item)

        def list_readiness(self, *, limit):
            return []

    app.include_router(create_saas_router(registry=Wrapper()))
    response = TestClient(app).post(
        "/v1/saas/scale-readiness/register",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_tenant_id"] == "tenant-1"
    assert params["p_active_subscription"] is True
    assert params["p_tenant_isolation_verified"] is True


def test_transport_rejects_provisioning_rpc_before_connect():
    rpc = PostgresSaasRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        SaasRegistryTransportError,
        match="cannot execute",
    ):
        rpc("provision_tenant", {})
