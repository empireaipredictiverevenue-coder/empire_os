from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.experiment_api import create_experiment_router
from empire_os.experiment_registry import ExperimentRegistryRecord
from empire_os.experiment_registry_transport import (
    ExperimentRegistryTransportError,
    PostgresExperimentRegistryRpc,
    RpcExperimentRegistryRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record(self, item: ExperimentRegistryRecord):
        item.validate()
        if item.experiment_key in self.rows:
            return {
                "status": "existing",
                "registry_id": self.rows[item.experiment_key]["registry_id"],
            }
        row = {
            "registry_id": f"registry-{len(self.rows) + 1}",
            "experiment_key": item.experiment_key,
            "metric": item.metric,
        }
        self.rows[item.experiment_key] = row
        return {"status": "recorded", **row}

    def list_experiments(self, *, limit):
        return list(self.rows.values())[:limit]


def client(repo=None):
    app = FastAPI()
    app.include_router(create_experiment_router(repo))
    return TestClient(app)


def body():
    return {
        "experiment_key": "pricing-copy-v1",
        "hypothesis": "New copy increases observed conversion",
        "metric": "conversion_rate",
        "control_variant": "control",
        "treatment_variants": ["variant-a"],
        "assignment_integrity_verified": True,
        "exposure_integrity_verified": True,
        "outcome_window_closed": False,
        "evidence": {"source": "canonical_experiment_observations"},
    }


def test_unbound_registry_fails_closed():
    response = client().post("/v1/experiments/registry", json=body())
    assert response.status_code == 503


def test_registry_records_without_execution_authority():
    response = client(FakeRegistry()).post(
        "/v1/experiments/registry",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["execution_authority"] == "none"
    assert data["traffic_mutation"] is False
    assert data["rollout_enabled"] is False
    assert data["pricing_mutation"] is False


def test_registry_is_idempotent_and_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/experiments/registry", json=body())
    second = c.post("/v1/experiments/registry", json=body())
    listing = c.get("/v1/experiments/registry")
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
        "/v1/experiments/registry",
        json=payload,
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]


def test_registry_rejects_control_as_treatment():
    payload = body()
    payload["treatment_variants"] = ["control"]
    response = client(FakeRegistry()).post(
        "/v1/experiments/registry",
        json=payload,
    )
    assert response.status_code == 422


def test_rpc_repository_maps_integrity_and_evidence():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "registry_id": "r1"}

    repo = RpcExperimentRegistryRepository(rpc)
    item = ExperimentRegistryRecord(
        experiment_key="exp-1",
        hypothesis="Observed lift",
        metric="revenue_per_subject",
        control_variant="control",
        treatment_variants=("treatment",),
        assignment_integrity_verified=True,
        exposure_integrity_verified=False,
        outcome_window_closed=False,
        evidence={"assignment": "verified"},
    )
    result = repo.record(item)
    assert result["status"] == "recorded"
    params = calls[0][1]
    assert params["p_assignment_integrity_verified"] is True
    assert params["p_exposure_integrity_verified"] is False
    assert params["p_evidence"]["assignment"] == "verified"


def test_transport_rejects_rollout_rpc_before_connect():
    rpc = PostgresExperimentRegistryRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        ExperimentRegistryTransportError,
        match="cannot execute",
    ):
        rpc("rollout_experiment_winner", {})
