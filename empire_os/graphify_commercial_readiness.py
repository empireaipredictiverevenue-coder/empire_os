"""Graphify-specific commercial evidence handoff to EXISTING owner gates.

Pure, private, OBSERVE-only. The source, finance, capacity, and predictive
owners authenticate evidence; graph similarity or forum chatter cannot do so.
This module never creates predictions, scores, buyers, leads, or actions.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

SCHEMA = "empire.graphify.commercial_evidence_readiness.v1"
COMPARISON_SCHEMA = "empire.graphify.market_research_join.v1"
VALUE_SCHEMA = "empire.predictive.customer_value_outcome_readiness.v1"
SOURCE_SCHEMA = "empire.predictive_revenue.market_economic_source_readiness.v1"
SHADOW_SCHEMA = "empire.lead_shadow_calibration_benchmark.v1"
MAX_LANES = 300


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _validate_comparison(comparison: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (not isinstance(comparison, Mapping)
            or comparison.get("schema_version") != COMPARISON_SCHEMA
            or comparison.get("status") != "RESEARCH_COMPARISON_ONLY_NO_BUYER_OR_REVENUE_PROOF"
            or comparison.get("mode") != "OBSERVE"
            or comparison.get("execution_authority") != "none"
            or comparison.get("model_training_authorized") is not False
            or comparison.get("campaign_execution_authorized") is not False):
        raise ValueError("untrusted Graphify research comparison")
    actual = comparison.get("comparison_sha256")
    if actual != _digest({k: v for k, v in comparison.items() if k != "comparison_sha256"}):
        raise ValueError("Graphify comparison content mismatch")
    rows = comparison.get("joined_lanes")
    if (not isinstance(rows, list) or not 0 <= len(rows) <= MAX_LANES
            or comparison.get("joined_lane_count") != len(rows)):
        raise ValueError("invalid Graphify lane evidence count")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("untrusted graph lane")
        ident = row.get("lane_ref")
        if not isinstance(ident, str) or not ident.startswith("revenue:") or ident in seen:
            raise ValueError("duplicate or untrusted graph lane identity")
        seen.add(ident)
        if (row.get("buyer_capacity_verified") is not False
                or row.get("demand_or_purchase_intent_verified") is not False
                or row.get("commercial_rights_verified") is not False
                or row.get("predictive_uplift_verified") is not False
                or row.get("forecast_probability") is not None
                or row.get("forecast_net_revenue") is not None):
            raise ValueError("unverified graph row promoted to commercial claim")
        for name in ("reported_buyer_demand_links", "reported_buyer_capacity_links",
                     "unknown_demand_edges", "fresh_lane_evidence_edges"):
            v = row.get(name)
            if type(v) is not int or v < 0 or v > 100_000:
                raise ValueError("invalid bounded graph evidence count")
    if comparison.get("matched_market_count") != len({
        row.get("matched_market_vertical") for row in rows
        if row.get("matched_market_vertical") is not None
    }):
        raise ValueError("market match count inconsistent")
    if comparison.get("matched_lane_count") != sum(
        row.get("matched_market_vertical") is not None for row in rows
    ):
        raise ValueError("lane match count inconsistent")
    return rows


def review_graphify_commercial_readiness(
    *, research_comparison: Mapping[str, Any],
    customer_value_readiness: Mapping[str, Any] | None,
    market_source_readiness: Mapping[str, Any] | None,
    shadow_calibration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare the exact graph-specific holds; never authorise commercial use.

    Aggregate owner checks are NOT authenticated individual customers, buyer
    receipts or model training permission. The graph-specific uplift gate
    remains closed until the existing prediction registry holds paired
    pre-outcome graph and baseline forecasts, with independent evaluation.
    """
    rows = _validate_comparison(research_comparison)
    blockers: set[str] = set()
    source_states = None
    if customer_value_readiness is None:
        blockers.add("OWNER_CUSTOMER_VALUE_READINESS_MISSING")
    else:
        v = customer_value_readiness
        if (not isinstance(v, Mapping)
                or v.get("schema_version") != VALUE_SCHEMA
                or v.get("mode") != "OBSERVE"
                or v.get("execution_authority") != "none"
                or v.get("model_outcome_calibration_authorized") is not False
                or v.get("customer_revenue_or_savings_verified_by_this_check") is not False
                or v.get("database_writes") is not False
                or v.get("outbound_sent") is not False):
            raise ValueError("unsafe customer-value readiness owner packet")
        for field in ("canonical_capacity_terms_verified_count",
                      "canonical_capacity_verified_count"):
            number = v.get(field)
            if number is not None and (type(number) is not int or not 0 <= number <= 100_000):
                raise ValueError("untrusted owner aggregate capacity count")
        for field in ("authenticated_product_app_service_purchases",
                      "authenticated_customer_value_measurements"):
            number = v.get(field)
            if number is not None and (type(number) is not int or not 0 <= number <= 100_000):
                raise ValueError("untrusted owner aggregate outcome count")
        if v.get("status") != "CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED":
            blockers.add("OWNER_CUSTOMER_VALUE_SOURCE_HOLD")
        if (v.get("canonical_capacity_terms_verified_count") is None or
                v.get("canonical_capacity_terms_verified_count") == 0):
            blockers.add("CANONICAL_BUYER_TERMS_UNVERIFIED")
        if (v.get("canonical_capacity_verified_count") is None or
                v.get("canonical_capacity_verified_count") == 0):
            blockers.add("CANONICAL_BUYER_CAPACITY_UNVERIFIED")
        if not v.get("authenticated_product_app_service_purchases"):
            blockers.add("AUTHENTICATED_CUSTOMER_PURCHASE_RECEIPTS_NOT_LINKED")
        if not v.get("authenticated_customer_value_measurements"):
            blockers.add("AUTHENTICATED_CUSTOMER_VALUE_OUTCOMES_NOT_LINKED")
        if v.get("original_prediction_registry_enabled_verified") is not True:
            blockers.add("CANONICAL_ORIGINAL_FORECAST_REGISTRY_NOT_PROVEN")

    if market_source_readiness is None:
        blockers.add("OWNER_MARKET_SOURCE_READINESS_MISSING")
    else:
        s = market_source_readiness
        if (not isinstance(s, Mapping)
                or s.get("schema_version") != SOURCE_SCHEMA
                or s.get("status") != "SOURCE_OWNER_MARKET_CONTEXT_REVIEWED"
                or s.get("mode") != "OBSERVE"
                or s.get("execution_authority") != "none"
                or s.get("database_writes") is not False
                or s.get("outbound_sent") is not False
                or s.get("economic_playbook_production_authorized") is not False):
            raise ValueError("unsafe market-source readiness packet")
        owners = s.get("sources")
        if not isinstance(owners, Mapping) or set(owners) != {
            "market_gps", "competitor_intelligence", "storm_opportunity"
        }:
            raise ValueError("incomplete existing source owner universe")
        source_states = {}
        for name, source in sorted(owners.items()):
            if (not isinstance(source, Mapping) or
                    source.get("source_owner") != name or
                    source.get("geographic_buying_capacity_authenticated") is not False or
                    source.get("may_calibrate_market_shock") is not False):
                raise ValueError("untrusted market source claim")
            state = source.get("status")
            if not isinstance(state, str) or len(state) > 100:
                raise ValueError("invalid source evidence status")
            source_states[name] = state
            if state != "RESEARCH_COVERAGE_FRESH_NOT_COMMERCIAL_PROOF":
                blockers.add("SOURCE_OWNER_" + name.upper() + "_NOT_FRESH")
        if s.get("original_source_revision_bound_to_pilot") is not False:
            raise ValueError("market source revision falsely bound")
        blockers.add("TERRITORY_SPECIFIC_SOURCE_AND_COMMERCIAL_RIGHTS_UNVERIFIED")

    if shadow_calibration is None:
        blockers.add("OWNER_TEMPORAL_CALIBRATION_EVIDENCE_UNAVAILABLE")
    else:
        c = shadow_calibration
        if (not isinstance(c, Mapping)
                or c.get("schema_version") != SHADOW_SCHEMA
                or c.get("mode") != "OBSERVE"
                or c.get("execution_authority") != "none"
                or c.get("training_performed") is not False
                or c.get("model_weight_mutation") is not False
                or c.get("promoted_learning") is not False
                or c.get("outbound_authorized") is not False
                or c.get("commercial_activation_authorized") is not False):
            raise ValueError("unsafe existing shadow calibration packet")
        if c.get("evaluation_ready") is not True:
            blockers.add("OWNER_TEMPORAL_CALIBRATION_HOLD")
        if c.get("lead_research_formula_evaluated") is not False:
            raise ValueError("shadow calibration falsely attributes graph evaluation")

    blockers.update((
        "GRAPH_AUGMENTED_VS_BASELINE_ORIGINAL_FORECAST_COHORT_MISSING",
        "INDEPENDENT_GRAPH_UPLIFT_NOT_PROVEN",
        "GRAPH_FEATURE_ML_REUSE_RIGHTS_NOT_ATTESTED",
        "GRAPH_OPERATOR_AUTHORIZATION_NOT_GRANTED",
    ))
    lanes = []
    for row in rows:
        specific = []
        if row["matched_market_vertical"] is None:
            specific.append("APPROVED_PUBLIC_PRODUCT_MARKET_MAPPING_MISSING")
        if not row["fresh_lane_evidence_edges"]:
            specific.append("FRESH_LANE_EVIDENCE_MISSING")
        if row["unknown_demand_edges"]:
            specific.append("DEMAND_QUANTITY_UNVERIFIED")
        if not row["reported_buyer_capacity_links"]:
            specific.append("REPORTED_BUYER_CAPACITY_LINK_MISSING")
        lanes.append({
            "lane_ref": row["lane_ref"],
            "market_vertical": row["matched_market_vertical"],
            "mapping_status": row["mapping_status"],
            "fresh_source_evidence_edge_count": row["fresh_lane_evidence_edges"],
            "unverified_demand_edge_count": row["unknown_demand_edges"],
            "reported_buyer_capacity_link_count": row["reported_buyer_capacity_links"],
            "public_research_observations": row["public_forum_observation_count"],
            "lane_evidence_holds": sorted(specific),
            "real_buyers_or_sales_established": False,
            "lead_or_buyer_allocation_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": "GRAPHIFY_EVIDENCE_REVIEW_ONLY_COMMERCIAL_HOLD",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "source_comparison_sha256": research_comparison["comparison_sha256"],
        "market_source_owner_statuses": source_states,
        "graph_lane_count": len(lanes),
        "graph_lanes": lanes,
        "required_owner_evidence": sorted(blockers),
        "verified_graph_roi_uplift": None,
        "verified_buyer_count": None,
        "verified_revenue": None,
        "graph_prediction_outcome_pairs": None,
        "next_owner": "existing_predictive_ledger_buyer_source_and_commerce_owners",
        "next_action": "OBTAIN_CANONICAL_BUYER_TERMS_OUTCOME_RECEIPTS_AND_ORIGINAL_GRAPH_FORECAST_PAIRS",
        "training_authorized": False,
        "campaign_authorized": False,
        "payments_authorized": False,
        "production_deployment_authorized": False,
    }
