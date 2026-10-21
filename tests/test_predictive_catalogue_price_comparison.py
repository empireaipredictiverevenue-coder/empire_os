"""Every catalogued SKU appears in comparison; unknown cost never becomes ROI."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from empire_os.predictive_catalogue_price_comparison import (
    CataloguePricingHold, review_catalogue_price_comparison,
)
from empire_os.predictive_revenue_products import PREDICTIVE_REVENUE_PRODUCTS

CATALOGUE = Path("/srv/empire_os/runtime/commercial_catalog/latest.json")


def original_catalogue():
    return json.loads(CATALOGUE.read_text())


def test_real_catalogue_all_86_skus_and_all_six_currencies_preserved():
    original = original_catalogue()
    copy = deepcopy(original)
    out = review_catalogue_price_comparison(original)
    assert original == copy
    assert out["catalogue_product_count"] == original["product_count"] == 86
    assert out["founder_approved_flagship_prices_count"] == 5
    assert out["catalogue_prices_unknown"] == 25
    assert out["catalogue_prices_observed_not_authenticated"] == 61
    assert len(out["family_counts"]) == 8
    assert out["astra_gpt6_independent_review"] == "NOT_EXECUTED"
    assert out["execution_authority"] == "none"
    assert out["price_change_authority"] == "none"
    assert out["database_writes"] is False
    assert out["outbound_sent"] is False
    assert {p["catalogue_currency"] for p in out["products"]} == {
        "USD","GBP","EUR","CAD","AUD","NZD"
    }
    mapped = {p["product_code"]: p for p in out["products"]}
    assert len(mapped) == 86
    for row in original["products"]:
        item = mapped[row["product_code"]]
        basis = row.get("price_basis") or {}
        assert item["catalogue_listed_price_minor_units"] == basis.get("amount_cents")
        assert item["catalogue_currency"] == (basis.get("currency") or row.get("currency"))
        assert item["catalogue_unit"] == basis.get("unit")
        assert item["foreign_currency_converted_to_usd"] is False
        assert item["evidence_backed_price_justified"] is False
        assert item["economic_delivery_cost_verified"] is False
        assert item["customer_value_independently_measured"] is False
        assert item["automatic_price_changes_authorized"] is False
        assert item["external_sales_or_pricing_published"] is False
        assert len(item["competitor_categories"]) == 6
    for tier in PREDICTIVE_REVENUE_PRODUCTS:
        item=mapped[tier.product_code]
        assert item["catalogue_listed_price_minor_units"] == tier.deployment_price_cents
        assert item["founder_flagship_price_approved"] is True


@pytest.mark.parametrize("case", ("negative_price","conflict_currency","tampered_flagship","unknown_family","extra_product"))
def test_tampered_catalogue_and_unapproved_price_held(case):
    original = original_catalogue()
    altered=deepcopy(original)
    if case == "negative_price":
        altered["products"][0]["price_basis"]["amount_cents"]=-1
    elif case == "conflict_currency":
        altered["products"][0]["price_basis"]["currency"]="AUD"
    elif case == "tampered_flagship":
        row=next(r for r in altered["products"] if r["product_code"]=="predictive_revenue_diagnostic")
        row["price_basis"]["amount_cents"]=30_000_00
    elif case == "unknown_family":
        altered["products"][0]["product_family"]="new_unknown"
    elif case == "extra_product":
        altered["products"].append(dict(altered["products"][0]))
        altered["product_count"]+=1
    with pytest.raises(CataloguePricingHold):
        review_catalogue_price_comparison(altered)
