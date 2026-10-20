"""Read-only per-SKU Predictive Revenue intelligence contracts for the EXISTING catalogue.

This maps product intent to required sources, forecast targets and gated delivery.
It never treats a catalogued SKU, buyer interest, research signal, historical
outcome count or forecast as a purchased/fulfilled/paid product.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import re

from empire_os.predictive_revenue_products import PREDICTIVE_REVENUE_PRODUCTS

SCHEMA = "empire.predictive_revenue.catalog_intelligence_contracts.v1"
SOURCE_SCHEMA = "empire.commercial-product-catalog.v1"
MAX_SKUS = 500
CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,95}$")

# Each lane reuses existing EmpireOS sensing, outcome and human decision systems.
# Predictions remain unavailable until tenant-scoped original evidence is verified.
LANES = {
    "recovered_mrr": (
        ("tenant_scoped_operational_observations", "original_customer_outcomes"),
        ("product_specific_conversion_or_retention_risk", "incremental_value_scenario"),
        "verified_incremental_contribution_margin",
    ),
    "search_intelligence": (
        ("source_dated_search_observations", "query_and_market_provenance"),
        ("relative_demand_or_rank_trend", "search_opportunity_priority"),
        "verified_qualified_acquisition_from_search",
    ),
    "commercial_exchange": (
        ("buyer_capacity_and_acceptance", "original_commercial_terms_and_settlement"),
        ("match_and_fill_probability", "expected_net_contribution"),
        "settled_net_contribution_from_matched_transactions",
    ),
    "opportunity_intelligence": (
        ("original_trigger_evidence", "canonical_entity_and_identity_lineage"),
        ("opportunity_priority", "time_sensitive_conversion_scenario"),
        "verified_converted_opportunities",
    ),
    "public_record_intelligence": (
        ("source_permit_record", "rights_and_location_provenance"),
        ("permit_trigger_forecast", "territory_opportunity_priority"),
        "verified_permissioned_project_conversions",
    ),
    "predictive_revenue": (
        ("tenant_scoped_crm_and_finance_read_models", "original_terminal_outcomes"),
        ("revenue_and_profit_forecast", "baseline_skill_and_calibration"),
        "verified_recognized_revenue_and_realized_profit",
    ),
    "private_capital": (
        ("source_backed_portfolio_entities", "rights_and_temporal_provenance"),
        ("market_consolidation_scenarios", "portfolio_opportunity_priority"),
        "verified_portfolio_economic_outcome",
    ),
    "property": (
        ("canonical_property_evidence", "dated_physical_and_permit_signals"),
        ("property_opportunity_trend", "risk_or_demand_scenario"),
        "verified_accepted_property_opportunity",
    ),
}

TIER_DEPTH = {
    "predictive_revenue_diagnostic": (
        "EVIDENCE_AND_GAP_DIAGNOSTIC",
        ("source_lineage", "leakage_and_bottleneck_review", "action_priorities"),
    ),
    "predictive_revenue_command_center": (
        "TENANT_RESTRICTED_COMMAND_SURFACE",
        ("crm_and_finance_read_models", "forecast_monitoring", "executive_scorecards"),
    ),
    "predictive_revenue_intelligence_os": (
        "CROSS_DEPARTMENT_INTELLIGENCE_OS",
        ("cross_source_reconciliation", "forecast_calibration", "economic_memory"),
    ),
    "predictive_revenue_autonomous_os": (
        "HUMAN_GOVERNED_AGENT_DECISIONS",
        ("opportunity_optimization", "approval_gated_workflows", "decision_audit"),
    ),
    "predictive_revenue_private_strategic": (
        "PRIVATE_TENANT_AND_PORTFOLIO_DEPLOYMENT",
        ("private_data_boundaries", "model_registry", "portfolio_risk_and_audit"),
    ),
}
CANONICAL_TIERS = frozenset(p.product_code for p in PREDICTIVE_REVENUE_PRODUCTS)
assert frozenset(TIER_DEPTH) == CANONICAL_TIERS


class ProductContractHold(ValueError):
    """Untrusted catalogue shape must fail closed instead of omitting SKUs."""


def _count(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SKUS:
        raise ProductContractHold(f"{label} count invalid")
    return value


def _sku(row: Mapping[str, Any]) -> dict[str, Any]:
    code, family, name = (
        row.get("product_code"), row.get("product_family"), row.get("product_name")
    )
    if (type(code) is not str or CODE_RE.fullmatch(code) is None
            or type(name) is not str or not 1 <= len(name.strip()) <= 180
            or type(family) is not str or family not in LANES
            or type(row.get("active")) is not bool
            or type(row.get("binding_terms_ready")) is not bool):
        raise ProductContractHold("invalid product catalogue row")
    if family == "predictive_revenue" and code not in CANONICAL_TIERS:
        raise ProductContractHold("unrecognised flagship tier")
    if family != "predictive_revenue" and code in CANONICAL_TIERS:
        raise ProductContractHold("flagship tier wrongly classified")
    sources, forecasts, actual = LANES[family]
    overrides: tuple[str, ...] = ()
    if family == "recovered_mrr":
        if code.startswith("forecast_"):
            overrides = ("original_time_ordered_revenue_series", "frozen_forecast_baseline")
            forecasts = ("tenant_revenue_forecast", "prediction_interval_and_error")
        elif code.startswith("leadscore_"):
            overrides = ("original_lead_terminal_outcomes",)
            forecasts = ("lead_conversion_probability", "cohort_calibration")
        elif code.startswith("closer_"):
            overrides = ("consented_sales_conversation_evidence",)
            forecasts = ("sales_stage_risk", "human_approved_next_action")
        elif code.startswith(("seo_", "content_", "market_eye_")):
            overrides = ("original_search_and_content_evidence",)
            forecasts = ("organic_demand_trend", "search_revenue_scenario")
    tier = TIER_DEPTH.get(code)
    return {
        "product_code": code,
        "product_family": family,
        "product_name": name.strip(),
        "existing_catalogue_terms_flag_observed": row["binding_terms_ready"],
        "catalogue_listing_is_not_purchase": True,
        "predicted_intelligence_targets": list(forecasts),
        "required_original_sources": sorted(set(sources + overrides)),
        "outcome_to_calibrate_against": actual,
        "tier_depth": tier[0] if tier else "PRODUCT_SPECIFIC_INTELLIGENCE",
        "existing_tier_capability_contract": list(tier[1]) if tier else [],
        "prediction_value": None,
        "prediction_confidence_interval": None,
        "prediction_evidence_status": "UNKNOWN_ORIGINAL_TENANT_OUTCOMES",
        "source_receipts_authenticated_here": False,
        "scientific_baseline_compared_here": False,
        "tenant_scope_verified_here": False,
        "buyer_purchasing_authority_verified": False,
        "commercial_terms_independently_verified": False,
        "fulfilment_available_verified": False,
        "automated_actions_authorized": False,
        "payment_authorized": False,
        "realized_revenue_proven": False,
        "delivery_mode": "PRODUCT_ADVISORY_CONTRACT_ONLY",
        "next_gate": "ORIGINAL_TENANT_SOURCE_AND_PRODUCT_DELIVERY_ACCEPTANCE",
    }


def build_catalogue_intelligence_contracts(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Validate full original catalogue shape, project non-authoritative SKU contracts.

    A supplied snapshot is NEVER independently authenticated by this pure mapper.
    A read-only caller must establish source provenance before downstream use.
    """
    if not isinstance(catalog, Mapping) or catalog.get("schema_version") != SOURCE_SCHEMA:
        raise ProductContractHold("original commercial catalogue schema required")
    count = _count(catalog.get("product_count"), "product")
    ready = _count(catalog.get("binding_terms_ready_count"), "terms-ready")
    rows = catalog.get("products")
    if type(rows) is not list or len(rows) != count:
        raise ProductContractHold("catalogue count disagrees with SKU records")
    seen: set[str] = set()
    contracts: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ProductContractHold("untrusted SKU record")
        item = _sku(row)
        code = item["product_code"]
        if code in seen:
            raise ProductContractHold("duplicate SKU")
        seen.add(code)
        contracts.append(item)
    if sum(x["existing_catalogue_terms_flag_observed"] for x in contracts) != ready:
        raise ProductContractHold("declared terms-ready count contradicts rows")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "PRODUCT_INTELLIGENCE_CONTRACTS_MAPPED_NOT_DELIVERED",
        "catalogue_source_schema": SOURCE_SCHEMA,
        "catalogue_source_authentication": "NOT_PERFORMED_BY_PURE_MAPPING",
        "product_count": count,
        "existing_catalogue_terms_ready_count": ready,
        "products": sorted(contracts, key=lambda x: x["product_code"]),
        "predictive_revenue_tiers_in_catalogue": sum(
            x["product_family"] == "predictive_revenue" for x in contracts
        ),
        "tenant_customer_evidence_verified": False,
        "economic_memory_updated": False,
        "forecasts_computed": False,
        "new_product_created": False,
        "commercial_pricing_changed": False,
        "database_writes": False,
        "outbound_sent": False,
        "production_activated": False,
        "execution_authority": "none",
    }
