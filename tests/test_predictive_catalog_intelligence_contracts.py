"""Product catalogue integration is one intelligence engine with fail-closed SKUs."""
from copy import deepcopy
import json

import pytest

from empire_os.predictive_catalog_intelligence_contracts import (
    ProductContractHold, build_catalogue_intelligence_contracts, TIER_DEPTH, LANES,
)


def catalog(rows=None):
    if rows is None:
        rows = [
            {"product_code": "forecast_pro", "product_name": "Forecast Pro",
             "product_family": "recovered_mrr", "binding_terms_ready": False,
             "active": True, "customer_name": "PRIVATE_NAME_DO_NOT_EMIT"},
            {"product_code": "competitor_search_gap",
             "product_name": "Competitor Search Gap",
             "product_family": "search_intelligence",
             "binding_terms_ready": True, "active": True},
            {"product_code": "predictive_revenue_diagnostic",
             "product_name": "Predictive Revenue Diagnostic",
             "product_family": "predictive_revenue",
             "binding_terms_ready": False, "active": True},
        ]
    return {"schema_version": "empire.commercial-product-catalog.v1",
            "product_count": len(rows),
            "binding_terms_ready_count":
                sum(r.get("binding_terms_ready") is True for r in rows),
            "products": rows}


def test_three_products_separate_pricing_from_forecasts():
    original = catalog()
    before = deepcopy(original)
    output = build_catalogue_intelligence_contracts(original)
    assert original == before
    assert output["product_count"] == 3
    assert output["existing_catalogue_terms_ready_count"] == 1
    assert output["forecasts_computed"] is False
    assert output["execution_authority"] == "none"
    assert "PRIVATE_NAME_DO_NOT_EMIT" not in json.dumps(output)
    for item in output["products"]:
        assert item["prediction_value"] is None
        assert item["prediction_confidence_interval"] is None
        assert item["tenant_scope_verified_here"] is False
        assert item["commercial_terms_independently_verified"] is False
        assert item["payment_authorized"] is False
        assert item["realized_revenue_proven"] is False


def test_forecast_and_leadscore_product_specific_targets():
    rows = [dict(product_code="forecast_lite", product_name="Forecast Lite",
                 product_family="recovered_mrr", active=True,
                 binding_terms_ready=False),
            dict(product_code="leadscore_growth", product_name="LeadScore",
                 product_family="recovered_mrr", active=True,
                 binding_terms_ready=False)]
    result = build_catalogue_intelligence_contracts(catalog(rows))
    indexed = {x["product_code"]: x for x in result["products"]}
    assert "tenant_revenue_forecast" in indexed["forecast_lite"]["predicted_intelligence_targets"]
    assert "lead_conversion_probability" in indexed["leadscore_growth"]["predicted_intelligence_targets"]


def test_all_flagship_product_tiers_preserved_without_auto_delivery():
    rows = [
        {"product_code": code, "product_name": code.replace("_", " "),
         "product_family": "predictive_revenue", "binding_terms_ready": False,
         "active": True} for code in TIER_DEPTH
    ]
    out = build_catalogue_intelligence_contracts(catalog(rows))
    assert out["predictive_revenue_tiers_in_catalogue"] == 5
    assert {x["tier_depth"] for x in out["products"]} == {
        x[0] for x in TIER_DEPTH.values()}
    assert all(x["delivery_mode"] == "PRODUCT_ADVISORY_CONTRACT_ONLY"
               for x in out["products"])


def test_all_eight_families_map_to_distinct_product_outcomes():
    rows = [dict(product_code="test_" + family,
                 product_name="Test " + family, product_family=family,
                 active=True, binding_terms_ready=False) for family in LANES]
    # The flagship lane requires only approved product codes.
    for item in rows:
        if item["product_family"] == "predictive_revenue":
            item["product_code"] = "predictive_revenue_command_center"
    out = build_catalogue_intelligence_contracts(catalog(rows))
    assert len({x["outcome_to_calibrate_against"] for x in out["products"]}) == 8


@pytest.mark.parametrize("change", [
    lambda c: c.update(schema_version="other"),
    lambda c: c.update(product_count=2),
    lambda c: c.update(product_count=True),
    lambda c: c.update(binding_terms_ready_count=0),
    lambda c: c["products"].append(deepcopy(c["products"][0])),
    lambda c: c["products"][0].update(binding_terms_ready="true"),
    lambda c: c["products"][0].update(active=1),
    lambda c: c["products"][0].update(product_family="unverified"),
    lambda c: c["products"][0].update(product_code="not / safe"),
    lambda c: c["products"][2].update(product_family="property"),
    lambda c: c["products"][0].update(product_code="predictive_revenue_intelligence_os"),
])
def test_invalid_catalogue_holds_instead_of_skipping_untrusted_products(change):
    test = catalog()
    change(test)
    with pytest.raises(ProductContractHold):
        build_catalogue_intelligence_contracts(test)


def test_empty_catalogue_keeps_unknown_outcomes_not_zeroes():
    out = build_catalogue_intelligence_contracts(catalog([]))
    assert out["product_count"] == 0
    assert out["tenant_customer_evidence_verified"] is False
    assert out["products"] == []


def test_never_promotes_claims_from_untrusted_input():
    c = catalog()
    c["execution_authority"] = "funds"
    c["actual_revenue"] = True
    c["products"][0].update(prediction_value=999999,
                            original_outcome_verified=True,
                            payment_authorized=True,
                            fulfilment_available_verified=True)
    out = build_catalogue_intelligence_contracts(c)
    assert "999999" not in json.dumps(out)
    assert out["execution_authority"] == "none"
    assert all(x["payment_authorized"] is False and
               x["fulfilment_available_verified"] is False
               for x in out["products"])
