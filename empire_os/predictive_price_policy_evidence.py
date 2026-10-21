"""Exact-unit, local founder-policy cost-ceiling comparison for existing SKUs.

Source-reported price and founder cost ceilings are assumptions, NOT actual
supplier invoices, customer benefit, realised margin, collection or ROI.
Caller source is not authenticated by this pure mapper.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "empire.predictive_revenue.policy_ceiling_scenario.v1"
LIMIT = 1_000_000_000_000


class PricingPolicyHold(ValueError):
    """Original priced product's policy sources are contradictory."""


def _source_cost(
    original: Mapping[str, Any], field: str, *,
    currency: str, unit: str, reference: str, price_minor: int,
) -> int:
    data = original.get(field)
    if (not isinstance(data, Mapping)
            or data.get("state") != "VERIFIED"
            or data.get("basis_type") != "policy_ceiling"
            or data.get("source_type") != "founder_approved"
            or data.get("currency") != currency
            or data.get("unit") != unit
            or type(data.get("amount_cents")) is not int
            or not 0 <= data["amount_cents"] <= LIMIT):
        raise PricingPolicyHold("cost ceiling source contradictory or noncomparable")
    if reference.startswith("founder_approval:"):
        if (data.get("approval_reference") != reference
                or data.get("observed_actual") is not False):
            raise PricingPolicyHold("unmatched or observed cost is not a founder ceiling")
    else:
        if (data.get("approval_date") != reference
                or data.get("observed_cost_claim") is not False
                or type(data.get("ceiling_bps_of_price")) is not int
                or not 0 <= data["ceiling_bps_of_price"] <= 10000
                or data["amount_cents"] > (
                    price_minor * data["ceiling_bps_of_price"] + 9999
                ) // 10000):
            raise PricingPolicyHold("unmatched dated cost ceiling")
    return data["amount_cents"]


def review_price_policy_ceiling(original: Mapping[str, Any]) -> dict[str, Any]:
    """Check the approved *scenario* ceiling; never set price-justified true."""
    if not isinstance(original, Mapping):
        raise PricingPolicyHold("product source invalid")
    price = original.get("price_basis")
    fulfilment = original.get("fulfilment_cost_basis")
    acquisition = original.get("acquisition_cost_basis")
    margin = original.get("margin_policy")
    if not all(isinstance(v, Mapping) for v in (
            price, fulfilment, acquisition, margin)):
        raise PricingPolicyHold("product economics source incomplete")
    states = tuple(v.get("state") for v in (price, fulfilment, acquisition, margin))
    if states != ("VERIFIED",) * 4:
        # Preserve UNKNOWN for missing policy; never calculate on partial state.
        if any(s == "VERIFIED" for s in states) and any(
                s not in ("VERIFIED", "UNKNOWN") for s in states):
            raise PricingPolicyHold("unreviewed partial policy state")
        return {
            "schema_version": SCHEMA,
            "policy_ceiling_scenario_status": "NOT_AVAILABLE_OR_NOT_ALL_VERIFIED",
            "policy_ceiling_scenario_available": False,
            "policy_ceiling_passes": None,
            "listed_price_minor_units": None,
            "maximum_policy_cost_minor_units": None,
            "policy_ceiling_case_contribution_minor_units": None,
            "policy_ceiling_case_margin_bps": None,
            "policy_required_margin_bps": None,
            "headroom_above_minimum_margin_minor_units": None,
            "source_policy_verified_as_actual_cost": False,
            "realized_margin_verified": False,
            "customer_value_verified": False,
            "price_justified_by_evidence": False,
            "execution_authority": "none",
        }
    currency = price.get("currency")
    unit = price.get("unit")
    amount = price.get("amount_cents")
    reference = margin.get("approval_reference") or margin.get("approval_date")
    if (currency not in ("USD", "GBP", "EUR", "CAD", "AUD", "NZD")
            or type(unit) is not str or not unit
            or type(amount) is not int or not 1 <= amount <= LIMIT
            or price.get("source_type") != "founder_approved"
            or type(reference) is not str or not reference
            or (margin.get("source_type") not in (None, "founder_approved"))
            or margin.get("basis_type") != "founder_policy"
            or type(margin.get("minimum_margin_bps")) is not int
            or not 0 <= margin["minimum_margin_bps"] <= 10000):
        raise PricingPolicyHold("original price or margin policy invalid")
    if reference.startswith("founder_approval:"):
        if price.get("approval_reference") != reference:
            raise PricingPolicyHold("price policy provenance differs from costs")
    else:
        if (margin.get("approval_date") != reference
                or price.get("approval_state") != "FOUNDER_APPROVED"):
            raise PricingPolicyHold("dated founder policy not consistent")
    f = _source_cost(
        original, "fulfilment_cost_basis",
        currency=currency, unit=unit, reference=reference, price_minor=amount,
    )
    a = _source_cost(
        original, "acquisition_cost_basis",
        currency=currency, unit=unit, reference=reference, price_minor=amount,
    )
    costs = f + a
    required = margin["minimum_margin_bps"]
    contribution = amount - costs
    allowed_cost_at_min_margin = (amount * (10000 - required)) // 10000
    passes = contribution * 10000 >= amount * required
    return {
        "schema_version": SCHEMA,
        "policy_ceiling_scenario_status": (
            "COST_CEILING_SCENARIO_MEETS_INTERNAL_MARGIN_POLICY"
            if passes else "COST_CEILING_SCENARIO_BELOW_INTERNAL_MARGIN_POLICY"
        ),
        "policy_ceiling_scenario_available": True,
        "policy_ceiling_passes": passes,
        "listed_price_minor_units": amount,
        "maximum_policy_cost_minor_units": costs,
        "policy_ceiling_case_contribution_minor_units": contribution,
        "policy_ceiling_case_margin_bps": (contribution * 10000) // amount,
        "policy_required_margin_bps": required,
        "headroom_above_minimum_margin_minor_units": (
            allowed_cost_at_min_margin - costs
        ),
        "currency": currency,
        "unit": unit,
        "scenario_exclusions": [
            "observed_fulfilment_and_acquisition_costs",
            "payment_processing_and_refunds_unless_in_original_caps",
            "fixed_overhead_tax_legal_support_and_unbudgeted_licences",
            "verified_customer_willingness_to_pay_and_benefit",
            "supplier_invoice_and_separate_settlement",
        ],
        "source_policy_verified_as_actual_cost": False,
        "realized_margin_verified": False,
        "customer_value_verified": False,
        "price_justified_by_evidence": False,
        "execution_authority": "none",
    }
