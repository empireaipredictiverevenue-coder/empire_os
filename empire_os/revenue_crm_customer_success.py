"""Phase 8 evidence-only customer-success review routing."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.revenue_crm_retention_freshness import (
    RevenueCrmRetentionFreshness,
)


@dataclass(frozen=True)
class CustomerSuccessReviewRoute:
    buyer_id: str
    available: bool
    review_type: str | None
    reason: str
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    follow_up_execution: bool = False
    crm_mutation: bool = False
    offer_mutation: bool = False
    payment_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def route_customer_success_review(
    freshness: RevenueCrmRetentionFreshness,
) -> CustomerSuccessReviewRoute:
    refs = freshness.base_readiness.evidence_refs
    if freshness.expansion_fresh_for_review:
        return CustomerSuccessReviewRoute(
            buyer_id=freshness.buyer_id,
            available=True,
            review_type="expansion_review",
            reason="fresh_verified_success_and_capacity_support_expansion_review",
            blockers=(),
            evidence_refs=refs,
        )

    if freshness.retention_fresh_for_review:
        expansion_only = tuple(
            blocker
            for blocker in freshness.blockers
            if blocker in {
                "successful_outcome_unknown",
                "successful_outcome_not_verified",
                "verified_buyer_capacity_missing",
                "buyer_capacity_not_available",
            }
            or blocker.startswith("capacity_")
        )
        return CustomerSuccessReviewRoute(
            buyer_id=freshness.buyer_id,
            available=True,
            review_type="retention_review",
            reason="retention_evidence_is_fresh_but_expansion_is_not_verified",
            blockers=expansion_only,
            evidence_refs=refs,
        )

    return CustomerSuccessReviewRoute(
        buyer_id=freshness.buyer_id,
        available=False,
        review_type=None,
        reason="retention_evidence_not_ready_or_not_fresh",
        blockers=freshness.blockers,
        evidence_refs=refs,
    )
