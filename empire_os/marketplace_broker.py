from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from empire_os.predictive_cloud_fabric import (
    EvidenceRef,
    PredictiveCloudFabricContext,
)


PPM = 1_000_000


def _probability(value: int | None) -> None:
    if value is not None and not 0 <= value <= PPM:
        raise ValueError("probability must be 0..1,000,000 PPM")


@dataclass(frozen=True)
class LeadDemand:
    lead_id: str
    vertical: str | None
    geography: str | None
    source: str | None
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class BuyerLiquidityOffer:
    buyer_id: str
    provider: str

    verticals: frozenset[str]
    geographies: frozenset[str]
    permitted_sources: frozenset[str]

    payout_cents: int | None
    acceptance_probability_ppm: int | None
    quality_probability_ppm: int | None
    payment_reliability_ppm: int | None

    capacity_available: bool
    active: bool
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if self.payout_cents is not None and self.payout_cents < 0:
            raise ValueError("payout must be >= 0 or unavailable")

        for value in (
            self.acceptance_probability_ppm,
            self.quality_probability_ppm,
            self.payment_reliability_ppm,
        ):
            _probability(value)


@dataclass(frozen=True)
class BuyerAllocationProposal:
    lead_id: str
    buyer_id: str
    provider: str
    eligible: bool
    expected_buyer_value_cents: int | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def expected_buyer_value_cents(
    *,
    payout_cents: int | None,
    acceptance_probability_ppm: int | None,
    quality_probability_ppm: int | None,
    payment_reliability_ppm: int | None,
) -> int | None:
    factors = (
        payout_cents,
        acceptance_probability_ppm,
        quality_probability_ppm,
        payment_reliability_ppm,
    )

    if any(value is None for value in factors):
        return None

    assert payout_cents is not None
    assert acceptance_probability_ppm is not None
    assert quality_probability_ppm is not None
    assert payment_reliability_ppm is not None

    return (
        payout_cents
        * acceptance_probability_ppm
        * quality_probability_ppm
        * payment_reliability_ppm
    ) // (PPM ** 3)


def build_allocation_proposal(
    *,
    context: PredictiveCloudFabricContext,
    lead: LeadDemand,
    offer: BuyerLiquidityOffer,
) -> BuyerAllocationProposal:
    if context.lead_id not in {None, lead.lead_id}:
        raise ValueError("fabric lead mismatch")

    blockers: list[str] = []

    if not offer.active:
        blockers.append("buyer_offer_inactive")

    if not offer.capacity_available:
        blockers.append("buyer_capacity_unavailable")

    if lead.vertical is None:
        blockers.append("lead_vertical_unavailable")
    elif (
        "*" not in offer.verticals
        and lead.vertical not in offer.verticals
    ):
        blockers.append("vertical_not_eligible")

    if lead.geography is None:
        blockers.append("lead_geography_unavailable")
    elif (
        "*" not in offer.geographies
        and lead.geography not in offer.geographies
    ):
        blockers.append("geography_not_eligible")

    if lead.source is None:
        blockers.append("lead_source_unavailable")
    elif (
        "*" not in offer.permitted_sources
        and lead.source not in offer.permitted_sources
    ):
        blockers.append("source_not_permitted")

    if not lead.evidence:
        blockers.append("lead_evidence_missing")

    if not offer.evidence:
        blockers.append("buyer_offer_evidence_missing")

    expected = expected_buyer_value_cents(
        payout_cents=offer.payout_cents,
        acceptance_probability_ppm=offer.acceptance_probability_ppm,
        quality_probability_ppm=offer.quality_probability_ppm,
        payment_reliability_ppm=offer.payment_reliability_ppm,
    )

    evidence_refs = tuple(sorted({
        ref.ref
        for ref in (
            *lead.evidence,
            *offer.evidence,
        )
    }))

    return BuyerAllocationProposal(
        lead_id=lead.lead_id,
        buyer_id=offer.buyer_id,
        provider=offer.provider,
        eligible=not blockers,
        expected_buyer_value_cents=expected,
        blockers=tuple(blockers),
        evidence_refs=evidence_refs,
    )


def build_allocation_book(
    *,
    context: PredictiveCloudFabricContext,
    lead: LeadDemand,
    offers: Iterable[BuyerLiquidityOffer],
) -> tuple[BuyerAllocationProposal, ...]:
    proposals = tuple(
        build_allocation_proposal(
            context=context,
            lead=lead,
            offer=offer,
        )
        for offer in offers
    )

    return tuple(sorted(
        proposals,
        key=lambda item: (
            not item.eligible,
            item.expected_buyer_value_cents is None,
            -(item.expected_buyer_value_cents or 0),
            item.provider,
            item.buyer_id,
        ),
    ))


def preferred_verified_destination(
    proposals: Iterable[BuyerAllocationProposal],
) -> BuyerAllocationProposal | None:
    for proposal in proposals:
        if (
            proposal.eligible
            and proposal.expected_buyer_value_cents is not None
        ):
            return proposal

    return None
