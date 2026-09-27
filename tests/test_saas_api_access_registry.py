from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.saas_api import create_saas_router
from empire_os.saas_api_access_registry import ApiAccessReviewRecord


class FakeApiAccessRegistry:
    def __init__(self):
        self.rows = {}

    def record_api_access_review(self, item: ApiAccessReviewRecord):
        item.validate()
        key = item.review_key
        if key in self.rows:
            return {
                "status": "existing",
                "review_id": self.rows[key]["review_id"],
            }
        row = {
            "review_id": f"api-access-review-{len(self.rows) + 1}",
            "review_key": key,
            "tenant_id": item.freshness.tenant_id,
            "user_id": item.freshness.user_id,
            "eligible": item.freshness.fresh_for_issuance_review,
        }
        self.rows[key] = row
        return {"status": "recorded", **row}

    def list_api_access_reviews(self, *, limit):
        return list(self.rows.values())[:limit]


def client(registry=None):
    app = FastAPI()
    app.include_router(
        create_saas_router(api_access_registry=registry)
    )
    return TestClient(app)


def body(**overrides):
    payload = {
        "review_key": "tenant-1:user-1:read-analytics:v1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "role": "admin",
        "membership_status": "active",
        "active_subscription": True,
        "tenant_isolation_verified": True,
        "requested_scopes": ["read:analytics"],
        "evidence_refs": ["membership:m1", "subscription:s1", "rls:r1"],
        "membership_observed_at": "2026-09-20T11:00:00+00:00",
        "subscription_observed_at": "2026-09-20T10:30:00+00:00",
        "isolation_observed_at": "2026-09-20T10:00:00+00:00",
        "now_utc": "2026-09-20T12:00:00+00:00",
        "max_age_seconds": 10800,
        "evidence": {"source": "canonical_saas_access_evidence"},
    }
    payload.update(overrides)
    return payload


def test_unbound_api_access_registry_fails_closed():
    response = client().post(
        "/v1/saas/api-access/reviews/register",
        json=body(),
    )
    assert response.status_code == 503


def test_fresh_access_review_registers_without_generating_key():
    response = client(FakeApiAccessRegistry()).post(
        "/v1/saas/api-access/reviews/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["mode"] == "OBSERVE"
    assert data["recommendation_only"] is True
    assert data["approval_required"] is True
    assert data["execution_authority"] == "none"
    assert data["api_key_issuance"] is False
    assert data["api_key_revocation"] is False
    assert data["secret_material_generated"] is False
    assert data["subscription_mutation"] is False
    assert data["provisioning_execution"] is False
    assert (
        data["review_record"]["eligible_for_manual_issuance_review"]
        is True
    )


def test_blocked_access_review_can_be_retained_for_audit():
    response = client(FakeApiAccessRegistry()).post(
        "/v1/saas/api-access/reviews/register",
        json=body(requested_scopes=["write:campaigns"]),
    )
    assert response.status_code == 200
    record = response.json()["review_record"]
    assert record["eligible_for_manual_issuance_review"] is False
    assert "unsupported_or_mutating_scope_requested" in (
        record["freshness"]["blockers"]
    )


def test_api_access_registry_is_idempotent_and_history_read_only():
    repo = FakeApiAccessRegistry()
    c = client(repo)
    first = c.post(
        "/v1/saas/api-access/reviews/register",
        json=body(),
    )
    second = c.post(
        "/v1/saas/api-access/reviews/register",
        json=body(),
    )
    history = c.get("/v1/saas/api-access/reviews")
    assert first.status_code == 200
    assert first.json()["status"] == "recorded"
    assert second.json()["status"] == "existing"
    assert history.status_code == 200
    payload = history.json()
    assert payload["read_only"] is True
    assert payload["recommendation_only"] is True
    assert payload["approval_required"] is True
    assert payload["execution_authority"] == "none"
    assert payload["api_key_issuance"] is False
    assert payload["api_key_revocation"] is False
    assert payload["secret_material_generated"] is False
    assert payload["subscription_mutation"] is False
    assert payload["provisioning_execution"] is False
    assert payload["count"] == 1


def test_api_access_registry_requires_provenance():
    response = client(FakeApiAccessRegistry()).post(
        "/v1/saas/api-access/reviews/register",
        json=body(evidence={}),
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]
