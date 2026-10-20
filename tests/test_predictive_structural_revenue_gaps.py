"""Precisely separate modeled gap mechanisms from authenticated lost revenue."""
from copy import deepcopy
import json

import pytest

from test_predictive_market_economic_twin import NOW, market
from test_predictive_profitability_playbooks import pilot,plan
from empire_os.predictive_structural_revenue_gaps import (
    review_structural_market_revenue_gaps,
)
from empire_os.predictive_market_economic_twin import review_market_economic_twin


def candidate(name="capacity_repair",cause="capacity_constraint",kind="labor_capacity",**kwargs):
    x={
        "case_key":name,
        "suspected_cause":cause,
        "driver_type":kind,
        "hypothesis_ref":"unverified_cost_and_demand_case",
        "estimated_days_to_effect_unverified":12,
        "assumed_one_off_cash_cost_minor":30000,
        "demand_multiplier":1,
        "capacity_multiplier":1.2,
        "price_multiplier":1,
        "conversion_multiplier":1,
        "acquisition_cost_multiplier":1,
        "fulfilment_cost_multiplier":1,
        "refund_rate_delta":0,
    }
    x.update(kwargs)
    return x


def rows():
    return [
        candidate(),
        candidate("reduce_materials","cost_pressure","material_cost",
                  capacity_multiplier=1,fulfilment_cost_multiplier=0.82,
                  assumed_one_off_cash_cost_minor=10000),
        candidate("increase_conversions","conversion_friction","consumer_preference",
                  capacity_multiplier=1,conversion_multiplier=1.12,
                  assumed_one_off_cash_cost_minor=15000),
        candidate("slower_new_channel","demand_acquisition","channel_distribution",
                  estimated_days_to_effect_unverified=70,capacity_multiplier=1,
                  demand_multiplier=1.2,
                  assumed_one_off_cash_cost_minor=20000),
    ]


def review(data=None,m=None,p=None,e=None):
    p=p or pilot()
    return review_structural_market_revenue_gaps(
        p,e if e is not None else plan(p),
        m if m is not None else market(),
        data if data is not None else rows(),as_of=NOW,
    )


def keyed(out):
    return {x["case_key"]:x for x in out["intervention_research_comparisons"]}


def test_structural_profit_cash_and_time_comparisons_from_existing_engine():
    out=review()
    assert out["status"]=="STRUCTURAL_MARKET_GAP_HYPOTHESIS_REVIEWED"
    assert out["intervention_count"]==4
    assert out["assumptions_are_real_market_evidence"] is False
    assert out["baseline_hypothetical_unserved_attempts"]==0
    assert out["original_economic_horizon_days"]==30
    assert out["estimated_market_revenue_gap_minor"] is None
    assert out["authenticated_potential_recoverable_revenue_minor"] is None
    assert out["root_causes_authenticated"] is False
    x=keyed(out)
    assert x["reduce_materials"]["hypothetical_incremental_operating_profit_net_of_one_off_cost_minor"]>0
    assert x["slower_new_channel"]["intervention_verdict"]=="RESEARCH_TIMING_BEYOND_ECONOMIC_HORIZON"
    assert x["increase_conversions"]["time_to_value_measured"] is False
    assert x["increase_conversions"]["gap_repair_profitability_proven"] is False
    assert out["decision_policy_authority_granted"] is False
    assert out["original_quant_forecast_registered"] is False
    assert out["database_writes"] is False
    assert out["outbound_sent"] is False


def test_original_economic_profit_delta_equals_twin_less_distinct_explicit_cost():
    p=pilot()
    e=plan(p)
    m=market()
    c=candidate("new_capacity","capacity_constraint","labor_capacity",
                assumed_one_off_cash_cost_minor=25000)
    out=review([c],p=p,e=e,m=m)
    x=keyed(out)["new_capacity"]
    original={
        "driver_key":c["case_key"],
        "driver_type":c["driver_type"],
        "assumption_status":"HYPOTHETICAL_UNCALIBRATED",
        "hypothesis_ref":c["hypothesis_ref"],
        **{k:c[k] for k in (
            "demand_multiplier","capacity_multiplier","price_multiplier",
            "conversion_multiplier","acquisition_cost_multiplier",
            "fulfilment_cost_multiplier","refund_rate_delta"
        )}
    }
    twin=review_market_economic_twin(p,e,m,[original],as_of=NOW)
    original_out=twin["driver_scenarios"][0]
    assert x["hypothetical_incremental_operating_profit_net_of_one_off_cost_minor"]==round(
        original_out["hypothetical_weighted_profit_delta_minor"]-25000,4)
    assert x["hypothetical_pre_collection_cash_exposure_including_one_off_minor"]==round(
        original_out["hypothetical_cash_stress_minor"]+25000,4)


def test_scarcity_is_counted_in_eligible_attempts_not_lost_sales():
    m=market()
    m["demand_units"]=1400
    m["capacity_units"]=1000
    out=review(m=m)
    assert out["baseline_hypothetical_unserved_attempts"]==400
    assert out["gap_diagnostics"][0]["hypothetical_gap_units"]==400
    assert out["gap_diagnostics"][0]["gap_units_are_actual_lost_sales"] is False
    assert out["gap_diagnostics"][0]["root_cause_established"] is False
    assert out["intervention_research_comparisons"][0]["simulated_unserved_eligible_attempts_not_lost_sales"]>=0
    assert out["estimated_market_revenue_gap_minor"] is None


def test_expensive_extra_work_can_be_loss_despite_higher_gross_activity():
    p=pilot();m=market();e=plan(p)
    x=candidate("expensive_sales","demand_acquisition","channel_distribution",
                assumed_one_off_cash_cost_minor=800000,
                capacity_multiplier=1,
                demand_multiplier=1.1)
    r=review([x],p=p,e=e,m=m)
    y=keyed(r)["expensive_sales"]
    assert y["hypothetical_incremental_operating_profit_net_of_one_off_cost_minor"]<0
    assert y["cash_exposure_exceeds_original_assumed_limit"] is True
    assert y["intervention_verdict"]=="RESEARCH_CASH_LIMIT_UNDER_ASSUMPTIONS"
    assert y["root_cause_independently_authenticated"] is False


def test_original_horizon_vs_unsupported_sales_speed_is_explicit():
    x=candidate("two_month_launch",estimated_days_to_effect_unverified=65)
    out=review([x])
    row=keyed(out)["two_month_launch"]
    assert row["timely_within_original_horizon_under_assumptions"] is False
    assert row["intervention_verdict"]=="RESEARCH_TIMING_BEYOND_ECONOMIC_HORIZON"


def test_no_hidden_demand_funnel_denominator_or_fake_probability():
    x=review()
    gap=x["gap_diagnostics"][-1]
    assert gap["observed_funnel_conversion_denominator"] is None
    assert gap["authenticated_market_purchase_or_service_units"] is None
    assert gap["observed_industry_total_addressable_gap_minor"] is None
    assert gap["causally_attributed_revenue_leak_minor"] is None
    assert x["hypothetical_case_weights_are_calibrated_probabilities"] is False
    assert x["measured_incremental_operating_profit_minor"] is None
    assert all(y["published_value_of_information_minor"] is None for y in x["intervention_research_comparisons"])


@pytest.mark.parametrize("which,value",[
    ("assumed_one_off_cash_cost_minor",True),
    ("assumed_one_off_cash_cost_minor",-1),
    ("assumed_one_off_cash_cost_minor",10**11),
    ("estimated_days_to_effect_unverified",0),
    ("estimated_days_to_effect_unverified",181),
    ("estimated_days_to_effect_unverified",1.1),
    ("demand_multiplier",True),
    ("demand_multiplier",float("nan")),
    ("demand_multiplier",6),
    ("capacity_multiplier",-0.2),
    ("price_multiplier",float("inf")),
    ("conversion_multiplier","1.2"),
    ("fulfilment_cost_multiplier",-1),
    ("acquisition_cost_multiplier",float("nan")),
    ("refund_rate_delta",1.1),
    ("refund_rate_delta",True),
    ("suspected_cause","PROVEN_CAUSAL_EFFECT"),
    ("driver_type","unknown_gap_solver"),
    ("case_key","customer@email.com"),
    ("hypothesis_ref","PII:buyer@example.com"),
])
def test_invalid_financial_time_causal_or_numeric_inputs_hold(which,value):
    c=candidate()
    c[which]=value
    with pytest.raises(ValueError):
        review([c])


def test_wrong_driver_for_cause_is_not_an_explanation():
    c=candidate("price_case","price_pressure","labor_capacity")
    with pytest.raises(ValueError):
        review([c])


def test_duplicate_interventions_and_unknown_fields_rejected():
    c=candidate()
    with pytest.raises(ValueError):
        review([c,deepcopy(c)])
    c["automatic_publish"]=True
    with pytest.raises(ValueError):
        review([c])


def test_cross_market_cannot_use_wrong_original_pilot_attempt_cohort():
    m=market()
    m["demand_units"]=500
    m["capacity_units"]=500
    with pytest.raises(ValueError):
        review(m=m)


def test_explicit_source_input_is_clearly_unverified_even_if_profitable():
    x=review([candidate("value_case","cost_pressure","material_cost",
                        capacity_multiplier=1,fulfilment_cost_multiplier=0.6,
                        assumed_one_off_cash_cost_minor=0)])
    row=x["intervention_research_comparisons"][0]
    assert row["hypothetical_incremental_operating_profit_net_of_one_off_cost_minor"]>0
    assert row["gap_repair_profitability_proven"] is False
    assert row["intervention_causally_tested"] is False
    assert row["time_to_value_measured"] is False


def test_no_private_customer_pii_or_original_stories_in_diagnostics():
    out=review()
    raw=json.dumps(out)
    assert "example.com" not in raw
    assert "private_street" not in raw
    assert out["live_campaign_or_website_changed"] is False
