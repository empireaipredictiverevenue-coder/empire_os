"""All-SKU price evidence and competitor-category research, no autonomous repricing.

The live catalogue is a source-reported snapshot; calling this mapper on JSON
does not authenticate its issuer, economic inputs, customer value or legal
terms. A catalogue READY field is not an accepted contract or a transaction.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from empire_os.predictive_catalog_intelligence_contracts import (
    build_catalogue_intelligence_contracts,
)
from empire_os.predictive_competitive_product_comparison import (
    BENCHMARKS, SCHEMA as FLAGSHIP_SCHEMA,
    compare_predictive_enterprise_products,
)
from empire_os.predictive_price_policy_evidence import (
    PricingPolicyHold, review_price_policy_ceiling,
)
from empire_os.predictive_product_specific_competitors import (
    review_product_specific_competitors,
)

SCHEMA = "empire.predictive_revenue.catalogue_price_comparison.v1"
MAX_AMT = 1_000_000_000_000
SEGMENTS_BY_FAMILY = {
    "recovered_mrr": ("crm", "forecasting", "sales_workflows"),
    "search_intelligence": ("analytics", "dashboards", "integrations"),
    "commercial_exchange": ("sales_workflows", "revenue_intelligence"),
    "opportunity_intelligence": ("sales_ai", "revenue_intelligence"),
    "public_record_intelligence": ("analytics", "integrations"),
    "predictive_revenue": ("forecasting", "revenue_intelligence", "sales_ai"),
    "private_capital": ("analytics", "revenue_intelligence"),
    "property": ("analytics", "integrations"),
}


class CataloguePricingHold(ValueError):
    """Source shape or economic provenance must not be normalized silently."""


def review_catalogue_price_comparison(catalogue: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(catalogue, Mapping):
        raise CataloguePricingHold("catalogue unavailable")
    try:
        contracts = build_catalogue_intelligence_contracts(catalogue)
    except (TypeError, ValueError):
        raise CataloguePricingHold("catalogue evidence contract invalid") from None
    if (set(SEGMENTS_BY_FAMILY) != {
        row["product_family"] for row in contracts["products"]
    }):
        raise CataloguePricingHold("unreviewed product family")
    by_code = {
        row["product_code"]: row for row in contracts["products"]
    }
    flagship = compare_predictive_enterprise_products()
    authoritative_prices = {
        p["product_code"]: p["price_usd_cents"] for p in flagship["products"]
    }
    counters: Counter[str] = Counter()
    entries = []
    for original in catalogue["products"]:
        code = original["product_code"]
        contract = by_code[code]
        family = contract["product_family"]
        basis = original.get("price_basis")
        if basis is None:
            basis = {}
        if type(basis) is not dict:
            raise CataloguePricingHold("untrusted catalogue price basis")
        amount = basis.get("amount_cents")
        if amount is not None and (
            type(amount) is not int or not 0 <= amount <= MAX_AMT
        ):
            raise CataloguePricingHold("non-canonical exact USD price")
        unit = basis.get("unit")
        if unit is not None and (
            type(unit) is not str or not 1 <= len(unit) <= 72
        ):
            raise CataloguePricingHold("unrecognised catalogue price unit")
        currency = basis.get("currency") or original.get("currency")
        if (currency not in ("USD", "GBP", "EUR", "CAD", "AUD", "NZD")
                or (basis.get("currency") is not None
                    and original.get("currency") is not None
                    and basis["currency"] != original["currency"])):
            raise CataloguePricingHold("conflicting or unreviewed currency")
        if code in authoritative_prices:
            if amount != authoritative_prices[code] or unit != "per_deployment":
                raise CataloguePricingHold("flagship price conflicts with founder authority")
        state = basis.get("commercial_approval_state")
        approval = basis.get("approval_state")
        source_type = basis.get("source_type")
        if (state is not None and (
                type(state) is not str or not 1 <= len(state) <= 96)):
            raise CataloguePricingHold("source-reported price state malformed")
        if (approval is not None and approval != "FOUNDER_APPROVED"):
            raise CataloguePricingHold("unreviewed price approval source state")
        if source_type == "founder_approved":
            if (state is not None or amount is None
                    or basis.get("state") != "VERIFIED"):
                raise CataloguePricingHold("original founder price custody inconsistent")
            custody = "FOUNDER_APPROVED_PRICE_SOURCE_REPORTED"
        elif source_type == "legacy_consensus":
            if (state != "REQUIRES_FOUNDER_ECONOMICS_REVIEW"
                    or amount is None or basis.get("state") != "VERIFIED"
                    or basis.get("basis_type") != "legacy_recovery_consensus"):
                raise CataloguePricingHold("legacy consensus not founder approved")
            custody = "LEGACY_CONSENSUS_UNAPPROVED"
        elif source_type in ("product_pricing", "product_metadata"):
            if (state != "REQUIRES_FOUNDER_ECONOMICS_REVIEW"
                    or amount is not None or basis.get("state") != "UNKNOWN"
                    or basis.get("basis_type") != "legacy_single_source"
                    or type(basis.get("candidate_amount_cents")) is not int
                    or basis["candidate_amount_cents"] <= 0):
                raise CataloguePricingHold("single-source candidate requires review")
            custody = "LEGACY_SINGLE_SOURCE_CANDIDATE"
        elif source_type is None:
            if (state != "REQUIRES_FOUNDER_PRICE_RESOLUTION"
                    or amount is not None or basis.get("state") != "CONFLICT"
                    or basis.get("basis_type") != "legacy_recovery_conflict"
                    or type(basis.get("metadata_candidate_cents")) is not int
                    or type(basis.get("pricing_candidate_cents")) is not int
                    or basis["metadata_candidate_cents"] <= 0
                    or basis["pricing_candidate_cents"] <= 0
                    or basis["metadata_candidate_cents"]
                    == basis["pricing_candidate_cents"]):
                raise CataloguePricingHold("conflicting historical prices unresolved")
            custody = "LEGACY_CONFLICT_NEEDS_FOUNDER_RESOLUTION"
        else:
            raise CataloguePricingHold("unreviewed price provenance source")
        if source_type != "founder_approved" and approval is not None:
            raise CataloguePricingHold("legacy source cannot claim founder approval")
        displayed_state = (
            state if state is not None
            else "FOUNDER_APPROVED_PRICE_SOURCE_REPORTED"
        )
        if amount is None:
            counters["catalogue_prices_unknown"] += 1
        else:
            counters["catalogue_prices_observed_not_authenticated"] += 1
        try:
            policy = review_price_policy_ceiling(original)
        except PricingPolicyHold:
            raise CataloguePricingHold(
                "original price policy ceiling contradicts catalogue"
            ) from None
        if policy["policy_ceiling_scenario_available"]:
            counters["approved_cost_ceiling_scenarios_available"] += 1
            if policy["policy_ceiling_passes"]:
                counters["approved_ceiling_scenarios_meeting_margin"] += 1
            else:
                counters["approved_ceiling_scenarios_below_margin"] += 1
        lane = review_product_specific_competitors(
            product_code=code, product_family=family,
        )
        competitors = [
            {
                "vendor": b["vendor"],
                "product": b["product"],
                "research_source_url": b["research_source_url"],
                "comparison_type": b["comparison_type"],
                "feature_parity_verified": False,
                "total_price_comparability_verified": False,
                "published_reference_unit": b["published_reference_unit"],
                "published_reference_price_usd_minor": b[
                    "published_reference_price_usd_minor"
                ],
                "price_justified_by_benchmark": False,
            }
            for b in lane["benchmarks"]
        ]
        counters["price_custody_" + custody] += 1
        counters["price_display_state_" + displayed_state] += 1
        counters["adjacent_reference_count"] += len(competitors)
        if not competitors:
            counters["products_without_adjacent_reference"] += 1
        entries.append({
            "product_code": code,
            "product_family": family,
            "product_name": contract["product_name"],
            "catalogue_listed_price_minor_units": amount,
            "catalogue_currency": currency,
            "catalogue_unit": unit,
            "foreign_currency_converted_to_usd": False,
            "catalogue_price_source_approval_state": displayed_state,
            "catalogue_price_basis_source_type": source_type,
            "catalogue_price_original_custody": custody,
            "catalogue_price_source_founder_approved": (
                source_type == "founder_approved"
            ),
            "catalogue_source_approval_is_customer_contract": False,
            "founder_flagship_price_approved": code in authoritative_prices,
            "existing_terms_flag_observed": contract[
                "existing_catalogue_terms_flag_observed"
            ],
            "terms_independently_authenticated": False,
            "product_delivery_accepted_by_customer": False,
            "economic_delivery_cost_verified": False,
            "customer_value_independently_measured": False,
            "forecast_eligible": False,
            "evidence_backed_price_justified": False,
            "price_review_status": "HOLD_ORIGINAL_SCOPE_COST_AND_BENEFIT_PROOF",
            "founder_policy_cost_ceiling_scenario": policy,
            "competitor_lane": lane["lane"],
            "competitor_categories": competitors,
            "no_reliable_direct_comparator_yet": True,
            "automatic_price_changes_authorized": False,
            "external_sales_or_pricing_published": False,
        })
    entries.sort(key=lambda p: (p["product_family"], p["product_code"]))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "FULL_CATALOGUE_PRICE_COMPARISON_RESEARCH_NOT_APPROVED",
        "catalogue_product_count": len(entries),
        "family_counts": dict(sorted(Counter(
            p["product_family"] for p in entries
        ).items())),
        "catalogue_prices_unknown": counters["catalogue_prices_unknown"],
        "catalogue_prices_observed_not_authenticated": counters[
            "catalogue_prices_observed_not_authenticated"
        ],
        "founder_approved_flagship_prices_count": len(authoritative_prices),
        "source_reported_founder_approved_price_count": counters[
            "price_custody_FOUNDER_APPROVED_PRICE_SOURCE_REPORTED"
        ],
        "legacy_consensus_price_review_required_count": counters[
            "price_custody_LEGACY_CONSENSUS_UNAPPROVED"
        ],
        "legacy_price_review_required_count": (
            counters["price_custody_LEGACY_CONSENSUS_UNAPPROVED"]
            + counters["price_custody_LEGACY_SINGLE_SOURCE_CANDIDATE"]
            + counters["price_custody_LEGACY_CONFLICT_NEEDS_FOUNDER_RESOLUTION"]
        ),
        "price_source_custody_counts": {
            "founder_price_source_reported": counters[
                "price_custody_FOUNDER_APPROVED_PRICE_SOURCE_REPORTED"
            ],
            "legacy_consensus_unapproved": counters[
                "price_custody_LEGACY_CONSENSUS_UNAPPROVED"
            ],
            "legacy_single_source_candidate": counters[
                "price_custody_LEGACY_SINGLE_SOURCE_CANDIDATE"
            ],
            "legacy_conflicted_candidate": counters[
                "price_custody_LEGACY_CONFLICT_NEEDS_FOUNDER_RESOLUTION"
            ],
        },
        "source_approval_is_independent_customer_acceptance": False,
        "approved_cost_ceiling_scenarios_available": counters[
            "approved_cost_ceiling_scenarios_available"
        ],
        "approved_ceiling_scenarios_meeting_margin": counters[
            "approved_ceiling_scenarios_meeting_margin"
        ],
        "approved_ceiling_scenarios_below_margin": counters[
            "approved_ceiling_scenarios_below_margin"
        ],
        "approved_cost_ceiling_scenario_is_actual_margin": False,
        "adjacent_reference_count": counters["adjacent_reference_count"],
        "products_without_adjacent_reference": counters[
            "products_without_adjacent_reference"
        ],
        "all_vendor_references_are_research_only": True,
        "original_catalogue_source_authenticated": False,
        "flagship_comparison_schema": FLAGSHIP_SCHEMA,
        "products": entries,
        "astra_gpt6_independent_review": "NOT_EXECUTED",
        "price_change_authority": "none",
        "source_scope_and_licensing_approved": False,
        "commercial_predicted_outcomes_verified": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
