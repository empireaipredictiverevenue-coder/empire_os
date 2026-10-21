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
        if state is not None and (type(state) is not str or not 1 <= len(state) <= 96):
            raise CataloguePricingHold("source-reported price state malformed")
        if amount is None:
            counters["catalogue_prices_unknown"] += 1
        else:
            counters["catalogue_prices_observed_not_authenticated"] += 1
        categories = set(SEGMENTS_BY_FAMILY[family])
        competitors = [
            {
                "vendor": b["vendor"],
                "product": b["product"],
                "category_overlap": sorted(categories.intersection(b["segments"])),
                "feature_parity_verified": False,
                "total_price_comparability_verified": False,
            }
            for b in BENCHMARKS
        ]
        entries.append({
            "product_code": code,
            "product_family": family,
            "product_name": contract["product_name"],
            "catalogue_listed_price_minor_units": amount,
            "catalogue_currency": currency,
            "catalogue_unit": unit,
            "foreign_currency_converted_to_usd": False,
            "catalogue_price_source_approval_state": state or "UNKNOWN",
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
            "competitor_categories": competitors,
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
