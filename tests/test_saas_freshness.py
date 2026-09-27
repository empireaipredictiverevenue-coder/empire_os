from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.saas_api import create_saas_router
from empire_os.saas_freshness import review_saas_quota_readiness


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def review(**overrides):
    values = {
        "tenant_id": "tenant-1",
        "observed_monthly_usage": 800,
        "observed_usage_limit": 1000,
        "active_subscription": True,
        "tenant_isolation_verified": True,
        "usage_observed_at": "2026-09-20T11:00:00+00:00",
        "subscription_observed_at": "2026-09-20T10:30:00+00:00",
        "isolation_observed_at": "2026-09-20T10:00:00+00:00",
        "now": NOW,
        "max_age_seconds": 10800,
    }
    values.update(overrides)
    return review_saas_quota_readiness(**values)


def test_fresh_verified_evidence_exposes_quota_headroom_only():
    result = review()
    assert result.quota.quota_review_ready is True
    assert result.quota.utilization_ratio == 0.8
    assert result.quota.remaining_units == 200
    assert result.quota.quota_state == "available"
    assert result.quota.blockers == ()
    assert result.quota.execution_authority == "none"
    assert result.quota.billing_execution is False
    assert result.quota.provisioning_execution is False
    assert result.quota.subscription_mutation is False
    assert result.quota.api_key_issuance is False


def test_stale_subscription_evidence_blocks_quota_review():
    result = review(
        subscription_observed_at="2026-09-20T07:00:00+00:00",
    )
    assert result.quota.quota_review_ready is False
    assert "subscription_evidence_stale" in result.quota.blockers


def test_inactive_subscription_and_unverified_isolation_block_review():
    result = review(
        active_subscription=False,
        tenant_isolation_verified=False,
    )
    assert result.quota.quota_review_ready is False
    assert "active_subscription_required" in result.quota.blockers
    assert "tenant_isolation_not_verified" in result.quota.blockers


def test_missing_usage_limit_stays_unknown():
    result = review(observed_usage_limit=None)
    assert result.quota.quota_review_ready is False
    assert result.quota.utilization_ratio is None
    assert result.quota.remaining_units is None
    assert result.quota.quota_state == "unknown"
    assert "observed_usage_limit_missing" in result.quota.blockers


def test_over_limit_is_observed_not_mutated():
    result = review(
        observed_monthly_usage=1200,
        observed_usage_limit=1000,
    )
    assert result.quota.quota_review_ready is False
    assert result.quota.utilization_ratio == 1.2
    assert result.quota.remaining_units == 0
    assert result.quota.quota_state == "over_limit"
    assert "observed_usage_over_limit" in result.quota.blockers
    assert result.quota.billing_execution is False


def test_future_usage_evidence_blocks_review():
    result = review(
        usage_observed_at="2026-09-20T12:05:00+00:00",
    )
    assert result.quota.quota_review_ready is False
    assert "usage_evidence_future" in result.quota.blockers


def test_api_preview_is_observe_only():
    app = FastAPI()
    app.include_router(create_saas_router())
    response = TestClient(app).post(
        "/v1/saas/quota-readiness/preview",
        json={
            "tenant_id": "tenant-1",
            "observed_monthly_usage": 800,
            "observed_usage_limit": 1000,
            "active_subscription": True,
            "tenant_isolation_verified": True,
            "usage_observed_at": "2026-09-20T11:00:00+00:00",
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
    assert body["provisioning_execution"] is False
    assert body["billing_execution"] is False
    assert body["subscription_mutation"] is False
    assert body["api_key_issuance"] is False
    assert body["review"]["quota"]["quota_review_ready"] is True


def test_api_rejects_naive_now_timestamp():
    app = FastAPI()
    app.include_router(create_saas_router())
    response = TestClient(app).post(
        "/v1/saas/quota-readiness/preview",
        json={
            "tenant_id": "tenant-1",
            "observed_monthly_usage": 800,
            "observed_usage_limit": 1000,
            "active_subscription": True,
            "tenant_isolation_verified": True,
            "usage_observed_at": "2026-09-20T11:00:00+00:00",
            "subscription_observed_at": "2026-09-20T10:30:00+00:00",
            "isolation_observed_at": "2026-09-20T10:00:00+00:00",
            "now_utc": "2026-09-20T12:00:00",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "now_utc must include timezone"
