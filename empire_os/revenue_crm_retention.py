"""Phase 8 evidence-backed CRM retention and expansion readiness."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RevenueCrmRetentionEvidence:
    buyer_id: str
    buyer_activated: bool
    buyer_evidence_ref: str | None
    payment_verified: bool
    payment_evidence_ref: str | None
    fulfilment_delivered: bool
    fulfilment_evidence_ref: str | None
    outcome_observed: bool
    outcome_success_verified: bool | None
    outcome_evidence_ref: str | None
    buyer_available_capacity: int | None
    capacity_evidence_ref: str | None

    def validate(self) -> None:
        if not self.buyer_id.strip():
            raise ValueError("buyer_id required")
        if (
            self.buyer_available_capacity is not None
            and self.buyer_available_capacity < 0
        ):
            raise ValueError("buyer_available_capacity must be nonnegative")


@dataclass(frozen=True)
class RevenueCrmRetentionExpansionReadiness:
    buyer_id: str
    retention_review_ready: bool
    expansion_review_ready: bool
    retention_blockers: tuple[str, ...]
    expansion_blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    follow_up_execution: bool = False
    payment_execution: bool = False
    crm_mutation: bool = False
    offer_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_retention_expansion_readiness(
    evidence: RevenueCrmRetentionEvidence,
) -> RevenueCrmRetentionExpansionReadiness:
    evidence.validate()
    retention: list[str] = []
    refs: list[str] = []

    if evidence.buyer_activated and str(
        evidence.buyer_evidence_ref or ""
    ).strip():
        refs.append(str(evidence.buyer_evidence_ref).strip())
    else:
        retention.append("activated_buyer_evidence_missing")

    if evidence.payment_verified and str(
        evidence.payment_evidence_ref or ""
    ).strip():
        refs.append(str(evidence.payment_evidence_ref).strip())
    else:
        retention.append("verified_payment_evidence_missing")

    if evidence.fulfilment_delivered and str(
        evidence.fulfilment_evidence_ref or ""
    ).strip():
        refs.append(str(evidence.fulfilment_evidence_ref).strip())
    else:
        retention.append("delivered_fulfilment_evidence_missing")

    if evidence.outcome_observed and str(
        evidence.outcome_evidence_ref or ""
    ).strip():
        refs.append(str(evidence.outcome_evidence_ref).strip())
    else:
        retention.append("observed_outcome_evidence_missing")

    retention_ordered = tuple(sorted(set(retention)))
    expansion = list(retention_ordered)

    if evidence.outcome_success_verified is None:
        expansion.append("successful_outcome_unknown")
    elif evidence.outcome_success_verified is not True:
        expansion.append("successful_outcome_not_verified")

    capacity_ref = str(evidence.capacity_evidence_ref or "").strip()
    if evidence.buyer_available_capacity is None or not capacity_ref:
        expansion.append("verified_buyer_capacity_missing")
    elif evidence.buyer_available_capacity <= 0:
        expansion.append("buyer_capacity_not_available")
        refs.append(capacity_ref)
    else:
        refs.append(capacity_ref)

    expansion_ordered = tuple(sorted(set(expansion)))
    return RevenueCrmRetentionExpansionReadiness(
        buyer_id=evidence.buyer_id,
        retention_review_ready=not retention_ordered,
        expansion_review_ready=not expansion_ordered,
        retention_blockers=retention_ordered,
        expansion_blockers=expansion_ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
