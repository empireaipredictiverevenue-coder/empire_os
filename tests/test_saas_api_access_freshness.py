from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.saas_api import create_saas_router
from empire_os.saas_api_access import (
    ApiAccessEvidence,
    assess_api_access_readiness,
)
from empire_os.saas_api_access_freshness import assess_api_access_freshness
from empire_os.saas_scale import TenantMembership


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def readiness(**overrides):
    values = {
        "membership": TenantMembership(
            tenant_id="tenant-1",
            user_id="user-1",
            role="admin",
            status="active",
        ),
        "active_subscription": True,
        "tenant_isolation_verified": True,
        "requested_scopes": ("read:analytics",),
        "evidence_refs": ("membership:m1", "subscription:s1", "rls:r1"),
    }
    values.update(overrides)
    return assess_api_access_readiness(ApiAccessEvidence(**values))


def test_fresh_access_evidence_is_review_ready_only():
    result = assess_api_access_freshness(
        readiness=readiness(),
        membership_observed_at="2026-09-20T11:00:00+00:00",
        subscription_observed_at="2026-09-20T10:30:00+00:00",
        isolation_observed_at="2026-09-20T10:00:00+00:00",
        now=NOW,
        max_age_seconds=10800,
    )
    assert result.fresh_for_issuance_review is True
    assert result.blockers == ()
    assert result.execution_authority == "none"
    assert result.api_key_issuance is False
    assert result.secret_material_generated is False


def test_stale_subscription_blocks_issuance_review():
    result = assess_api_access_freshness(
        readiness=readiness(),
        membership_observed_at="2026-09-20T11:00:00+00:00",
        subscription_observed_at="2026-09-20T07:00:00+00:00",
        isolation_observed_at="2026-09-20T10:00:00+00:00",
        now=NOW,
        max_age_seconds=10800,
    )
    assert result.fresh_for_issuance_review is False
    assert "subscription_evidence_stale" in result.blockers


def test_future_isolation_evidence_blocks_review():
    result = assess_api_access_freshness(
        readiness=readiness(),
        membership_observed_at="2026-09-20T11:00:00+00:00",
        subscription_observed_at="2026-09-20T10:30:00+00:00",
        isolation_observed_at="2026-09-20T12:05:00+00:00",
        now=NOW,
        max_age_seconds=10800,
    )
    assert result.fresh_for_issuance_review is False
    assert "isolation_evidence_from_future" in result.blockers


def test_existing_scope_blockers_survive_freshness_review():
    blocked = readiness(requested_scopes=("write:campaigns",))
    result = assess_api_access_freshness(
        readiness=blocked,
        membership_observed_at="2026-09-20T11:00:00+00:00",
        subscription_observed_at="2026-09-20T10:30:00+00:00",
        isolation_observed_at="2026-09-20T10:00:00+00:00",
        now=NOW,
    )
    assert result.fresh_for_issuance_review is False
    assert "unsupported_or_mutating_scope_requested" in result.blockers


def test_api_preview_never_generates_key_material():
    app = FastAPI()
    app.include_router(create_saas_router())
    response = TestClient(app).post(
        "/v1/saas/api-access/freshness/preview",
        json={
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "role": "admin",
            "membership_status": "active",
            "active_subscription": True,
            "tenant_isolation_verified": True,
            "requested_scopes": ["read:analytics"],
            "evidence_refs": [
                "membership:m1",
                "subscription:s1",
                "rls:r1",
            ],
            "membership_observed_at": "2026-09-20T11:00:00+00:00",
            "subscription_observed_at": "2026-09-20T10:30:00+00:00",
            "isolation_observed_at": "2026-09-20T10:00:00+00:00",
            "now_utc": "2026-09-20T12:00:00+00:00",
            "max_age_seconds": 10800,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["recommendation_only"] is True
    assert body["execution_authority"] == "none"
    assert body["api_key_issuance"] is False
    assert body["api_key_revocation"] is False
    assert body["secret_material_generated"] is False
    assert body["subscription_mutation"] is False
    assert body["freshness"]["fresh_for_issuance_review"] is True
