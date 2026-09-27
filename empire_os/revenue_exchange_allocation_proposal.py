"""Phase 13 evidence-only inventory-to-buyer allocation proposal review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_allocation_readiness import ExchangeAllocationReadiness


@dataclass(frozen=True)
class ExchangeAllocationProposalEvidence:
    inventory_id: str
    buyer_id: str
    niche: str
    metro: str
    inventory_qualified: bool
    inventory_evidence_ref: str | None
    buyer_capacity_remaining: int | None
    buyer_capacity_evidence_ref: str | None
    proposed_price_cents: int
    verified_price_evidence_ref: str | None
    territory_eligible: bool | None
    territory_evidence_ref: str | None
    exclusivity_clear: bool | None
    exclusivity_evidence_ref: str | None

    def validate(self) -> None:
        for label, value in (
            ("inventory_id", self.inventory_id),
            ("buyer_id", self.buyer_id),
            ("niche", self.niche),
            ("metro", self.metro),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{label} required")
        if self.proposed_price_cents <= 0:
            raise ValueError("proposed_price_cents must be positive")
        if self.buyer_capacity_remaining is not None and self.buyer_capacity_remaining < 0:
            raise ValueError("buyer_capacity_remaining must be nonnegative")


@dataclass(frozen=True)
class ExchangeAllocationProposalReview:
    inventory_id: str
    buyer_id: str
    niche: str
    metro: str
    proposed_price_cents: int
    ready_for_operator_match_review: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    allocation_authority: str = "none"
    pricing_authority: str = "none"
    settlement_authority: str = "none"
    exclusivity_authority: str = "none"
    funds_movement: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_exchange_allocation_proposal(
    *,
    snapshot: ExchangeSnapshot,
    readiness: ExchangeAllocationReadiness,
    evidence: ExchangeAllocationProposalEvidence,
) -> ExchangeAllocationProposalReview:
    evidence.validate()
    if (
        snapshot.niche != evidence.niche
        or snapshot.metro != evidence.metro
        or readiness.niche != evidence.niche
        or readiness.metro != evidence.metro
    ):
        raise ValueError("allocation proposal market identity mismatch")

    blockers = list(readiness.blockers)
    refs = list(readiness.evidence_refs)
    if not readiness.ready_for_operator_allocation_review:
        blockers.append("market_allocation_not_ready")

    inventory_ref = str(evidence.inventory_evidence_ref or "").strip()
    if evidence.inventory_qualified and inventory_ref:
        refs.append(inventory_ref)
    else:
        blockers.append("qualified_inventory_evidence_missing")

    capacity_ref = str(evidence.buyer_capacity_evidence_ref or "").strip()
    if evidence.buyer_capacity_remaining is None or not capacity_ref:
        blockers.append("buyer_capacity_evidence_missing")
    elif evidence.buyer_capacity_remaining <= 0:
        refs.append(capacity_ref)
        blockers.append("buyer_capacity_not_available")
    else:
        refs.append(capacity_ref)

    price_ref = str(evidence.verified_price_evidence_ref or "").strip()
    if not price_ref:
        blockers.append("verified_price_evidence_missing")
    else:
        refs.append(price_ref)
    if evidence.proposed_price_cents not in snapshot.verified_price_per_lead_cents:
        blockers.append("proposed_price_not_in_verified_market_set")

    territory_ref = str(evidence.territory_evidence_ref or "").strip()
    if evidence.territory_eligible is None or not territory_ref:
        blockers.append("territory_eligibility_evidence_missing")
    elif evidence.territory_eligible is not True:
        refs.append(territory_ref)
        blockers.append("buyer_not_territory_eligible")
    else:
        refs.append(territory_ref)

    exclusivity_ref = str(evidence.exclusivity_evidence_ref or "").strip()
    if evidence.exclusivity_clear is None or not exclusivity_ref:
        blockers.append("exclusivity_clearance_evidence_missing")
    elif evidence.exclusivity_clear is not True:
        refs.append(exclusivity_ref)
        blockers.append("exclusivity_conflict_observed")
    else:
        refs.append(exclusivity_ref)

    ordered = tuple(sorted(set(blockers)))
    return ExchangeAllocationProposalReview(
        inventory_id=evidence.inventory_id,
        buyer_id=evidence.buyer_id,
        niche=evidence.niche,
        metro=evidence.metro,
        proposed_price_cents=evidence.proposed_price_cents,
        ready_for_operator_match_review=not ordered,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
