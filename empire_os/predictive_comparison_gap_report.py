"""Bounded, reproducible commercial price-evidence review queues.

The queue describes *missing proof* from a root-owned source snapshot. It is
not a quote, priced contract, completed ASTRA review, or owner approval.
"""
from __future__ import annotations
from collections import Counter
from typing import Any

SCHEMA = "empire.predictive_revenue.product_comparison_action_gaps.v1"
PRICE_RESOLUTION = "REQUIRES_FOUNDER_PRICE_RESOLUTION"
ECONOMICS_REVIEW = "REQUIRES_FOUNDER_ECONOMICS_REVIEW"


def build_comparison_gap_report(report: dict[str, Any]) -> dict[str, Any]:
    entries = report.get("products")
    if (type(entries) is not list or len(entries) != report.get("catalogue_product_count")
            or len({r["product_code"] for r in entries}) != len(entries)):
        raise ValueError("original catalogue product inventory mismatch")
    queues: dict[str, list[str]] = {
        "founder_price_resolution_required": [],
        "unpriced_founder_economics_required": [],
        "legacy_priced_founder_economics_required": [],
        "source_approved_price_without_full_cost_policy": [],
        "product_scope_or_comparator_research_needed": [],
    }
    for product in entries:
        code = product["product_code"]
        state = product["catalogue_price_source_approval_state"]
        amount = product["catalogue_listed_price_minor_units"]
        source = product["catalogue_price_basis_source_type"]
        ceiling = product["founder_policy_cost_ceiling_scenario"]
        if product["catalogue_price_original_custody"].startswith("LEGACY_"):
            if amount is None and state == PRICE_RESOLUTION:
                queues["founder_price_resolution_required"].append(code)
            elif amount is None and state == ECONOMICS_REVIEW:
                queues["unpriced_founder_economics_required"].append(code)
            elif amount is not None and state == ECONOMICS_REVIEW:
                queues["legacy_priced_founder_economics_required"].append(code)
            else:
                raise ValueError("unexpected legacy pricing state")
        elif product["catalogue_price_original_custody"] == "FOUNDER_APPROVED_PRICE_SOURCE_REPORTED":
            if (state != "FOUNDER_APPROVED_PRICE_SOURCE_REPORTED"
                    or amount is None):
                raise ValueError("original founder source approval inconsistent")
            if not ceiling["policy_ceiling_scenario_available"]:
                queues["source_approved_price_without_full_cost_policy"].append(code)
        else:
            raise ValueError("unreviewed pricing provenance")
        if not product["competitor_categories"]:
            queues["product_scope_or_comparator_research_needed"].append(code)
        if (product["terms_independently_authenticated"]
                or product["economic_delivery_cost_verified"]
                or product["customer_value_independently_measured"]
                or product["evidence_backed_price_justified"]):
            raise ValueError("source inferred independent customer economics")
    for queue in queues.values():
        queue.sort()
    counts = {k:len(v) for k,v in queues.items()}
    if (counts["founder_price_resolution_required"]
            + counts["unpriced_founder_economics_required"]
            != report["catalogue_prices_unknown"]):
        raise ValueError("original missing-price total irreconcilable")
    if (counts["product_scope_or_comparator_research_needed"]
            != report["products_without_adjacent_reference"]):
        raise ValueError("original adjacent competitor inventory mismatch")
    if (counts["source_approved_price_without_full_cost_policy"]
            + report["approved_cost_ceiling_scenarios_available"]
            != report["source_reported_founder_approved_price_count"]):
        raise ValueError("approved price policy bundle irreconcilable")
    if (counts["legacy_priced_founder_economics_required"]
            + counts["unpriced_founder_economics_required"]
            + counts["founder_price_resolution_required"]
            != report["legacy_price_review_required_count"]):
        raise ValueError("legacy pricing review queue irreconcilable")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "PRODUCT_PRICING_EVIDENCE_GAPS_NEED_ORIGINAL_SOURCES",
        "product_count": len(entries),
        "founder_price_source_reported_count": report[
            "source_reported_founder_approved_price_count"
        ],
        "legacy_price_consensus_review_required_count": report[
            "legacy_consensus_price_review_required_count"
        ],
        "legacy_total_founder_review_required_count": report[
            "legacy_price_review_required_count"
        ],
        "founder_approved_cost_ceiling_scenario_count": report[
            "approved_cost_ceiling_scenarios_available"
        ],
        "queue_counts": counts,
        "queues": queues,
        "overlapping_queues_are_not_unique_customer_opportunities": True,
        "internal_cost_policy_is_not_actual_profit": True,
        "independent_customer_acceptance_or_revenue_verified": False,
        "price_changes_authorized": False,
        "astra_gpt6_independent_review": "NOT_EXECUTED",
        "execution_authority": "none",
    }
