"""SaaS quota and overage readiness from verified Clone Fleet usage."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from empire_os.digital_avatar_fleet_metering import AvatarFleetMonthlyUsage
from empire_os.saas_freshness import (
    SaasFreshnessQuotaReview,
    review_saas_quota_readiness,
)
from empire_os.saas_usage_billing import (
    SaasUsageBillingReview,
    SaasUsageBillingTerms,
    review_saas_usage_billing,
)


@dataclass(frozen=True)
class AvatarFleetSaasReadiness:
    tenant_id: str
    period: str
    quota_review: SaasFreshnessQuotaReview
    billing_review: SaasUsageBillingReview | None
    verified_usage_units: int
    usage_source: str
    mode: str = "OBSERVE"
    recommendation_only: bool = True
    subscription_mutation: bool = False
    invoice_creation: bool = False
    payment_request_creation: bool = False
    funds_movement: bool = False
    billing_execution: bool = False
    recognized_revenue: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "period": self.period,
            "quota_review": self.quota_review.as_dict(),
            "billing_review": (
                self.billing_review.as_dict()
                if self.billing_review is not None
                else None
            ),
            "verified_usage_units": self.verified_usage_units,
            "usage_source": self.usage_source,
            "mode": self.mode,
            "recommendation_only": self.recommendation_only,
            "subscription_mutation": self.subscription_mutation,
            "invoice_creation": self.invoice_creation,
            "payment_request_creation": self.payment_request_creation,
            "funds_movement": self.funds_movement,
            "billing_execution": self.billing_execution,
            "recognized_revenue": self.recognized_revenue,
            "execution_authority": self.execution_authority,
        }


def review_avatar_fleet_saas_readiness(
    *,
    usage: AvatarFleetMonthlyUsage,
    observed_usage_limit: int | None,
    active_subscription: bool,
    tenant_isolation_verified: bool,
    subscription_observed_at: str,
    isolation_observed_at: str,
    now: datetime,
    max_age_seconds: int = 21600,
    billing_terms: SaasUsageBillingTerms | None = None,
) -> AvatarFleetSaasReadiness:
    if not usage.tenant_id.strip():
        raise ValueError("fleet SaaS usage tenant_id required")
    if usage.observed_monthly_usage < 1:
        raise ValueError("fleet SaaS usage must contain verified units")
    if usage.execution_authority != "none":
        raise ValueError("fleet SaaS usage grants forbidden authority")
    if (
        usage.billing_execution
        or usage.payment_execution
        or usage.revenue_recognition
    ):
        raise ValueError("fleet SaaS usage contains forbidden billing authority")

    quota = review_saas_quota_readiness(
        tenant_id=usage.tenant_id,
        observed_monthly_usage=usage.observed_monthly_usage,
        observed_usage_limit=observed_usage_limit,
        active_subscription=active_subscription,
        tenant_isolation_verified=tenant_isolation_verified,
        usage_observed_at=usage.observed_at,
        subscription_observed_at=subscription_observed_at,
        isolation_observed_at=isolation_observed_at,
        now=now,
        max_age_seconds=max_age_seconds,
    )

    billing = None
    if billing_terms is not None:
        if billing_terms.tenant_id != usage.tenant_id:
            raise ValueError("fleet SaaS billing tenant mismatch")
        billing = review_saas_usage_billing(
            quota_review=quota,
            terms=billing_terms,
        )

    return AvatarFleetSaasReadiness(
        tenant_id=usage.tenant_id,
        period=usage.period,
        quota_review=quota,
        billing_review=billing,
        verified_usage_units=usage.observed_monthly_usage,
        usage_source=usage.source,
    )
