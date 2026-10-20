"""Market Digital Twin -> economic scenario recomputation; synthetic only."""
from datetime import timedelta
import json

import pytest

from test_predictive_profitability_playbooks import NOW, pilot, plan
from empire_os.predictive_market_economic_twin import review_market_economic_twin


def market():
    return {
        "market_key":"united_states",
        "geography_key":"littlerock_ar",
        "niche_key":"hvac",
        "baseline_at":(NOW-timedelta(minutes=5)).isoformat(),
        "evidence_ref":"synthetic_market_research",
        "assumption_status":"HYPOTHETICAL_UNCALIBRATED",
        "demand_units":1000,"capacity_units":1200,
        "price_per_unit_minor":10000,
        "capacity_rights_verified":False,
    }


def driver(name="storm_rise",type="weather_storm",**values):
    row={
        "driver_key":name,"driver_type":type,
        "assumption_status":"HYPOTHETICAL_UNCALIBRATED",
        "hypothesis_ref":"synthetic_weather_test",
        "demand_multiplier":1.5,
        "capacity_multiplier":1.0,
        "price_multiplier":1.0,
        "conversion_multiplier":1.0,
        "acquisition_cost_multiplier":1.0,
        "fulfilment_cost_multiplier":1.0,
        "refund_rate_delta":0.0,
    }
    row.update(values)
    return row


def review(drivers=None,market_input=None,economic=None):
    p=pilot()
    return review_market_economic_twin(
        p, economic if economic is not None else plan(p),
        market_input if market_input is not None else market(),
        drivers if drivers is not None else [driver()],as_of=NOW,
    )


def test_higher_weather_demand_is_capacity_capped_and_profit_recomputed():
    r=review()
    assert r["status"]=="HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED"
    assert r["scenario_driver_count"]==1
    d=r["driver_scenarios"][0]
    assert d["simulated_demand_units"]==1500
    assert d["simulated_capacity_units"]==1200
    assert d["simulated_eligible_attempts_capacity_capped"]==1200
    assert d["capacity_binding"] is True
    assert d["simulated_purchased_unit_price_minor"]==10000
    assert d["hypothetical_weighted_profit_delta_minor"]>0
    assert d["driver_intervention_is_proven_causal_effect"] is False
    assert r["weather_phenomenon_confirmed"] is False
    assert r["source_market_conditions_authenticated"] is False
    assert r["simulated_served_attempts_are_paid_sales"] is False
    assert r["scenario_profit_is_recognized_revenue"] is False
    assert r["uses_existing_market_digital_twin"] is True
    assert r["uses_existing_profitability_playbook"] is True
    assert r["market_shock_applied_to_production"] is False
    assert r["execution_authority"]=="none"
    assert "synthetic_market_research" not in json.dumps(r)


def test_scarce_labor_capacity_reduces_eligible_cohort_and_profit():
    result=review([driver("labor_shortage","labor_capacity",
        demand_multiplier=1.0,capacity_multiplier=0.25)])
    scenario=result["driver_scenarios"][0]
    assert scenario["simulated_eligible_attempts_capacity_capped"]==300
    assert scenario["capacity_binding"] is True
    assert scenario["hypothetical_weighted_profit_delta_minor"]<0
    assert result["pricing_and_purchasing_terms_verified"] is False


def test_competitor_price_cut_and_material_inflation_recompute_full_books():
    result=review([
        driver("competitor_price_cut","competitor_response",demand_multiplier=1.0,
               price_multiplier=0.8),
        driver("material_cost_rise","material_cost",demand_multiplier=1.0,
               fulfilment_cost_multiplier=1.8),
    ])
    assert {r["driver_type"] for r in result["driver_scenarios"]}=={
        "competitor_response","material_cost",
    }
    assert all(s["hypothetical_weighted_profit_delta_minor"]<0
               for s in result["driver_scenarios"])
    assert result["scenario_driver_count"]==2
    assert result["original_forecast_registered"] is False


def test_zero_demand_yields_negative_cost_not_fake_sales():
    out=review([driver("lost_market","regulatory_change",
                        demand_multiplier=0)])
    scenario=out["driver_scenarios"][0]
    assert scenario["simulated_eligible_attempts_capacity_capped"]==0
    assert scenario["hypothetical_weighted_operating_profit_minor"]<0
    assert out["scenario_profit_is_recognized_revenue"] is False


@pytest.mark.parametrize("field,value",[
    ("demand_multiplier",-1),("capacity_multiplier",True),
    ("price_multiplier",float("inf")),("conversion_multiplier",10),
    ("refund_rate_delta",5),("driver_type","verified_storm"),
    ("assumption_status","CALIBRATED"),("hypothesis_ref","bob@example.org"),
])
def test_invalid_driver_or_fake_evidence_is_blocked(field,value):
    with pytest.raises(ValueError):
        review([driver(**{field:value})])


@pytest.mark.parametrize("field,value",[
    ("market_key","london@example.org"),
    ("capacity_rights_verified",True),
    ("assumption_status","VERIFIED_MARKET"),
    ("baseline_at","2026-10-01T00:00:00+00:00"),
    ("capacity_units",-1),
    ("price_per_unit_minor",0),
    ("demand_units",1.5),
])
def test_market_data_is_hypothetical_and_bounded(field,value):
    bad=market();bad[field]=value
    with pytest.raises(ValueError):
        review(market_input=bad)


def test_original_price_unit_and_pilot_revision_must_match():
    econ=plan()
    econ["scenarios"][0]["unit_price_minor"]=5000
    with pytest.raises(ValueError,match="unit"):
        review(economic=econ)


def test_duplicate_driver_keys_rejected():
    with pytest.raises(ValueError):
        review([driver(),driver()])


def test_geographic_market_has_no_personal_contact_or_outbound():
    outcome=review([driver("price_pressure","competitor_response",
                           price_multiplier=0.9)])
    assert outcome["outbound_sent"] is False
    assert outcome["database_writes"] is False
    assert outcome["company_geographic_eligibility_verified"] is False
    assert outcome["pricing_and_purchasing_terms_verified"] is False


def test_baseline_capacity_and_economic_attempts_must_represent_same_cohort():
    mismatch=market()
    mismatch["demand_units"]=900
    with pytest.raises(ValueError, match="attempt cohort"):
        review(market_input=mismatch)


def test_conversion_above_probability_one_is_held_not_clamped():
    econ=plan()
    econ["scenarios"][2]["conversion_rate"]=0.21
    with pytest.raises(ValueError,match="probability one"):
        review([driver("impossible_conversion","consumer_preference",
                       conversion_multiplier=5.0)],economic=econ)
