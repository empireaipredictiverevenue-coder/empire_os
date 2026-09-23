"""Founder-policy launch pricing proposal for currently unpriced products.

This file is a non-binding policy proposal until the founder explicitly
approves the exact ladder and the governed commercial catalog independently
verifies the resulting pending versions.

Market anchors were observed on 2026-09-23 from current public pricing for
Ahrefs, Semrush, Local Falcon and SerpApi. Those benchmarks inform positioning
only; Empire prices below are company policy proposals, not claims of observed
historical sale prices or observed unit costs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


POLICY_REFERENCE = "founder_pricing_proposal:2026-09-23:v1"
APPROVAL_REFERENCE = (
    "founder_approval:2026-09-23:commercial_pricing_ladder_v1"
)


@dataclass(frozen=True)
class PricePolicy:
    product_code: str
    billing_model: str
    unit: str
    amount_cents: int
    acquisition_cost_ceiling_cents: int
    fulfilment_cost_ceiling_cents: int
    minimum_margin_bps: int
    positioning: str
    included_units: int | None = None
    overage_amount_cents: int | None = None

    @property
    def policy_margin_bps(self) -> int:
        contribution = (
            self.amount_cents
            - self.acquisition_cost_ceiling_cents
            - self.fulfilment_cost_ceiling_cents
        )
        return int(contribution * 10000 / self.amount_cents)

    def as_approved_dict(
        self,
        approval_reference: str,
    ) -> dict[str, Any]:
        reference = str(approval_reference or "").strip()
        if not reference:
            raise ValueError("explicit founder approval reference required")

        value = self.as_dict()
        for key in (
            "price_basis",
            "acquisition_cost_basis",
            "fulfilment_cost_basis",
            "margin_policy",
        ):
            basis = dict(value[key])
            basis["state"] = "VERIFIED"
            basis["source_type"] = "founder_approved"
            basis["approval_reference"] = reference
            basis.pop("proposal_reference", None)
            value[key] = basis

        value["binding"] = False
        value["founder_approval_required"] = False
        value["founder_approval_reference"] = reference
        return value

    def as_dict(self) -> dict[str, Any]:
        price_basis: dict[str, Any] = {
            "state": "PROPOSED",
            "basis_type": "founder_policy",
            "source_type": "founder_policy_proposal",
            "currency": "USD",
            "unit": self.unit,
            "amount_cents": self.amount_cents,
            "proposal_reference": POLICY_REFERENCE,
        }
        if self.included_units is not None:
            price_basis["included_units"] = self.included_units
        if self.overage_amount_cents is not None:
            price_basis["overage_amount_cents"] = self.overage_amount_cents

        return {
            "product_code": self.product_code,
            "billing_model": self.billing_model,
            "currency": "USD",
            "price_basis": price_basis,
            "acquisition_cost_basis": {
                "state": "PROPOSED",
                "basis_type": "policy_ceiling",
                "source_type": "founder_policy_proposal",
                "currency": "USD",
                "unit": self.unit,
                "amount_cents": self.acquisition_cost_ceiling_cents,
                "observed_actual": False,
                "proposal_reference": POLICY_REFERENCE,
            },
            "fulfilment_cost_basis": {
                "state": "PROPOSED",
                "basis_type": "policy_ceiling",
                "source_type": "founder_policy_proposal",
                "currency": "USD",
                "unit": self.unit,
                "amount_cents": self.fulfilment_cost_ceiling_cents,
                "observed_actual": False,
                "proposal_reference": POLICY_REFERENCE,
            },
            "margin_policy": {
                "state": "PROPOSED",
                "basis_type": "founder_policy",
                "minimum_margin_bps": self.minimum_margin_bps,
                "proposal_reference": POLICY_REFERENCE,
            },
            "policy_margin_bps": self.policy_margin_bps,
            "positioning": self.positioning,
            "binding": False,
            "founder_approval_required": True,
        }


LAUNCH_PRICING: tuple[PricePolicy, ...] = (
    PricePolicy("local_search_grid", "monthly_subscription", "per_month", 7900, 800, 1200, 6500, "SMB/local entry product"),
    PricePolicy("content_protection", "monthly_subscription", "per_month", 9900, 1000, 1500, 6500, "SMB content decay/cannibalisation monitor"),
    PricePolicy("geo_ai_visibility", "monthly_subscription", "per_month", 14900, 1500, 2000, 6500, "AI/AEO/GEO visibility monitoring"),
    PricePolicy("authority_intelligence", "monthly_subscription", "per_month", 14900, 1500, 2000, 6500, "authority/backlink intelligence"),
    PricePolicy("competitor_search_gap", "one_time", "per_report", 19900, 2000, 3000, 6500, "one-off competitor opportunity report"),
    PricePolicy("search_opportunity_map", "one_time", "per_report", 24900, 2500, 5000, 6500, "one-off search opportunity map"),
    PricePolicy("technical_search_audit", "one_time", "per_audit", 29900, 3000, 6000, 6500, "technical SEO/search audit"),
    PricePolicy("search_growth_command", "monthly_subscription", "per_month", 29900, 4000, 6000, 6500, "combined SMB/mid-market search command product"),
    PricePolicy("serp_intelligence_api", "usage_and_subscription", "per_month", 9900, 1500, 2000, 6000, "developer/API entry tier", included_units=10000, overage_amount_cents=1),
    PricePolicy("permit_intelligence", "monthly_subscription", "per_month", 49900, 7500, 7500, 6500, "high-value public-record opportunity intelligence"),
    PricePolicy("property_intelligence", "monthly_subscription", "per_month", 79900, 12000, 12000, 6500, "property/operator intelligence"),
    PricePolicy("private_capital_rollup", "monthly_subscription", "per_month", 150000, 20000, 25000, 6500, "private-capital and roll-up intelligence"),
)


def build_launch_pricing_proposal() -> dict[str, Any]:
    products = [policy.as_dict() for policy in LAUNCH_PRICING]
    return {
        "schema_version": "empire.commercial_pricing_policy.v1",
        "policy_reference": POLICY_REFERENCE,
        "currency": "USD",
        "product_count": len(products),
        "products": products,
        "existing_verified_product_unchanged": {
            "product_code": "managed_service",
            "amount_cents": 150000,
            "billing_model": "flat_pilot",
        },
        "market_anchor_note": (
            "Current public prices for Ahrefs, Semrush, Local Falcon and "
            "SerpApi informed positioning; Empire amounts are founder-policy "
            "proposals, not observed historical transaction prices."
        ),
        "binding": False,
        "founder_approval_required": True,
        "approved_live_reference": APPROVAL_REFERENCE,
        "database_mutation_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
