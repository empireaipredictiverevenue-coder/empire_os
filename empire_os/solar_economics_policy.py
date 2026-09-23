"""Founder economics proposal for localized Solar Opportunity Maps.

This module produces policy ceilings only. They are not observed historical costs. The founder approved these policy
ceilings on 2026-09-23; they may now be used as verified commercial-policy
evidence while remaining distinct from observed historical spend.

Proposal shape mirrors the existing first-cash governance pattern:
- acquisition-cost ceiling: 20% of local selling price
- fulfilment-cost ceiling: 20% of local selling price
- resulting contribution floor at both ceilings: 60%
- proposed minimum gross margin policy: 55%
- policy buffer between ceiling case and minimum margin: 5 percentage points

No catalog mutation, buyer acceptance, payment mutation or revenue recognition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from empire_os.market_pricing import SOLAR_OPPORTUNITY_MAP_PRICES


ACQUISITION_CEILING_BPS = 2000
FULFILMENT_CEILING_BPS = 2000
MINIMUM_MARGIN_BPS = 5500
POLICY_STATE = "FOUNDER_APPROVED"


def _bps_amount(amount_minor: int, bps: int) -> int:
    return int(amount_minor * bps // 10000)


def build_market_economics_proposal() -> dict[str, Any]:
    rows = []
    for price in SOLAR_OPPORTUNITY_MAP_PRICES.values():
        acquisition = _bps_amount(
            price.amount_minor,
            ACQUISITION_CEILING_BPS,
        )
        fulfilment = _bps_amount(
            price.amount_minor,
            FULFILMENT_CEILING_BPS,
        )
        contribution = (
            price.amount_minor
            - acquisition
            - fulfilment
        )
        realized_margin_bps = int(
            contribution * 10000 // price.amount_minor
        )

        rows.append({
            "product_code": price.product_code,
            "country_code": price.country_code,
            "currency": price.currency,
            "display_price": price.display_price,
            "price_minor": price.amount_minor,
            "price_state": price.approval_state,
            "acquisition_cost_ceiling": {
                "state": POLICY_STATE,
                "amount_minor": acquisition,
                "currency": price.currency,
                "unit": "per_map",
                "basis_type": "founder_policy_proposal",
                "ceiling_bps_of_price": ACQUISITION_CEILING_BPS,
                "observed_cost_claim": False,
            },
            "fulfilment_cost_ceiling": {
                "state": POLICY_STATE,
                "amount_minor": fulfilment,
                "currency": price.currency,
                "unit": "per_map",
                "basis_type": "founder_policy_proposal",
                "ceiling_bps_of_price": FULFILMENT_CEILING_BPS,
                "observed_cost_claim": False,
            },
            "margin_policy": {
                "state": POLICY_STATE,
                "minimum_margin_bps": MINIMUM_MARGIN_BPS,
                "basis_type": "founder_policy_proposal",
            },
            "ceiling_case": {
                "contribution_minor": contribution,
                "realized_margin_bps": realized_margin_bps,
                "margin_buffer_bps": (
                    realized_margin_bps - MINIMUM_MARGIN_BPS
                ),
            },
            "binding_terms_ready": False,
            "founder_approved": True,
            "actual_revenue": False,
        })

    return {
        "schema_version": "empire.solar-economics-policy-proposal.v1",
        "policy_state": POLICY_STATE,
        "acquisition_ceiling_bps": ACQUISITION_CEILING_BPS,
        "fulfilment_ceiling_bps": FULFILMENT_CEILING_BPS,
        "minimum_margin_bps": MINIMUM_MARGIN_BPS,
        "ceiling_case_margin_bps": (
            10000
            - ACQUISITION_CEILING_BPS
            - FULFILMENT_CEILING_BPS
        ),
        "policy_buffer_bps": (
            10000
            - ACQUISITION_CEILING_BPS
            - FULFILMENT_CEILING_BPS
            - MINIMUM_MARGIN_BPS
        ),
        "market_count": len(rows),
        "markets": rows,
        "proposal_is_observed_cost": False,
        "resource_observations_used_as_cash_cost": False,
        "founder_approval_required": False,
        "founder_approval_date": "2026-09-23",
        "catalog_mutation_authorized": True,
        "binding_terms_ready": False,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "actual_revenue": False,
        "execution_authority": "proposal_only",
    }


def catalog_economics_basis(country_code: str) -> dict[str, Any]:
    """Return founder-approved catalog basis for one localized market."""
    proposal = build_market_economics_proposal()
    row = next(
        item for item in proposal["markets"]
        if item["country_code"] == str(country_code).strip().upper()
    )
    price = SOLAR_OPPORTUNITY_MAP_PRICES[
        str(country_code).strip().upper()
    ]
    return {
        "product_code": row["product_code"],
        "billing_model": "one_time",
        "currency": row["currency"],
        "price_basis": {
            "state": "VERIFIED",
            "amount_cents": row["price_minor"],
            "currency": row["currency"],
            "unit": "per_map",
            "billing_model": "one_time",
            "source_type": "founder_approved",
            "approval_state": "FOUNDER_APPROVED",
            "rationale": price.rationale,
        },
        "acquisition_cost_basis": {
            "state": "VERIFIED",
            "amount_cents": row["acquisition_cost_ceiling"]["amount_minor"],
            "currency": row["currency"],
            "unit": "per_map",
            "source_type": "founder_approved",
            "basis_type": "policy_ceiling",
            "ceiling_bps_of_price": ACQUISITION_CEILING_BPS,
            "observed_cost_claim": False,
            "approval_date": "2026-09-23",
        },
        "fulfilment_cost_basis": {
            "state": "VERIFIED",
            "amount_cents": row["fulfilment_cost_ceiling"]["amount_minor"],
            "currency": row["currency"],
            "unit": "per_map",
            "source_type": "founder_approved",
            "basis_type": "policy_ceiling",
            "ceiling_bps_of_price": FULFILMENT_CEILING_BPS,
            "observed_cost_claim": False,
            "approval_date": "2026-09-23",
        },
        "margin_policy": {
            "state": "VERIFIED",
            "minimum_margin_bps": MINIMUM_MARGIN_BPS,
            "basis_type": "founder_policy",
            "approval_date": "2026-09-23",
        },
        "provenance": {
            "source": "empire_os.solar_economics_policy",
            "country_code": row["country_code"],
            "policy_state": "FOUNDER_APPROVED",
            "approval_date": "2026-09-23",
            "policy_ceiling_not_observed_cost": True,
            "resource_observations_used_as_cash_cost": False,
            "binding_terms_ready": False,
        },
        "evidence_refs": [
            (
                "founder_approved_economics:"
                f"{row['product_code']}:"
                "cac20_fulfilment20_margin55"
            ),
            "runtime:solar_opportunity_maps/economics_latest.json",
        ],
    }
