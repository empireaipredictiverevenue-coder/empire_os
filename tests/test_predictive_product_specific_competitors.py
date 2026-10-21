"""Explicit SKU-specific adjacent vendor research, never feature parity."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from empire_os.predictive_product_specific_competitors import (
    review_product_specific_competitors, VENDORS, LANES,
)
from empire_os.predictive_catalogue_price_comparison import review_catalogue_price_comparison

CATALOG = Path("/srv/empire_os/runtime/commercial_catalog/latest.json")

@pytest.mark.parametrize("code,family,lane,vendors", [
    ("predictive_revenue_diagnostic", "predictive_revenue", "revenue_platform", {"Clari", "Gong"}),
    ("local_search_grid", "search_intelligence", "local_search", {"BrightLocal", "Semrush"}),
    ("solar_opportunity_map_gb", "search_intelligence", "solar_map_adjacent", {"Regrid", "PropStream"}),
    ("search_opportunity_map", "search_intelligence", "search_analytics", {"Semrush", "Ahrefs"}),
    ("exchange_seat_growth", "commercial_exchange", "lead_routing_adjacent", {"Apollo", "Clay"}),
    ("property_intelligence", "property", "property_adjacent", {"Regrid", "PropStream"}),
    ("permit_intelligence", "public_record_intelligence", "permits_adjacent", {"ConstructConnect"}),
    ("private_capital_rollup", "private_capital", "private_capital", {"Dealroom"}),
    ("leadscore_growth", "recovered_mrr", "prospecting_adjacent", {"Apollo", "Clay"}),
    ("forecast_pro", "recovered_mrr", "revenue_platform", {"Clari", "Gong"}),
    ("meetily_pro", "recovered_mrr", "meeting_workflow_unknown", set()),
    ("all_access", "recovered_mrr", "unmapped_scope", set()),
])
def test_product_lane_chosen_explicitly_without_equal_cost_or_parity(code,family,lane,vendors):
    report = review_product_specific_competitors(product_code=code, product_family=family)
    assert report["lane"] == lane
    assert vendors.issubset({b["vendor"] for b in report["benchmarks"]})
    assert report["benchmark_count"] == len(report["benchmarks"])
    assert report["no_reliable_direct_comparator_yet"] is True
    assert report["automatic_repricing_authorized"] is False
    assert all(
        b["direct_competitor_parity_authenticated"] is False and
        b["contract_total_cost_comparable"] is False and
        b["price_justified_by_benchmark"] is False and
        b["licensing_equivalence_verified"] is False and
        b["research_source_url"].startswith("https://")
        for b in report["benchmarks"]
    )

def test_no_auto_comparable_quote_from_units_or_absent_price():
    for key, details in VENDORS.items():
        vendor, product, url, unit, cents, explanation = details
        assert url.startswith("https://")
        assert unit
        assert cents is None or type(cents) is int and cents > 0
        assert explanation
    assert VENDORS["regrid"][3] == "USD_PER_MONTH_PROPERTY_APP"
    assert VENDORS["dealroom"][3] == "USD_PER_YEAR_STARTING_THREE_SEATS"
    assert VENDORS["apollo"][4] is None

def test_all_original_skus_mapped_once_and_unmapped_explicit():
    catalog=json.loads(CATALOG.read_text())
    report=review_catalogue_price_comparison(catalog)
    rows=report["products"]
    assert len(rows) == 86
    assert len({r["product_code"] for r in rows}) == 86
    assert sum(not r["competitor_categories"] for r in rows) == report["products_without_adjacent_reference"]
    assert report["products_without_adjacent_reference"] > 0
    assert sum(len(r["competitor_categories"]) for r in rows) == report["adjacent_reference_count"]
    assert all(r["no_reliable_direct_comparator_yet"] for r in rows)
    assert all(not item["total_price_comparability_verified"] for r in rows for item in r["competitor_categories"])

def test_forecast_and_source_currency_never_automatically_changed():
    original=json.loads(CATALOG.read_text())
    output=review_catalogue_price_comparison(original)
    assert output["price_change_authority"] == "none"
    assert output["all_vendor_references_are_research_only"] is True
    assert output["approved_ceiling_scenarios_meeting_margin"] == 26
    for sku in output["products"]:
        assert sku["automatic_price_changes_authorized"] is False
        assert sku["evidence_backed_price_justified"] is False

def test_invalid_product_input_rejected():
    for code,family in ((0,"recovered_mrr"),("x",None),([],[])):
        with pytest.raises(ValueError):
            review_product_specific_competitors(product_code=code, product_family=family)
