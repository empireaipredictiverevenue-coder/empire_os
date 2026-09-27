"""Phase 16 evidence-only USDT usage billing preview."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.saas_freshness import SaasFreshnessQuotaReview


@dataclass(frozen=True)
class SaasUsageBillingTerms:
    tenant_id: str
    commercial_terms_verified: bool
    commercial_terms_ref: str | None
    overage_price_usdt_micros_per_unit: int | None
    pricing_evidence_ref: str | None

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id required")
        if (
            self.overage_price_usdt_micros_per_unit is not None
            and self.overage_price_usdt_micros_per_unit < 0
        ):
            raise ValueError(
                "overage_price_usdt_micros_per_unit must be nonnegative"
            )


@dataclass(frozen=True)
class SaasUsageBillingReview:
    tenant_id: str
    charge_preview_ready: bool
    observed_usage_units: int
    included_usage_units: int | None
    billable_overage_units: int | None
    overage_price_usdt_micros_per_unit: int | None
    computed_charge_usdt_micros: int | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    invoice_creation: bool = False
    payment_request_creation: bool = False
    funds_movement: bool = False
    billing_execution: bool = False
    subscription_mutation: bool = False
    recognized_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_saas_usage_billing(
    *,
    quota_review: SaasFreshnessQuotaReview,
    terms: SaasUsageBillingTerms,
) -> SaasUsageBillingReview:
    terms.validate()
    quota = quota_review.quota
    if quota.tenant_id != terms.tenant_id:
        raise ValueError("usage billing tenant mismatch")

    blockers = [
        blocker
        for blocker in quota.blockers
        if blocker != "observed_usage_over_limit"
    ]
    refs: list[str] = []

    terms_ref = str(terms.commercial_terms_ref or "").strip()
    if not terms.commercial_terms_verified or not terms_ref:
        blockers.append("verified_commercial_terms_required")
    else:
        refs.append(terms_ref)

    pricing_ref = str(terms.pricing_evidence_ref or "").strip()
    if terms.overage_price_usdt_micros_per_unit is None or not pricing_ref:
        blockers.append("verified_overage_pricing_evidence_missing")
    else:
        refs.append(pricing_ref)

    included = quota.observed_usage_limit
    billable = None
    charge = None
    if included is not None and included > 0:
        billable = max(quota.observed_monthly_usage - included, 0)
        if terms.overage_price_usdt_micros_per_unit is not None:
            charge = billable * terms.overage_price_usdt_micros_per_unit

    ordered = tuple(sorted(set(blockers)))
    return SaasUsageBillingReview(
        tenant_id=quota.tenant_id,
        charge_preview_ready=not ordered,
        observed_usage_units=quota.observed_monthly_usage,
        included_usage_units=included,
        billable_overage_units=billable,
        overage_price_usdt_micros_per_unit=(
            terms.overage_price_usdt_micros_per_unit
        ),
        computed_charge_usdt_micros=charge,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
