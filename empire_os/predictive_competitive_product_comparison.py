"""Source-labelled enterprise price and capability comparison; never a price approval.

This analysis does not compare bespoke deployments to SaaS seat fees as if the
scope, cost, terms, security, delivery, or value were equivalent. It keeps the
existing founder-approved prices intact, admits no fabricated costs or ROI,
and prepares a reproducible ASTRA GPT-6 independent review packet.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from empire_os.predictive_revenue_products import PREDICTIVE_REVENUE_PRODUCTS

SCHEMA = "empire.predictive_revenue.competitive_product_comparison.v1"
AS_OF = "2026-10-21"

# Official vendor pricing links verified in the research on the date above.
# USD seat/month pricing only; no extrapolation to an enterprise deployment.
# Quote-required entries deliberately have a null published price.
BENCHMARKS = (
    {
        "vendor": "HubSpot", "product": "Sales Hub Enterprise",
        "billing": "USD_PER_USER_MONTH_ANNUAL",
        "public_unit_price_usd": 150,
        "source_url": "https://legal.hubspot.com/hubspot-product-and-services-catalog",
        "segments": ("crm", "sales_workflows", "analytics", "forecasting"),
        "notes": "Additional onboarding, services and seats may apply",
    },
    {
        "vendor": "Microsoft", "product": "Dynamics 365 Sales Enterprise",
        "billing": "USD_PER_USER_MONTH_ANNUAL",
        "public_unit_price_usd": 105,
        "source_url": "https://www.microsoft.com/en-us/dynamics-365/products/sales/pricing",
        "segments": ("crm", "sales_workflows", "sales_ai", "forecasting"),
        "notes": "Other licences and integrations are not included in this number",
    },
    {
        "vendor": "Zoho", "product": "CRM Enterprise",
        "billing": "USD_PER_USER_MONTH_ANNUAL",
        "public_unit_price_usd": 40,
        "source_url": "https://www.zoho.com/crm/zohocrm-pricing-enterprise.html",
        "segments": ("crm", "sales_workflows", "analytics", "sales_ai"),
        "notes": "SaaS seat fee; no equivalent private consulting delivery implied",
    },
    {
        "vendor": "Clari", "product": "Revenue Platform",
        "billing": "CONTACT_VENDOR_FOR_QUOTE",
        "public_unit_price_usd": None,
        "source_url": "https://www.clari.com/pricing/",
        "segments": ("revenue_intelligence", "forecasting", "sales_workflows"),
        "notes": "Public quote form; no unverified numerical price inferred",
    },
    {
        "vendor": "Gong", "product": "Revenue AI",
        "billing": "CUSTOM_PER_USER_PLUS_PLATFORM_FEE",
        "public_unit_price_usd": None,
        "source_url": "https://www.gong.io/pricing",
        "segments": ("revenue_intelligence", "conversation_intelligence", "forecasting"),
        "notes": "Custom quote varies by licences, platform scale and services",
    },
    {
        "vendor": "Databox", "product": "Team Core",
        "billing": "USD_PER_MONTH_PLATFORM",
        "public_unit_price_usd": 249,
        "source_url": "https://databox.com/pricing",
        "segments": ("analytics", "dashboards", "integrations"),
        "notes": "Platform subscription; bespoke implementation pricing is separate",
    },
)

PRODUCT_OVERLAP = {
    "predictive_revenue_diagnostic": (
        "analytics", "revenue_intelligence", "forecasting",
    ),
    "predictive_revenue_command_center": (
        "crm", "analytics", "dashboards", "forecasting", "integrations",
    ),
    "predictive_revenue_intelligence_os": (
        "revenue_intelligence", "forecasting", "analytics", "sales_ai",
    ),
    "predictive_revenue_autonomous_os": (
        "revenue_intelligence", "forecasting", "sales_workflows", "sales_ai",
    ),
    "predictive_revenue_private_strategic": (
        "revenue_intelligence", "forecasting", "integrations", "analytics",
    ),
}

REQUIRED_JUSTIFICATION = (
    "buyer_confirmed_problem_and_willingness_to_pay",
    "bounded_deliverable_scope_and_acceptance_criteria",
    "authenticated_source_rights_and_data_access",
    "implementation_labor_and_infrastructure_cost",
    "ongoing_support_security_and_sla_cost",
    "independent_benefit_or_relevant_customer_value_evidence",
    "refund_contract_tax_and_payment_terms",
    "delivery_feasibility_and_tenant_isolation",
)


def compare_predictive_enterprise_products() -> dict[str, Any]:
    """Compare features and units without implied price parity or false ROI."""
    if set(PRODUCT_OVERLAP) != {p.product_code for p in PREDICTIVE_REVENUE_PRODUCTS}:
        raise ValueError("enterprise product ladder and benchmark scope diverged")
    comparators = tuple(
        dict(b,
             observed_as_of=AS_OF,
             source_kind="PUBLISHED_VENDOR_PAGE",
             independent_feature_parity_verified=False,
             contract_equivalence_verified=False)
        for b in BENCHMARKS
    )
    products = []
    for product in PREDICTIVE_REVENUE_PRODUCTS:
        overlap = frozenset(PRODUCT_OVERLAP[product.product_code])
        competitor_lanes = [
            {
                "vendor": benchmark["vendor"],
                "product": benchmark["product"],
                "common_category_labels": sorted(
                    overlap.intersection(benchmark["segments"])
                ),
                "actual_feature_parity_verified": False,
                "comparable_total_contract_cost_verified": False,
            }
            for benchmark in BENCHMARKS
        ]
        products.append({
            "product_code": product.product_code,
            "product_name": product.name,
            "price_usd_cents": product.deployment_price_cents,
            "approved_price_type": product.price_type,
            "founder_price_state_preserved": product.pricing_state,
            "price_is_one_time_or_floor": product.billing_model,
            "current_product_outcome_claim": product.outcome,
            "proposed_scope_categories": list(PRODUCT_OVERLAP[product.product_code]),
            "competitors": competitor_lanes,
            "justification_requirements": list(REQUIRED_JUSTIFICATION),
            "verified_cost_of_delivery_usd_cents": None,
            "verified_customer_value_usd_cents": None,
            "verified_gross_margin_percent": None,
            "empirical_value_or_roi_proven": False,
            "real_customer_acceptance_test_passed": False,
            "scoped_binding_terms_verified": False,
            "price_justification_status": "UNVERIFIED_PENDING_SCOPE_COST_AND_CUSTOMER_VALUE",
            "competitive_price_ordering_is_valid": False,
            "automatic_price_change_authorized": False,
            "customer_claim_or_public_announcement_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "observed_as_of": AS_OF,
        "source_kind": "public_official_vendor_pricing_page_research",
        "comparator_count": len(comparators),
        "comparators": list(comparators),
        "product_count": len(products),
        "products": products,
        "comparison_method": "CATEGORY_OVERLAP_NOT_FUNCTIONAL_EQUIVALENCE",
        "seats_and_bespoke_projects_not_normalized_to_one_price": True,
        "astra_gpt6_independent_review": "NOT_EXECUTED",
        "independent_review_requires_exact_committed_code_and_tests": True,
        "price_authority": "existing_founder_approved_prices_unchanged",
        "registered_forecasts_or_actual_profit_authenticated": False,
        "original_database_or_runtime_queried": False,
        "customer_price_approval_or_sales_execution": False,
        "model_weights_changed": False,
        "execution_authority": "none",
    }
