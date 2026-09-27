"""Founder-approved Predictive Revenue enterprise product ladder.

Predictive Revenue is the commercial engine beneath Predictive Cloud. These
products package existing EmpireOS forecasting, opportunity, revenue truth,
market intelligence and enterprise-control capabilities into sellable
deployment tiers.

The approved USD amounts are launch entry prices / floors. They do not imply
verified fulfilment cost, margin, deployment scope, payment, revenue, or
execution authority. High-ticket deployments remain scoped before binding
commercial terms are accepted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PredictiveRevenueProduct:
    product_code: str
    name: str
    deployment_price_cents: int
    price_type: str
    ideal_buyer: str
    outcome: str
    included_capabilities: tuple[str, ...]
    recurring_model: str
    billing_model: str = "enterprise_deployment"
    currency: str = "USD"
    pricing_state: str = "FOUNDER_APPROVED"
    price_approved_at: str = "2026-09-24"
    binding_terms_ready: bool = False
    execution_mode: str = "OBSERVE"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


PREDICTIVE_REVENUE_PRODUCTS: tuple[PredictiveRevenueProduct, ...] = (
    PredictiveRevenueProduct(
        product_code="predictive_revenue_diagnostic",
        name="Predictive Revenue Diagnostic",
        deployment_price_cents=2_500_000,
        price_type="fixed_entry_price",
        ideal_buyer="growth_company_or_portfolio_company",
        outcome=(
            "Evidence-backed revenue-system diagnostic covering forecast "
            "readiness, leakage, opportunity, bottlenecks and prioritized actions."
        ),
        included_capabilities=(
            "revenue_truth_review",
            "pipeline_and_conversion_analysis",
            "forecast_readiness",
            "revenue_leakage_analysis",
            "market_opportunity_review",
            "priority_action_plan",
        ),
        recurring_model="none_required",
        billing_model="one_time_enterprise_diagnostic",
    ),
    PredictiveRevenueProduct(
        product_code="predictive_revenue_command_center",
        name="Predictive Revenue Command Center",
        deployment_price_cents=5_000_000,
        price_type="starting_deployment_price",
        ideal_buyer="mid_market_growth_team",
        outcome=(
            "Connect core commercial evidence into a live revenue command "
            "surface with forecasting, opportunity and risk intelligence."
        ),
        included_capabilities=(
            "crm_signal_integration",
            "search_and_demand_intelligence",
            "lead_and_buyer_intelligence",
            "revenue_pulse",
            "forecast_surface",
            "opportunity_command_queue",
            "executive_scorecards",
        ),
        recurring_model="custom_managed_intelligence_optional",
    ),
    PredictiveRevenueProduct(
        product_code="predictive_revenue_intelligence_os",
        name="Predictive Revenue Intelligence OS",
        deployment_price_cents=10_000_000,
        price_type="starting_deployment_price",
        ideal_buyer="multi_team_mid_market_or_enterprise",
        outcome=(
            "Company-wide Predictive Revenue operating layer combining "
            "forecasting, market intelligence, scoring, revenue truth and "
            "executive decision support."
        ),
        included_capabilities=(
            "predictive_revenue_command_center",
            "market_and_demand_intelligence",
            "customer_and_buyer_intelligence",
            "search_attention_intelligence",
            "conversion_intelligence",
            "ltv_and_retention_evidence",
            "revenue_truth",
            "economic_memory",
            "prediction_vs_actual_calibration",
        ),
        recurring_model="custom_managed_intelligence_optional",
    ),
    PredictiveRevenueProduct(
        product_code="predictive_revenue_autonomous_os",
        name="Autonomous Predictive Revenue OS",
        deployment_price_cents=20_000_000,
        price_type="starting_deployment_price",
        ideal_buyer="large_multi_market_operator",
        outcome=(
            "Predictive Revenue OS plus governed agent workflows for research, "
            "acquisition, qualification, sales support and optimization."
        ),
        included_capabilities=(
            "predictive_revenue_intelligence_os",
            "governed_agent_workflows",
            "opportunity_factory",
            "buyer_acquisition_system",
            "ai_closer_support",
            "growth_optimization",
            "scenario_intelligence",
            "enterprise_controls",
        ),
        recurring_model="custom_managed_intelligence_optional",
    ),
    PredictiveRevenueProduct(
        product_code="predictive_revenue_private_strategic",
        name="Private Strategic Predictive Revenue Deployment",
        deployment_price_cents=25_000_000,
        price_type="starting_floor",
        ideal_buyer="enterprise_network_private_equity_or_strategic_partner",
        outcome=(
            "Dedicated/private Predictive Revenue environment with custom "
            "models, data boundaries, intelligence feeds and strategic deployment."
        ),
        included_capabilities=(
            "autonomous_predictive_revenue_os",
            "private_deployment",
            "custom_data_boundaries",
            "custom_models",
            "private_intelligence_feeds",
            "white_label_option",
            "portfolio_or_network_scope",
            "dedicated_enterprise_controls",
        ),
        recurring_model="custom_enterprise_contract",
    ),
)


def predictive_revenue_product_catalog() -> dict[str, Any]:
    products = []
    for row in PREDICTIVE_REVENUE_PRODUCTS:
        data = row.as_dict()
        data["deployment_price_display"] = (
            "$" + f"{row.deployment_price_cents / 100:,.0f}"
            + ("+" if row.price_type == "starting_floor" else "")
        )
        products.append(data)

    return {
        "schema_version": "empire.predictive-revenue-products.v1",
        "positioning": "flagship_enterprise_product_line",
        "product_count": len(products),
        "products": products,
        "commercial_hierarchy": {
            "entry": "self_serve_intelligence",
            "recurring": "commercial_exchange",
            "flagship": "predictive_revenue_os",
        },
        "pricing_authority": "founder_approved_2026_09_24",
        "recurring_enterprise_pricing": "custom_scope_not_yet_fixed",
        "binding_terms_ready": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def predictive_revenue_product(product_code: str) -> PredictiveRevenueProduct:
    code = str(product_code or "").strip().lower()
    for row in PREDICTIVE_REVENUE_PRODUCTS:
        if row.product_code == code:
            return row
    raise ValueError("unknown predictive revenue product")
