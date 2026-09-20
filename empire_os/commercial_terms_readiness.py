"""Evidence-only readiness review for proposing commercial terms.

This module does not choose a price, approve an offer, accept terms, create a
payment request, or recognize revenue. It only says whether the evidence needed
by the governed commercial-terms RPC is complete.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CommercialTermsReadinessEvidence:
    closer_case_id: str
    fulfilment_order_id: str
    buyer_id: str
    prospect_id: str
    order_state: str
    buyer_conversation_observed: bool
    capacity_intake_state: str
    capacity_evidence_ref: str | None
    territory: str | None
    daily_cap: int | None
    delivery_route: str | None
    proposed_price_cents: int | None
    verified_price_evidence_ref: str | None
    acquisition_cost_cents: int | None
    acquisition_cost_evidence_ref: str | None
    fulfilment_cost_cents: int | None
    fulfilment_cost_evidence_ref: str | None

    def validate(self) -> None:
        for label, value in (
            ("closer_case_id", self.closer_case_id),
            ("fulfilment_order_id", self.fulfilment_order_id),
            ("buyer_id", self.buyer_id),
            ("prospect_id", self.prospect_id),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{label} required")


@dataclass(frozen=True)
class CommercialTermsReadiness:
    ready_for_terms_proposal: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    expected_margin_cents: int | None
    terms_packet: dict[str, Any] | None
    pricing_authority: str = "none"
    approval_authority: str = "none"
    acceptance_authority: str = "none"
    settlement_authority: str = "none"
    actual_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def review_commercial_terms_readiness(
    evidence: CommercialTermsReadinessEvidence,
) -> CommercialTermsReadiness:
    evidence.validate()
    blockers: list[str] = []
    refs: list[str] = []

    if evidence.order_state not in {"qualified", "matched"}:
        blockers.append("qualified_or_matched_order_required")

    if evidence.buyer_conversation_observed is not True:
        blockers.append("genuine_buyer_conversation_missing")

    capacity_ref = _clean(evidence.capacity_evidence_ref)
    if evidence.capacity_intake_state != "complete" or not capacity_ref:
        blockers.append("complete_buyer_capacity_evidence_missing")
    else:
        refs.append(capacity_ref)

    if not _clean(evidence.territory):
        blockers.append("buyer_territory_missing")
    if evidence.daily_cap is None or evidence.daily_cap <= 0:
        blockers.append("buyer_daily_capacity_missing")
    if _clean(evidence.delivery_route) not in {
        "email",
        "webhook",
        "phone",
        "api",
    }:
        blockers.append("buyer_delivery_route_missing")

    price_ref = _clean(evidence.verified_price_evidence_ref)
    if evidence.proposed_price_cents is None or evidence.proposed_price_cents <= 0:
        blockers.append("verified_price_missing")
    elif not price_ref:
        blockers.append("verified_price_evidence_missing")
    else:
        refs.append(price_ref)

    acquisition_ref = _clean(evidence.acquisition_cost_evidence_ref)
    if evidence.acquisition_cost_cents is None or evidence.acquisition_cost_cents < 0:
        blockers.append("acquisition_cost_missing")
    elif not acquisition_ref:
        blockers.append("acquisition_cost_evidence_missing")
    else:
        refs.append(acquisition_ref)

    fulfilment_ref = _clean(evidence.fulfilment_cost_evidence_ref)
    if evidence.fulfilment_cost_cents is None or evidence.fulfilment_cost_cents < 0:
        blockers.append("fulfilment_cost_missing")
    elif not fulfilment_ref:
        blockers.append("fulfilment_cost_evidence_missing")
    else:
        refs.append(fulfilment_ref)

    margin: int | None = None
    if (
        evidence.proposed_price_cents is not None
        and evidence.proposed_price_cents > 0
        and evidence.acquisition_cost_cents is not None
        and evidence.acquisition_cost_cents >= 0
        and evidence.fulfilment_cost_cents is not None
        and evidence.fulfilment_cost_cents >= 0
    ):
        margin = (
            evidence.proposed_price_cents
            - evidence.acquisition_cost_cents
            - evidence.fulfilment_cost_cents
        )
        if margin <= 0:
            blockers.append("positive_expected_margin_required")

    ordered = tuple(sorted(set(blockers)))
    packet: dict[str, Any] | None = None
    if not ordered:
        packet = {
            "currency": "USD",
            "settlement_asset": "USDT",
            "settlement_chain": "BSC",
            "territory": _clean(evidence.territory),
            "daily_cap": evidence.daily_cap,
            "delivery_route": _clean(evidence.delivery_route),
            "price_cents": evidence.proposed_price_cents,
            "acquisition_cost_cents": evidence.acquisition_cost_cents,
            "fulfilment_cost_cents": evidence.fulfilment_cost_cents,
            "expected_margin_cents": margin,
            "buyer_capacity_evidence_ref": capacity_ref,
            "verified_price_evidence_ref": price_ref,
            "acquisition_cost_evidence_ref": acquisition_ref,
            "fulfilment_cost_evidence_ref": fulfilment_ref,
            "binding": False,
            "actual_revenue": False,
        }

    return CommercialTermsReadiness(
        ready_for_terms_proposal=not ordered,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
        expected_margin_cents=margin,
        terms_packet=packet,
    )
