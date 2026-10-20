"""Multi-index economic risk scenarios are experiments, not observed margins."""
from copy import deepcopy
import json

import pytest

from test_predictive_bls_cost_index import owner as bls_owner
from test_predictive_market_economic_twin import (
    market, NOW, driver,
)
from test_predictive_profitability_playbooks import pilot,plan
from empire_os.predictive_bls_cost_index import review_bls_cost_index_owner
from empire_os.predictive_multi_index_economics import (
    review_multi_index_cost_pressure,
)
from empire_os.predictive_market_economic_twin import review_market_economic_twin

SECOND="PCU111111111111"


def reviewed(*,two=False):
    original=bls_owner()
    original["generated_at"]=NOW.isoformat()
    if two:
        m=deepcopy(original["approved_series_manifest"][0])
        m["series_id"]=SECOND
        original["approved_series_manifest"].append(m)
        original["bls_api_response"]["Results"]["series"].append({
            "seriesID":SECOND,
            "data":[
                {"year":"2026","period":"M08","value":"105","footnotes":[]},
                {"year":"2025","period":"M08","value":"100","footnotes":[]},
            ],
        })
    out=review_bls_cost_index_owner(original,as_of=NOW)
    assert out["status"]=="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"
    return out


def basket(*,two=False):
    first=reviewed()["series_research_cards"][0]["original_public_series_id"]
    result=[{
        "series_id":first,
        "assumed_input_cost_share":0.4,
        "assumed_index_to_cost_translation_fraction":0.75,
    }]
    if two:
        result.append({
            "series_id":SECOND,
            "assumed_input_cost_share":0.1,
            "assumed_index_to_cost_translation_fraction":1,
        })
    return result


def cases():
    return [
        {"case_key":"no_index_change","assumed_index_change_scale":0,
         "assumed_capacity_multiplier":1,"assumed_demand_multiplier":1,
         "assumed_price_multiplier":1},
        {"case_key":"source_movement","assumed_index_change_scale":1,
         "assumed_capacity_multiplier":1,"assumed_demand_multiplier":1,
         "assumed_price_multiplier":1},
        {"case_key":"high_cost_plus_capacity","assumed_index_change_scale":2,
         "assumed_capacity_multiplier":0.65,"assumed_demand_multiplier":1,
         "assumed_price_multiplier":0.95},
    ]


def evaluate(*,source=None,cost_basket=None,scenario_cases=None,geo=None):
    p=pilot()
    return review_multi_index_cost_pressure(
        source if source is not None else reviewed(),
        p,plan(p),geo if geo is not None else market(),
        cost_basket=cost_basket if cost_basket is not None else basket(),
        scenario_cases=scenario_cases if scenario_cases is not None else cases(),
        as_of=NOW,
    )


def output_by_case(out):
    return {r["case_key"]:r for r in out["hypothetical_scenario_outcomes"]}


def test_multi_case_cost_shocks_go_through_existing_full_profit_twin():
    original=evaluate()
    assert original["status"]=="MULTI_INDEX_HYPOTHETICAL_ECONOMIC_RISK_REVIEWED"
    assert original["scenario_count"]==3
    assert original["source_revision_sha256"]==reviewed()["source_revision_sha256"]
    assert original["assumed_total_cost_exposure_share"]==0.4
    assert original["currency_and_actual_costs_verified"] is False
    scenarios=output_by_case(original)
    assert scenarios["no_index_change"]["assumed_composite_fulfilment_cost_multiplier"]==1
    assert scenarios["source_movement"]["assumed_composite_fulfilment_cost_multiplier"]==1.03
    assert scenarios["high_cost_plus_capacity"]["assumed_composite_fulfilment_cost_multiplier"]==1.06
    assert (scenarios["source_movement"]["hypothetical_expected_operating_profit_minor"]
            <scenarios["no_index_change"]["hypothetical_expected_operating_profit_minor"])
    assert (scenarios["high_cost_plus_capacity"]["hypothetical_expected_operating_profit_minor"]
            <scenarios["source_movement"]["hypothetical_expected_operating_profit_minor"])
    assert original["largest_stressed_profit_loss_case"]=="high_cost_plus_capacity"
    assert original["hypothetical_profit_dispersion_minor"]>0
    assert original["calibrated_likelihood_of_loss"] is None
    assert original["realized_customer_gross_profit_minor"] is None
    assert original["original_forecast_registered"] is False
    assert original["scenario_executed"] is False
    assert original["database_writes"] is False
    assert original["execution_authority"]=="none"


def test_two_indices_cost_basket_avoids_doubling_full_material_cost_base():
    out=evaluate(source=reviewed(two=True),cost_basket=basket(two=True))
    r=output_by_case(out)
    assert out["assumed_total_cost_exposure_share"]==0.5
    assert r["source_movement"]["assumed_composite_fulfilment_cost_multiplier"]==1.035
    assert r["high_cost_plus_capacity"]["assumed_composite_fulfilment_cost_multiplier"]==1.07
    assert out["cost_series_overlaps_independently_checked"] is False
    assert out["source_to_actual_job_cost_mapping_authenticated"] is False


def test_original_economic_twin_engine_profit_is_reused_not_recomputed_loosely():
    out=evaluate()
    p=pilot()
    d=driver("source_movement","material_cost",
             demand_multiplier=1,capacity_multiplier=1,price_multiplier=1,
             fulfilment_cost_multiplier=1.03)
    t=review_market_economic_twin(p,plan(p),market(),[d],as_of=NOW)
    assert output_by_case(out)["source_movement"]["hypothetical_expected_operating_profit_minor"]==(
        t["driver_scenarios"][0]["hypothetical_weighted_operating_profit_minor"]
    )


def test_unknown_currency_geo_cannot_use_us_national_series():
    m=market()
    m["market_key"]="united_kingdom"
    with pytest.raises(ValueError):
        evaluate(geo=m)


@pytest.mark.parametrize("field,value",[
    ("assumed_input_cost_share",True),
    ("assumed_input_cost_share",1.1),
    ("assumed_input_cost_share",-0.1),
    ("assumed_input_cost_share",float("nan")),
    ("assumed_index_to_cost_translation_fraction","0.5"),
    ("assumed_index_to_cost_translation_fraction",float("inf")),
])
def test_basket_exposure_and_assumption_values_must_be_bounded(field,value):
    rows=basket()
    rows[0][field]=value
    with pytest.raises(ValueError):
        evaluate(cost_basket=rows)


def test_disallow_shares_over_100_percent_or_duplicate_ppi_series():
    items=basket(two=True)
    items[0]["assumed_input_cost_share"]=0.95
    items[1]["assumed_input_cost_share"]=0.25
    with pytest.raises(ValueError):
        evaluate(source=reviewed(two=True),cost_basket=items)
    rows=basket()
    with pytest.raises(ValueError):
        evaluate(cost_basket=rows*2)


@pytest.mark.parametrize("field,value",[
    ("assumed_index_change_scale",True),
    ("assumed_index_change_scale",3.5),
    ("assumed_index_change_scale",-0.1),
    ("assumed_index_change_scale",float("inf")),
    ("assumed_capacity_multiplier",float("nan")),
    ("assumed_demand_multiplier",4),
    ("assumed_price_multiplier",-1),
])
def test_scenario_multiplier_requires_explicit_bounded_experiment(field,value):
    inputs=cases()
    inputs[1][field]=value
    with pytest.raises(ValueError):
        evaluate(scenario_cases=inputs)


def test_duplicate_scenarios_or_single_case_are_not_a_risk_range():
    x=cases()
    x[1]["case_key"]=x[0]["case_key"]
    with pytest.raises(ValueError):
        evaluate(scenario_cases=x)
    with pytest.raises(ValueError):
        evaluate(scenario_cases=[cases()[0]])


def test_source_month_yoy_gap_cannot_be_masked_by_assumed_growth():
    source=deepcopy(reviewed())
    source["series_research_cards"][0]["year_over_year_index_change_pct_research_only"]=None
    with pytest.raises(ValueError):
        evaluate(source=source)


def test_wage_index_cannot_be_used_as_material_price_and_workforce():
    source=deepcopy(reviewed())
    source["series_research_cards"][0]["owner_reported_series_role"]="wage_related_index"
    with pytest.raises(ValueError):
        evaluate(source=source)


def test_source_owner_clock_stale_future_or_fake_profit_authority_rejected():
    for field,value in [
        ("owner_source_generated_at","2026-09-01T00:00:00+00:00"),
        ("owner_source_generated_at","2030-01-01T00:00:00+00:00"),
        ("realized_profit_verified",True),
        ("actual_material_or_labor_cost_authenticated",True),
        ("execution_authority","spend"),
    ]:
        source=deepcopy(reviewed())
        source[field]=value
        with pytest.raises(ValueError):
            evaluate(source=source)


def test_extreme_index_shocks_do_not_create_invalid_negative_fulfilment_costs():
    source=deepcopy(reviewed())
    source["series_research_cards"][0]["year_over_year_index_change_pct_research_only"]=-100
    inputs=cases()
    inputs[2]["assumed_index_change_scale"]=3
    row=basket()
    row[0]["assumed_input_cost_share"]=1
    row[0]["assumed_index_to_cost_translation_fraction"]=1
    with pytest.raises(ValueError):
        evaluate(source=source,cost_basket=row,scenario_cases=inputs)


def test_uses_no_customer_identifiers_or_paying_buyer_claims():
    out=evaluate()
    raw=json.dumps(out)
    assert "example.org" not in raw
    assert out["genuine_purchases_from_cost_signal"] is None
    assert out["scenario_outcomes_entered_into_economic_memory"] is False
    assert out["new_commercial_or_marketing_playbook_authorized"] is False
