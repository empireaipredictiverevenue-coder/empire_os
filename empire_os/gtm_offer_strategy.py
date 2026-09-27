"""Evidence-first multi-niche offer and demo strategy.

Historical agency positioning is retained as product/market strategy only.
Prices, job values, media costs and ROI are never assumed without current
evidence. This module produces plans, not outbound sends or commercial terms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.niche_taxonomy import niche_family


TIER_1_FAMILIES = {"roofing", "restoration"}
TIER_2_FAMILIES = {
    "solar",
    "hvac",
    "logistics",
    "legal",
    "insurance",
    "mortgage",
}


@dataclass(frozen=True)
class NicheOfferContext:
    niche: str
    metro: str | None
    pe_backed: bool | None
    high_cash_flow_evidence: bool | None
    founder_network_fit: bool | None
    opportunity_evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not str(self.niche or "").strip():
            raise ValueError("niche required")


def classify_niche_tier(context: NicheOfferContext) -> dict[str, Any]:
    context.validate()
    family = niche_family(context.niche)

    if family in TIER_1_FAMILIES:
        tier = 1
        reason = "canonical_high_ticket_vertical"
    elif (
        family in TIER_2_FAMILIES
        and (
            context.pe_backed is True
            or context.high_cash_flow_evidence is True
        )
    ):
        tier = 2
        reason = "evidence_backed_high_cash_flow_operation"
    elif context.founder_network_fit is True:
        tier = 3
        reason = "founder_network_or_domain_fit"
    else:
        tier = None
        reason = "insufficient_tier_evidence"

    return {
        "niche_family": family,
        "tier": tier,
        "reason": reason,
        "evidence_refs": list(
            dict.fromkeys(
                ref.strip()
                for ref in context.opportunity_evidence_refs
                if ref.strip()
            )
        ),
        "automatic_market_entry": False,
        "automatic_budget": False,
        "automatic_pricing": False,
    }


def build_demo_asset_plan(
    *,
    context: NicheOfferContext,
    capability_evidence_refs: tuple[str, ...],
) -> dict[str, Any]:
    classification = classify_niche_tier(context)
    family = classification["niche_family"]
    refs = list(
        dict.fromkeys(
            [
                *classification["evidence_refs"],
                *(
                    ref.strip()
                    for ref in capability_evidence_refs
                    if ref.strip()
                ),
            ]
        )
    )

    if family in {"roofing", "restoration"}:
        demo = {
            "hook": "live opportunity and event intelligence",
            "proof_surfaces": [
                "source_signal",
                "qualification",
                "buyer_routing",
                "crm_followup",
            ],
            "lead_magnet": "live_event_radar",
        }
    elif family in {"solar", "hvac", "logistics"}:
        demo = {
            "hook": "revenue leak and capacity audit",
            "proof_surfaces": [
                "pipeline_signal",
                "qualification",
                "conversion",
                "followup",
            ],
            "lead_magnet": "revenue_leak_audit",
        }
    else:
        demo = {
            "hook": "workflow and cost replacement audit",
            "proof_surfaces": [
                "current_process",
                "automation",
                "conversion",
                "economic_evidence",
            ],
            "lead_magnet": "competitor_stack_calculator",
        }

    return {
        "schema_version": "empire.demo_asset_plan.v1",
        "niche_family": family,
        "niche_tier": classification["tier"],
        "metro": context.metro,
        **demo,
        "target_duration_seconds": 180,
        "format": "screen_demo",
        "style": "technical_unscripted",
        "evergreen_pre_nurture": True,
        "evidence_refs": refs,
        "recording_ready": bool(refs),
        "publishing_enabled": False,
        "automatic_distribution": False,
        "pricing_claims_allowed_without_evidence": False,
        "roi_claims_allowed_without_evidence": False,
        "actual_revenue": False,
    }


def build_high_ticket_offer_frame(
    *,
    context: NicheOfferContext,
    verified_price_evidence_ref: str | None,
    verified_outcome_evidence_refs: tuple[str, ...],
) -> dict[str, Any]:
    classification = classify_niche_tier(context)
    price_ref = str(verified_price_evidence_ref or "").strip()
    outcome_refs = tuple(
        dict.fromkeys(
            ref.strip()
            for ref in verified_outcome_evidence_refs
            if ref.strip()
        )
    )

    return {
        "schema_version": "empire.high_ticket_offer_frame.v1",
        "niche_family": classification["niche_family"],
        "niche_tier": classification["tier"],
        "offer_models": [
            "managed_service",
            "setup_plus_usage",
            "usage_based",
            "white_label",
        ],
        "verified_price_available": bool(price_ref),
        "verified_price_evidence_ref": price_ref or None,
        "verified_outcome_evidence_refs": list(outcome_refs),
        "case_study_ready": bool(outcome_refs),
        "commercial_terms_ready": False,
        "automatic_price_selection": False,
        "automatic_terms_acceptance": False,
        "actual_revenue": False,
    }
