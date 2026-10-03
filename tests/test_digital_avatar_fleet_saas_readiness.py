from datetime import datetime, timezone

import pytest

from empire_os.digital_avatar_fleet_metering import AvatarFleetMonthlyUsage
from empire_os.digital_avatar_fleet_saas_readiness import (
    review_avatar_fleet_saas_readiness,
)
from empire_os.saas_usage_billing import SaasUsageBillingTerms


NOW = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)


def usage(units=3, **overrides):
    values = {
        "tenant_id": "tenant-a",
        "period": "2026-10",
        "observed_monthly_usage": units,
        "usage_keys": tuple(f"usage-{i}" for i in range(units)),
        "evidence_refs": ("recall-verification:1",),
        "observed_at": "2026-10-03T12:30:00+00:00",
        "source": "digital_avatar_verified_lifecycle:abc",
    }
    values.update(overrides)
    return AvatarFleetMonthlyUsage(**values)


def terms(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "commercial_terms_verified": True,
        "commercial_terms_ref": "commercial_terms_review:verified",
        "overage_price_usdt_micros_per_unit": 1_500_000,
        "pricing_evidence_ref": "pricing:verified:v1",
    }
    values.update(overrides)
    return SaasUsageBillingTerms(**values)


def review(units=3, limit=10, **overrides):
    values = {
        "usage": usage(units),
        "observed_usage_limit": limit,
        "active_subscription": True,
        "tenant_isolation_verified": True,
        "subscription_observed_at": "2026-10-03T12:30:00+00:00",
        "isolation_observed_at": "2026-10-03T12:30:00+00:00",
        "now": NOW,
    }
    values.update(overrides)
    return review_avatar_fleet_saas_readiness(**values)


def test_fresh_in_limit_verified_usage_is_quota_ready():
    result = review(units=3, limit=10)
    quota = result.quota_review.quota
    assert quota.quota_review_ready is True
    assert quota.quota_state == "available"
    assert quota.remaining_units == 7
    assert result.billing_review is None
    assert result.recommendation_only is True
    assert result.execution_authority == "none"


def test_exact_limit_is_exhausted_without_mutation():
    result = review(units=10, limit=10)
    quota = result.quota_review.quota
    assert quota.quota_review_ready is True
    assert quota.quota_state == "exhausted"
    assert quota.remaining_units == 0
    assert result.subscription_mutation is False


def test_over_limit_usage_can_be_reviewed_as_overage_only_with_verified_terms():
    result = review(
        units=12,
        limit=10,
        billing_terms=terms(),
    )
    quota = result.quota_review.quota
    billing = result.billing_review
    assert quota.quota_state == "over_limit"
    assert "observed_usage_over_limit" in quota.blockers
    assert billing is not None
    assert billing.charge_preview_ready is True
    assert billing.billable_overage_units == 2
    assert billing.computed_charge_usdt_micros == 3_000_000
    assert billing.invoice_creation is False
    assert billing.payment_request_creation is False
    assert billing.funds_movement is False
    assert billing.billing_execution is False
    assert billing.recognized_revenue is False


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    [
        (
            "subscription_observed_at",
            "2026-10-01T00:00:00+00:00",
            "subscription_evidence_stale",
        ),
        (
            "isolation_observed_at",
            "2026-10-01T00:00:00+00:00",
            "isolation_evidence_stale",
        ),
    ],
)
def test_stale_subscription_or_isolation_blocks_quota(field, value, blocker):
    result = review(**{field: value})
    assert result.quota_review.quota.quota_review_ready is False
    assert blocker in result.quota_review.quota.blockers


def test_stale_usage_blocks_quota():
    result = review(
        usage=usage(observed_at="2026-10-01T00:00:00+00:00"),
    )
    assert result.quota_review.quota.quota_review_ready is False
    assert "usage_evidence_stale" in result.quota_review.quota.blockers


def test_inactive_subscription_and_unverified_isolation_block():
    result = review(
        active_subscription=False,
        tenant_isolation_verified=False,
    )
    blockers = result.quota_review.quota.blockers
    assert "active_subscription_required" in blockers
    assert "tenant_isolation_not_verified" in blockers


def test_missing_usage_limit_blocks_readiness():
    result = review(observed_usage_limit=None)
    assert result.quota_review.quota.quota_review_ready is False
    assert "observed_usage_limit_missing" in result.quota_review.quota.blockers


def test_billing_tenant_mismatch_fails_closed():
    with pytest.raises(ValueError, match="billing tenant mismatch"):
        review(
            units=12,
            limit=10,
            billing_terms=terms(tenant_id="tenant-b"),
        )


def test_missing_verified_terms_or_price_evidence_blocks_charge_preview():
    unverified = review(
        units=12,
        limit=10,
        billing_terms=terms(
            commercial_terms_verified=False,
            commercial_terms_ref=None,
        ),
    )
    assert unverified.billing_review.charge_preview_ready is False
    assert "verified_commercial_terms_required" in (
        unverified.billing_review.blockers
    )

    no_price = review(
        units=12,
        limit=10,
        billing_terms=terms(
            overage_price_usdt_micros_per_unit=None,
            pricing_evidence_ref=None,
        ),
    )
    assert no_price.billing_review.charge_preview_ready is False
    assert "verified_overage_pricing_evidence_missing" in (
        no_price.billing_review.blockers
    )


def test_readiness_never_creates_invoice_payment_or_revenue():
    result = review(
        units=12,
        limit=10,
        billing_terms=terms(),
    )
    assert result.invoice_creation is False
    assert result.payment_request_creation is False
    assert result.funds_movement is False
    assert result.billing_execution is False
    assert result.recognized_revenue is False
    assert result.execution_authority == "none"
