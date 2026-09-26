from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.saas_api import create_saas_router


class FakeTenantRepository:
    tenant_id = "tenant-1"

    def memberships(self, *, limit):
        return [{
            "user_key": "user-1",
            "role": "viewer",
            "status": "active",
        }][:limit]

    def usage(self, *, limit):
        return [{
            "metric": "predictions",
            "value": 42,
            "period": "2026-09",
            "source": "canonical_usage_meter",
        }][:limit]

    def subscriptions(self, *, limit):
        return [{
            "plan_key": "pro",
            "status": "active",
            "billing_provider": "external",
            "observed_at": "2026-09-19T18:15:00+00:00",
            "source": "subscription_state_reader",
        }][:limit]


def client(repository=None):
    app = FastAPI()
    app.include_router(create_saas_router(repository))
    return TestClient(app)


def test_health_is_observe_only_and_tenant_scoped():
    response = client().get("/v1/saas/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["tenant_scoped"] is True
    assert body["repository_available"] is False


def test_usage_read_is_scoped_to_repository_tenant():
    response = client(FakeTenantRepository()).get(
        "/v1/saas/usage?limit=10"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant-1"
    assert body["count"] == 1
    assert body["items"][0]["metric"] == "predictions"


def test_subscription_read_never_enables_billing():
    response = client(FakeTenantRepository()).get(
        "/v1/saas/subscriptions"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["billing_execution"] is False
    assert body["execution_authority"] == "none"


def test_missing_repository_fails_closed():
    response = client().get("/v1/saas/memberships")
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "saas_tenant_repository_not_activated"
    )


def test_missing_tenant_scope_fails_closed():
    class UnscopedRepository(FakeTenantRepository):
        tenant_id = ""

    response = client(UnscopedRepository()).get("/v1/saas/usage")
    assert response.status_code == 503
    assert response.json()["detail"] == "saas_tenant_scope_missing"
