from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.enterprise_api import create_enterprise_router


class FakeRepository:
    def controls(self, *, limit):
        return [{
            "control_key": "tenant_row_isolation",
            "family": "data_isolation",
            "tenant_key": "tenant-1",
            "status": "pass",
            "evidence_refs": ["rls:test"],
            "observed_at": "2026-09-19T23:55:00+00:00",
            "source": "control_probe",
        }][:limit]

    def slos(self, *, limit):
        return [{
            "service_key": "public-gateway",
            "metric": "availability",
            "target": 0.99,
            "observed": 0.995,
            "window": "30d",
            "observed_at": "2026-09-19T23:55:00+00:00",
            "source": "slo_probe",
        }][:limit]


def client(repository=None):
    app = FastAPI()
    app.include_router(create_enterprise_router(repository))
    return TestClient(app)


def test_health_is_observe_only():
    response = client().get("/v1/enterprise/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["repository_available"] is False


def test_readiness_uses_observed_controls_and_slos():
    response = client(FakeRepository()).get(
        "/v1/enterprise/readiness?limit=10"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    readiness = body["readiness"]
    assert readiness["ready_for_enterprise_review"] is True
    assert readiness["control_passes"] == 1
    assert readiness["slo_passes"] == 1


def test_missing_repository_fails_closed():
    response = client().get("/v1/enterprise/readiness")
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "enterprise_evidence_repository_not_activated"
    )


def test_unknown_control_blocks_readiness():
    class UnknownRepository(FakeRepository):
        def controls(self, *, limit):
            rows = list(super().controls(limit=limit))
            rows[0]["status"] = "unknown"
            return rows

    response = client(UnknownRepository()).get(
        "/v1/enterprise/readiness"
    )
    assert response.status_code == 200
    readiness = response.json()["readiness"]
    assert readiness["ready_for_enterprise_review"] is False
    assert "control_unknowns_present" in readiness["blockers"]
