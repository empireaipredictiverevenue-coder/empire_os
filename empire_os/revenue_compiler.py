from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from empire_os.predictive_cloud_fabric import (
    EvidenceRef,
    PredictiveCloudFabricContext,
)


@dataclass(frozen=True)
class OpportunitySignal:
    opportunity_id: str
    vertical: str | None
    geography: str | None
    opportunity_type: str | None
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class ProductCandidate:
    product_id: str
    name: str
    price_cents: int | None

    active: bool
    fulfilment_ready: bool
    checkout_ready: bool

    verticals: frozenset[str]
    geographies: frozenset[str]
    opportunity_types: frozenset[str]

    recurring: bool = False
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class RevenuePlan:
    opportunity_id: str
    product_id: str
    product_name: str
    price_cents: int | None
    recurring: bool

    exact_match_dimensions: int
    evidence_refs: tuple[str, ...]

    ready_for_offer: bool
    blockers: tuple[str, ...]


def _match(
    value: str | None,
    allowed: frozenset[str],
) -> tuple[bool, bool]:
    if "*" in allowed:
        return True, False
    if value is None:
        return False, False
    return (value in allowed, value in allowed)


def compile_revenue_plan(
    *,
    context: PredictiveCloudFabricContext,
    opportunity: OpportunitySignal,
    product: ProductCandidate,
) -> RevenuePlan:
    if context.opportunity_id not in {
        None,
        opportunity.opportunity_id,
    }:
        raise ValueError("fabric opportunity mismatch")

    blockers: list[str] = []
    exact = 0

    if not product.active:
        blockers.append("product_inactive")

    if not product.fulfilment_ready:
        blockers.append("fulfilment_not_ready")

    if not product.checkout_ready:
        blockers.append("checkout_not_ready")

    if product.price_cents is None:
        blockers.append("price_unavailable")

    dimensions = (
        (
            opportunity.vertical,
            product.verticals,
            "vertical_not_eligible",
        ),
        (
            opportunity.geography,
            product.geographies,
            "geography_not_eligible",
        ),
        (
            opportunity.opportunity_type,
            product.opportunity_types,
            "opportunity_type_not_eligible",
        ),
    )

    for value, allowed, blocker in dimensions:
        eligible, is_exact = _match(value, allowed)

        if not eligible:
            blockers.append(blocker)

        exact += int(is_exact)

    if not opportunity.evidence:
        blockers.append("opportunity_evidence_missing")

    evidence_refs = tuple(sorted({
        ref.ref
        for ref in (
            *opportunity.evidence,
            *product.evidence,
        )
    }))

    return RevenuePlan(
        opportunity_id=opportunity.opportunity_id,
        product_id=product.product_id,
        product_name=product.name,
        price_cents=product.price_cents,
        recurring=product.recurring,
        exact_match_dimensions=exact,
        evidence_refs=evidence_refs,
        ready_for_offer=not blockers,
        blockers=tuple(blockers),
    )


def compile_revenue_plans(
    *,
    context: PredictiveCloudFabricContext,
    opportunity: OpportunitySignal,
    products: Iterable[ProductCandidate],
) -> tuple[RevenuePlan, ...]:
    plans = tuple(
        compile_revenue_plan(
            context=context,
            opportunity=opportunity,
            product=product,
        )
        for product in products
    )

    # Eligibility/match ordering only.
    # Canonical Empire economic algorithms retain economic priority.
    return tuple(sorted(
        plans,
        key=lambda plan: (
            not plan.ready_for_offer,
            -plan.exact_match_dimensions,
            plan.product_id,
        ),
    ))
