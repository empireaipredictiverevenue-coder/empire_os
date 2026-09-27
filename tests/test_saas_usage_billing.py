from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.saas_api import create_saas_router
from empire_os.saas_freshness import review_saas_quota_readiness
from empire_os.saas_usage_billing import (
    SaasUsageBillingTerms,
    review_saas_usage_billing,
)


NOW = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def quota(*, usage=120, limit=100):
    return review_saas_quota_readiness(
        tenant_id="tenant-1",
        observed_monthly_usage=usage,
        observed_usage_limit=limit,
        active_subscription=True,
        tenant_isolation_verified=True,
        usage_observed_at="2026-09-20T15:00:00+00:00",
        subscription_observed_at="2026-09-20T15:00:00+00:00",
        isolation_observed_at="2026-09-20T15:00:00+00:00",
        now=NOW,
    )


def terms(**overrides):
    values = {
        "tenant_id": "tenant-1",
        "commercial_terms_verified": True,
        "commercial_terms_ref": "terms:tenant-1:v1",
        "overage_price_usdt_micros_per_unit": 250000,
        "pricing_evidence_ref": "pricing:tenant-1:v1",
    }
    values.update(overrides)
    return SaasUsageBillingTerms(**values)


def test_over_limit_usage_can_be_reviewed_for_usdt_overage_without_billing():
    review = review_saas_usage_billing(
        quota_review=quota(),
        terms=terms(),
    )
    assert review.charge_preview_ready is True
    assert review.billable_overage_units == 20
    assert review.computed_charge_usdt_micros == 5000000
    assert review.invoice_creation is False
    assert review.payment_request_creation is False
    assert review.funds_movement is False
    assert review.billing_execution is False
    assert review.recognized_revenue is False


def test_usage_within_allowance_has_zero_preview_charge_not_revenue():
    review = review_saas_usage_billing(
        quota_review=quota(usage=80, limit=100),
        terms=terms(),
    )
    assert review.charge_preview_ready is True
    assert review.billable_overage_units == 0
    assert review.computed_charge_usdt_micros == 0
    assert review.recognized_revenue is False


def test_unverified_terms_keep_charge_unknown_for_execution():
    review = review_saas_usage_billing(
        quota_review=quota(),
        terms=terms(
            commercial_terms_verified=False,
            commercial_terms_ref=None,
        ),
    )
    assert review.charge_preview_ready is False
    assert "verified_commercial_terms_required" in review.blockers
    assert review.billing_execution is False


def test_stale_usage_evidence_blocks_charge_preview():
    stale = review_saas_quota_readiness(
        tenant_id="tenant-1",
        observed_monthly_usage=120,
        observed_usage_limit=100,
        active_subscription=True,
        tenant_isolation_verified=True,
        usage_observed_at="2026-09-10T15:00:00+00:00",
        subscription_observed_at="2026-09-20T15:00:00+00:00",
        isolation_observed_at="2026-09-20T15:00:00+00:00",
        now=NOW,
    )
    review = review_saas_usage_billing(
        quota_review=stale,
        terms=terms(),
    )
    assert review.charge_preview_ready is False
    assert "usage_evidence_stale" in review.blockers


def test_api_usage_billing_preview_never_requests_payment():
    app = FastAPI()
    app.include_router(create_saas_router())
    response = TestClient(app).post(
        "/v1/saas/usage-billing/preview",
        json={
            "tenant_id": "tenant-1",
            "observed_monthly_usage": 120,
            "observed_usage_limit": 100,
            "active_subscription": True,
            "tenant_isolation_verified": True,
            "usage_observed_at": "2026-09-20T15:00:00+00:00",
            "subscription_observed_at": "2026-09-20T15:00:00+00:00",
            "isolation_observed_at": "2026-09-20T15:00:00+00:00",
            "now_utc": "2026-09-20T16:00:00+00:00",
            "commercial_terms_verified": True,
            "commercial_terms_ref": "terms:tenant-1:v1",
            "overage_price_usdt_micros_per_unit": 250000,
            "pricing_evidence_ref": "pricing:tenant-1:v1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["invoice_creation"] is False
    assert body["payment_request_creation"] is False
    assert body["funds_movement"] is False
    assert body["billing_execution"] is False
    assert body["subscription_mutation"] is False
    assert body["recognized_revenue"] is False
    assert body["review"]["charge_preview_ready"] is True
