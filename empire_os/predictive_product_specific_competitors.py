"""Citable adjacent vendor reference lanes for EmpireOS SKU comparison.

Official-page observations are static research references, not verified feature
parity, binding vendor offers, approved licences, or direct price comparisons.
Unknown SKUs deliberately receive no benchmark instead of a fake match.
"""
from __future__ import annotations

from typing import Any

from empire_os.predictive_competitive_product_comparison import BENCHMARKS

AS_OF = "2026-10-21"
SCHEMA = "empire.predictive_revenue.product_specific_adjacent_comparators.v1"

# Current publicly described products. The price amount is one OBSERVED
# reference unit in USD cents, never a normalized equivalent Empire offer.
VENDORS = {
    "semrush_seo": ("Semrush", "SEO toolkit", "https://www.semrush.com/pricing/seo-ai-search/",
                    "USD_PER_MONTH_MONTHLY", 13900, "Research: SEO platform subscription"),
    "ahrefs": ("Ahrefs", "Lite", "https://ahrefs.com/pricing/",
               "USD_PER_MONTH", 12900, "Research: SEO platform subscription"),
    "brightlocal": ("BrightLocal", "Track",
                    "https://www.brightlocal.com/pricing/",
                    "USD_PER_MONTH_ONE_LOCATION", 4100,
                    "Research: monthly Track for one location; annual lower effective rate"),
    "semrush_local": ("Semrush", "Local Base",
                      "https://www.semrush.com/pricing/local/",
                      "USD_PER_LOCATION_MONTH_ANNUAL", 3000,
                      "Research: billed annually; add-ons and other limits differ"),
    "apollo": ("Apollo", "Sales intelligence",
               "https://www.apollo.io/pricing", "MULTIPLE_SEAT_AND_CREDIT_PLANS",
               None, "Research: credit/seat mix changes effective costs"),
    "clay": ("Clay", "Launch",
             "https://www.clay.com/pricing", "USD_PER_MONTH_MONTHLY",
             18500, "Research: starting monthly plan; separate data and action credits"),
    "builtwith": ("BuiltWith", "Basic",
                  "https://builtwith.com/plans", "USD_PER_MONTH", 29500,
                  "Research: technographics database subscription"),
    "propstream": ("PropStream", "Essentials",
                   "https://www.propstream.com/pricing", "USD_PER_MONTH_MONTHLY", 9900,
                   "Research: property intelligence subscription; not bulk data rights"),
    "regrid": ("Regrid", "Property App Pro",
               "https://app.regrid.com/plans", "USD_PER_MONTH_PROPERTY_APP",
               1000, "Research: app access; not an enterprise parcel API licence"),
    "constructconnect": ("ConstructConnect", "Project Intelligence Starter",
                         "https://www.constructconnect.com/pricing",
                         "USD_PER_MARKET_PER_SEAT_MONTH_STARTING", 12900,
                         "Research: regional commercial project listings; not verified permit API"),
    "dealroom": ("Dealroom", "Premium", "https://dealroom.co/pricing-usd",
                 "USD_PER_YEAR_STARTING_THREE_SEATS", 1450000,
                 "Research: annual capital intelligence platform; not financial advisory services"),
}
LEGACY = {
    b["vendor"].lower(): {
        "vendor": b["vendor"], "product": b["product"],
        "source_url": b["source_url"] if "source_url" in b else (
            "https://www.microsoft.com/en-us/dynamics-365/products/sales/pricing"
            if b["vendor"] == "Microsoft" else
            "https://www.zoho.com/crm/zohocrm-pricing-enterprise.html"
            if b["vendor"] == "Zoho" else
            "https://legal.hubspot.com/hubspot-product-and-services-catalog"
            if b["vendor"] == "HubSpot" else
            "https://www.clari.com/pricing/" if b["vendor"] == "Clari" else
            "https://www.gong.io/pricing" if b["vendor"] == "Gong"
            else "https://databox.com/pricing"
        ),
        "published_reference_unit": b["billing"],
        "published_reference_price_usd_minor": (
            b["public_unit_price_usd"] * 100
            if b["public_unit_price_usd"] is not None else None
        ),
        "research_note": b["notes"],
    } for b in BENCHMARKS
}

LANES = {
    "revenue_platform": ("hubspot", "microsoft", "zoho", "clari", "gong", "databox"),
    "local_search": ("brightlocal", "semrush_local"),
    "search_analytics": ("semrush_seo", "ahrefs", "brightlocal"),
    "solar_map_adjacent": ("propstream", "regrid", "semrush_local"),
    "prospecting_adjacent": ("apollo", "clay", "builtwith"),
    "lead_routing_adjacent": ("apollo", "clay"),
    "property_adjacent": ("propstream", "regrid"),
    "permits_adjacent": ("constructconnect", "regrid"),
    "private_capital": ("dealroom",),
    "meeting_workflow_unknown": (),
    "unmapped_scope": (),
}

def _lane(code: str, family: str) -> str:
    if family == "predictive_revenue":
        return "revenue_platform"
    if family == "search_intelligence":
        if code.startswith("solar_opportunity_map_"):
            return "solar_map_adjacent"
        if code in ("local_search_grid", "geo_ai_visibility"):
            return "local_search"
        return "search_analytics"
    if family == "commercial_exchange":
        return "lead_routing_adjacent"
    if family == "opportunity_intelligence":
        return "prospecting_adjacent"
    if family == "private_capital":
        return "private_capital"
    if family == "property":
        return "property_adjacent"
    if family == "public_record_intelligence":
        return "permits_adjacent"
    if family == "recovered_mrr":
        if code.startswith(("seo_", "market_eye_", "content_pulse_")):
            return "search_analytics"
        if code.startswith(("leadscore_", "scraper_", "spy_data")):
            return "prospecting_adjacent"
        if code.startswith(("contractor_exchange_", "closer_", "router_saas")):
            return "lead_routing_adjacent"
        if code.startswith("forecast_"):
            return "revenue_platform"
        if code.startswith("meetily_"):
            return "meeting_workflow_unknown"
    return "unmapped_scope"


def review_product_specific_competitors(*, product_code: str, product_family: str) -> dict[str, Any]:
    if type(product_code) is not str or type(product_family) is not str:
        raise ValueError("product identity required")
    lane = _lane(product_code, product_family)
    if lane not in LANES:
        raise ValueError("unreviewed competitor lane")
    items: list[dict[str, Any]] = []
    for key in LANES[lane]:
        if key in VENDORS:
            vendor, name, url, unit, cents, note = VENDORS[key]
            item = dict(
                vendor=vendor, product=name, research_source_url=url,
                published_reference_unit=unit,
                published_reference_price_usd_minor=cents,
                research_note=note,
            )
        else:
            item = dict(LEGACY[key],
                        research_source_url=LEGACY[key]["source_url"])
            item.pop("source_url")
        items.append({
            **item,
            "research_as_of": AS_OF,
            "comparison_type": "ADJACENT_MARKET_REFERENCE_ONLY",
            "direct_competitor_parity_authenticated": False,
            "contract_total_cost_comparable": False,
            "licensing_equivalence_verified": False,
            "price_justified_by_benchmark": False,
        })
    return {
        "schema_version": SCHEMA,
        "lane": lane,
        "benchmark_count": len(items),
        "benchmarks": items,
        "product_scope_authenticated_by_mapping": False,
        "no_reliable_direct_comparator_yet": True,
        "vendor_prices_are_not_equivalent_quotes": True,
        "automatic_repricing_authorized": False,
        "execution_authority": "none",
    }
