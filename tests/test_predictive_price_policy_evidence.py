"""Cost ceilings are budget scenarios, never observed gross profit."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import pytest

from empire_os.predictive_price_policy_evidence import (
    PricingPolicyHold, review_price_policy_ceiling,
)
from empire_os.predictive_catalogue_price_comparison import (
    CataloguePricingHold, review_catalogue_price_comparison,
)

SOURCE = Path("/srv/empire_os/runtime/commercial_catalog/latest.json")


def original():
    return json.loads(SOURCE.read_text())


def sku(code):
    return deepcopy(next(x for x in original()["products"] if x["product_code"] == code))


def test_all_original_founder_ceilings_pass_without_claiming_actual_margin():
    catalogue=original()
    reviewed=[review_price_policy_ceiling(p) for p in catalogue["products"]]
    assert sum(x["policy_ceiling_scenario_available"] for x in reviewed) == 26
    assert sum(x["policy_ceiling_passes"] is True for x in reviewed) == 26
    assert sum(x["policy_ceiling_passes"] is None for x in reviewed) == 60
    assert all(x["realized_margin_verified"] is False for x in reviewed)
    assert all(x["price_justified_by_evidence"] is False for x in reviewed)
    assert all(x["customer_value_verified"] is False for x in reviewed)
    assert all(x["execution_authority"]=="none" for x in reviewed)


def test_dated_regional_local_price_uses_same_currency_and_unit():
    p=sku("solar_opportunity_map_gb")
    output=review_price_policy_ceiling(p)
    assert output["currency"]=="GBP"
    assert output["unit"]=="per_map"
    assert output["maximum_policy_cost_minor_units"] == 9960
    assert output["listed_price_minor_units"] == 24900
    assert output["policy_ceiling_case_contribution_minor_units"] == 14940
    assert output["policy_ceiling_case_margin_bps"] == 6000
    assert output["policy_required_margin_bps"] == 5500
    assert output["policy_ceiling_passes"] is True


def test_founder_policy_reference_cost_scenario_not_actual():
    p=sku("authority_intelligence")
    result=review_price_policy_ceiling(p)
    assert result["policy_ceiling_passes"] is True
    assert result["listed_price_minor_units"] == 14900
    assert result["maximum_policy_cost_minor_units"] == 3500
    assert result["policy_ceiling_case_contribution_minor_units"] == 11400
    assert result["policy_required_margin_bps"]==6500
    assert result["source_policy_verified_as_actual_cost"] is False
    assert "payment_processing_and_refunds_unless_in_original_caps" in result["scenario_exclusions"]


@pytest.mark.parametrize("kind",[
    "currency", "unit", "reference", "observed_actual", "boolean_cost",
    "margin_policy", "price_source", "dated_cost_flag",
    "dated_inflated_amount", "dated_wrong_policy_date",
])
def test_tampered_policy_fails_closed(kind):
    p=sku("authority_intelligence")
    if kind=="currency":
        p["fulfilment_cost_basis"]["currency"]="GBP"
    elif kind=="unit":
        p["acquisition_cost_basis"]["unit"]="per_report"
    elif kind=="reference":
        p["acquisition_cost_basis"]["approval_reference"]="another"
    elif kind=="observed_actual":
        p["fulfilment_cost_basis"]["observed_actual"]=True
    elif kind=="boolean_cost":
        p["acquisition_cost_basis"]["amount_cents"]=True
    elif kind=="margin_policy":
        p["margin_policy"]["basis_type"]="unknown"
    elif kind=="price_source":
        p["price_basis"]["source_type"]="scraper"
    elif kind=="dated_cost_flag":
        p=sku("solar_opportunity_map_gb")
        p["acquisition_cost_basis"]["observed_cost_claim"]=True
    elif kind=="dated_inflated_amount":
        p=sku("solar_opportunity_map_gb")
        p["acquisition_cost_basis"]["amount_cents"]=20000
    elif kind=="dated_wrong_policy_date":
        p=sku("solar_opportunity_map_gb")
        p["margin_policy"]["approval_date"]="2026-07-23"
    with pytest.raises(PricingPolicyHold):
        review_price_policy_ceiling(p)


def test_policy_margin_shortfall_reports_not_a_price_authorization():
    p=sku("authority_intelligence")
    p["margin_policy"]["minimum_margin_bps"]=9000
    result=review_price_policy_ceiling(p)
    assert result["policy_ceiling_passes"] is False
    assert result["headroom_above_minimum_margin_minor_units"]<0
    assert result["price_justified_by_evidence"] is False
    assert result["execution_authority"]=="none"


def test_catalogue_review_preserves_original_prices_and_adds_budget_scoping():
    original_doc=original()
    before=deepcopy(original_doc)
    outcome=review_catalogue_price_comparison(original_doc)
    assert original_doc==before
    assert outcome["catalogue_product_count"]==86
    assert outcome["approved_cost_ceiling_scenarios_available"]==26
    assert outcome["approved_ceiling_scenarios_meeting_margin"]==26
    assert outcome["approved_ceiling_scenarios_below_margin"]==0
    assert outcome["approved_cost_ceiling_scenario_is_actual_margin"] is False
    assert outcome["price_change_authority"]=="none"
    assert outcome["astra_gpt6_independent_review"]=="NOT_EXECUTED"
    assert all(not p["founder_policy_cost_ceiling_scenario"]["realized_margin_verified"] for p in outcome["products"])


def test_catalogue_fails_closed_if_one_original_policy_cost_or_margin_is_forged():
    doc=original()
    candidate=next(p for p in doc["products"] if p["product_code"]=="authority_intelligence")
    candidate["fulfilment_cost_basis"]["currency"]="AUD"
    with pytest.raises(CataloguePricingHold):
        review_catalogue_price_comparison(doc)
