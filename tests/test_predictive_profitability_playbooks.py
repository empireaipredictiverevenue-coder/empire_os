"""Predictive Profitability / scenarios / playbooks on original pilot revision.

Synthetic explicit assumption cases; no live currency, buyer price, ROI,
contract, registered forecast or actual gross profit ever inferred.
"""
from copy import deepcopy
from datetime import timedelta
from math import ceil
import json
import pytest

from test_predictive_customer_value_pilot_preflight import NOW, source, design
from empire_os.predictive_customer_value_pilot_preflight import review_prospective_customer_value_pilot
from empire_os.predictive_profitability_playbooks import (
    review_profitability_playbook, build_profitability_scenario_portfolio,
)


def pilot():
    bridge=source()
    return review_prospective_customer_value_pilot(bridge,design(bridge),as_of=NOW)


def row(name,p=.10,refund=.10,price=10000,attempts=1000,kind="service",ccy="USD"):
    return {
        "scenario_key":name,"weight":{"downside":0.25,"base":0.50,"upside":0.25}[name],
        "assumption_status":"HYPOTHETICAL_UNCALIBRATED",
        "assumption_ref":"research_hypothesis_"+name,
        "currency":ccy,"product_type":kind,
        "unit_price_minor":price,
        "qualified_attempts":attempts,
        "conversion_rate":p,"refund_rate":refund,"paid_cycles":1,
        "paid_cycle_retention_rate":1.0,"paid_cycle_period_days":7,
        "fulfilment_cost_per_paid_cycle_minor":2500,
        "payment_fee_per_paid_cycle_minor":300,
        "acquisition_cost_per_attempt_minor":250,
        "fixed_pilot_cost_minor":50000,
        "operating_overhead_minor":20000,
        "cash_collection_lag_days":15,
    }


def plan(pilot_ref=None,kind="service",ccy="USD"):
    p=pilot_ref if pilot_ref is not None else pilot()
    return {
        "opportunity_key":p["opportunity_key"],
        "pilot_design_sha256":p["design_revision_sha256"],
        "economic_horizon_days":30,
        "risk_aversion":0.25,
        "max_cash_exposure_minor":700000,
        "scenarios":[
            row("downside",p=.03,refund=.25,kind=kind,ccy=ccy),
            row("base",p=.10,refund=.10,kind=kind,ccy=ccy),
            row("upside",p=.20,refund=.05,kind=kind,ccy=ccy),
        ],
    }


def review(p=None,x=None):
    pp=p if p is not None else pilot()
    return review_profitability_playbook(pp,x if x is not None else plan(pp),as_of=NOW)


def test_scenario_economics_gross_vs_operating_and_quant_reuse():
    r=review()
    assert r["status"]=="HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY"
    rows={x["scenario_key"]:x for x in r["scenario_rows"]}
    b=rows["base"]
    assert b["expected_paid_customer_equivalents_hypothetical"]==100
    assert b["expected_revenue_minor_hypothetical"]==900000
    assert b["expected_cogs_minor_hypothetical"]==280000
    assert b["expected_gross_profit_minor_hypothetical"]==620000
    assert b["acquisition_spend_minor_hypothetical"]==250000
    assert b["fixed_and_overhead_minor_hypothetical"]==70000
    assert b["expected_operating_profit_minor_hypothetical"]==300000
    assert b["break_even_qualified_attempts_hypothetical"]==190
    assert b["cash_outflow_before_collections_minor_hypothetical"]==600000
    assert rows["downside"]["expected_operating_profit_minor_hypothetical"]==-179000
    assert rows["upside"]["expected_operating_profit_minor_hypothetical"]==1020000
    assert r["hypothetical_weighted_operating_profit_minor"]==360250
    assert r["hypothetical_worst_operating_profit_minor"]==-179000
    assert r["hypothetical_robust_operating_profit_minor"]==225437.5
    assert r["uses_existing_quant_economics"] is True
    assert r["original_forecast_registered"] is False
    assert r["actual_gross_profit_verified"] is False
    assert r["economic_memory_learning_performed"] is False
    assert r["outbound_sent"] is False
    assert r["spend_authorized"] is False
    assert r["scenario_set_exhaustive_or_calibrated"] is False
    assert r["modeled_profit_is_recognized_revenue"] is False


def test_playbooks_are_specific_triggers_not_permissions():
    r=review()
    actions={x["playbook_key"]:x for x in r["playbooks"]}
    assert "VERIFY_FIRST_PAYER" in actions
    assert "REGISTER_PRE_OUTCOME_ECONOMICS" in actions
    assert "LIMIT_DOWNSIDE" in actions
    assert "REPAIR_UNIT_ECONOMICS" in actions
    assert "MEASURE_CUSTOMER_VALUE" in actions
    assert "REASSESS_COMPETITIVE_MARKET" in actions
    assert all(not x["automatic_execution_allowed"] for x in actions.values())
    assert r["playbooks_are_agent_execution_authority"] is False
    x=plan()
    x["max_cash_exposure_minor"]=100
    x["scenarios"][0]["cash_collection_lag_days"]=30
    z=review(x=x)
    assert z["worst_case_cash_exposure_above_assumed_limit"] is True
    names={a["playbook_key"] for a in z["playbooks"]}
    assert {"CAP_CASH_EXPOSURE","PROTECT_CASH_CYCLE"}<=names


def test_zero_conversion_cannot_be_mislabeled_positive_profit():
    x=plan()
    for s in x["scenarios"]:
        s["conversion_rate"]=0.0
    r=review(x=x)
    assert r["hypothetical_weighted_operating_profit_minor"]<0
    assert all(k["expected_revenue_minor_hypothetical"]==0 for k in r["scenario_rows"])
    assert all(k["break_even_qualified_attempts_hypothetical"] is None for k in r["scenario_rows"])
    assert all(k["expected_gross_margin_hypothetical"] is None for k in r["scenario_rows"])


def test_subscription_paid_cycles_are_hypothetical_not_actual_ltv():
    x=plan(kind="app")
    for s in x["scenarios"]:
        s["paid_cycles"]=3
    r=review(x=x)
    assert r["product_type"]=="app"
    assert r["scenario_rows"][1]["expected_revenue_minor_hypothetical"]==2700000
    assert r["scenario_rows"][1]["expected_cogs_minor_hypothetical"]==840000
    assert r["actual_gross_profit_verified"] is False


@pytest.mark.parametrize("product",[
    "product","app","service","data_product","lead","call","appointment", "click", "seat", "subscription", "affiliate",
])
def test_covers_existing_physical_digital_and_performance_products(product):
    assert review(x=plan(kind=product))["product_type"]==product


@pytest.mark.parametrize("mutation",[
    lambda x:x.update(pilot_design_sha256="0"*64),
    lambda x:x.update(opportunity_key="another:opportunity"),
    lambda x:x.update(economic_horizon_days=31),
    lambda x:x.update(economic_horizon_days=True),
    lambda x:x.update(risk_aversion=float("nan")),
    lambda x:x.update(risk_aversion=True),
    lambda x:x["scenarios"][0].update(weight=0.35),
    lambda x:x["scenarios"][0].update(assumption_status="SIGNED_FORECAST"),
    lambda x:x["scenarios"][0].update(unit_price_minor=-1),
    lambda x:x["scenarios"][0].update(refund_rate=1.05),
    lambda x:x["scenarios"][0].update(conversion_rate=True),
    lambda x:x["scenarios"][0].update(qualified_attempts=2.1),
    lambda x:x["scenarios"][0].update(currency="BTC"),
    lambda x:x["scenarios"][0].update(unit_price_minor=float("inf")),
    lambda x:x["scenarios"][0].update(product_type=["service"]),
    lambda x:x["scenarios"][0].update(paid_cycles=0),
    lambda x:x["scenarios"][0].update(paid_cycle_retention_rate=1.5),
    lambda x:x["scenarios"][0].update(paid_cycle_period_days=0),
    lambda x:x["scenarios"][0].update(cash_collection_lag_days=-1),
    lambda x:x["scenarios"][0].update(assumption_ref="contact@example.org"),
])
def test_invalid_or_overconfident_scenario_assumptions_rejected(mutation):
    x=plan()
    mutation(x)
    with pytest.raises((ValueError,TypeError)):
        review(x=x)


def test_ranking_must_be_ordered_and_no_automatic_probability_normalization():
    x=plan()
    x["scenarios"][0]["conversion_rate"]=0.35
    with pytest.raises(ValueError,match="ordered"):
        review(x=x)
    x=plan()
    x["scenarios"][1]["weight"]=0.60
    with pytest.raises(ValueError,match="sum to one"):
        review(x=x)


def test_scenarios_cannot_rebrand_a_forecast_preflight_as_registered():
    p=pilot()
    x=plan(p)
    p["original_quant_forecast_registered"]=True
    with pytest.raises(ValueError):
        review(p,x)


def test_portfolio_reuses_canonical_optimizer_with_net_profit_and_cash_budget():
    a=review()
    p=pilot()
    pp=plan(p)
    pp["opportunity_key"]="community_pain:search_visibility"
    # Construct separately real linked opportunity from the second radar card
    bridge=source()
    original=design(bridge)
    card=bridge["research_cards"][1]
    original.update(
        opportunity_key=card["opportunity_key"],
        source_revision_fingerprint=card["source_revision_fingerprint"],
        primary_measure=card["proposed_primary_value_metric"],
        commercial_measure=card["proposed_commercial_validation_metric"],
    )
    other_pilot=review_prospective_customer_value_pilot(bridge,original,as_of=NOW)
    b=review(other_pilot,plan(other_pilot))
    outcome=build_profitability_scenario_portfolio(
        [a,b],budget_minor=6_240_000,risk_aversion=0.25,
        capacity_by_group={"commercial_delivery":1},
    )
    assert outcome["execution_authority"]=="none"
    assert outcome["scenario_values_already_net_operating_costs"] is True
    assert outcome["scenario_probabilities_calibrated"] is False
    assert outcome["capital_approval_granted"] is False
    assert outcome["spend_execution"] is False
    assert outcome["recognized_gross_profit"] is False
    assert len(outcome["scenario_context"]["scenarios"])==3


def test_portfolio_blocks_insufficient_cash_limit_instead_of_overriding_governor():
    r=review()
    output=build_profitability_scenario_portfolio(
        [r],budget_minor=100,risk_aversion=0.5,
        capacity_by_group={"commercial_delivery":1},
    )
    assert output["execution_authority"]=="none"
    assert output["status"]=="UNAVAILABLE"
    assert output["reason"]=="no_evidence_complete_actions"


@pytest.mark.parametrize("bad",[
    {"risk_aversion":1.1},
    {"budget_minor":True},
    {"capacity_by_group":{"commercial_delivery":True}},
    {"capacity_by_group":{}},
])
def test_portfolio_does_not_invent_approval_or_capacity(bad):
    args={
        "books":[review()],
        "budget_minor":1_000_000,
        "risk_aversion":0.5,
        "capacity_by_group":{"commercial_delivery":1},
    }
    args.update(bad)
    with pytest.raises(ValueError):
        build_profitability_scenario_portfolio(**args)


def test_renewal_retention_decay_changes_expected_ltv_and_margin_without_fake_subscribers():
    x=plan(kind="app")
    for item in x["scenarios"]:
        item["paid_cycles"]=3
        item["paid_cycle_retention_rate"]=0.8
    r=review(x=x)
    base=r["scenario_rows"][1]
    assert base["expected_paid_cycles_per_customer_hypothetical"]==2.44
    assert base["expected_revenue_minor_hypothetical"]==2196000
    assert base["expected_cogs_minor_hypothetical"]==683200
    assert base["customer_acquisition_cost_per_conversion_minor_hypothetical"]==2500
    assert base["actual_gross_profit_verified"] if False else r["actual_gross_profit_verified"] is False


def test_all_conversions_cash_stress_is_stricter_than_expected_cost():
    r=review()
    base=r["scenario_rows"][1]
    assert base["cash_outflow_before_collections_minor_hypothetical"]==600000
    assert base["all_conversions_before_collections_stress_cash_minor_hypothetical"]==3120000
    assert r["hypothetical_max_cash_outflow_before_collection_minor"]==3120000
    assert r["cash_upper_bound_assumes_all_attempts_convert_before_any_collection"] is True
    assert r["worst_case_cash_exposure_above_assumed_limit"] is True


def test_quant_value_of_information_is_hypothetical_and_not_research_approval():
    from empire_os.predictive_profitability_playbooks import review_profitability_research_value
    b=review()
    out=review_profitability_research_value(
        b,improved_operating_profit_minor_hypothesis=b["hypothetical_robust_operating_profit_minor"]+50000,
        research_cost_minor_hypothesis=1000,
        probability_research_changes_decision_hypothesis=0.5,
    )
    assert out["research_net_information_value_minor_hypothetical"]==24000
    assert out["research_worth_exploring_hypothetical"] is True
    assert out["uses_existing_quant_value_of_information"] is True
    assert out["research_probability_calibrated"] is False
    assert out["budget_or_research_execution_authorized"] is False
    assert out["verified_profit_or_conversions"] is False
    assert out["execution_authority"]=="none"


def test_negative_information_value_recommends_not_spending_even_on_hypothetical_upsides():
    from empire_os.predictive_profitability_playbooks import review_profitability_research_value
    b=review()
    out=review_profitability_research_value(
        b,improved_operating_profit_minor_hypothesis=b["hypothetical_robust_operating_profit_minor"]+200,
        research_cost_minor_hypothesis=1000,
        probability_research_changes_decision_hypothesis=0.5,
    )
    assert out["research_net_information_value_minor_hypothetical"]==-900
    assert out["research_worth_exploring_hypothetical"] is False


@pytest.mark.parametrize("bad",[
    {"probability_research_changes_decision_hypothesis":float("nan")},
    {"probability_research_changes_decision_hypothesis":1.5},
    {"probability_research_changes_decision_hypothesis":True},
    {"research_cost_minor_hypothesis":-1},
    {"research_cost_minor_hypothesis":None},
    {"improved_operating_profit_minor_hypothesis":None},
])
def test_value_of_information_unsupported_inputs_fail(bad):
    from empire_os.predictive_profitability_playbooks import review_profitability_research_value
    args={
        "book":review(),
        "improved_operating_profit_minor_hypothesis":250000,
        "research_cost_minor_hypothesis":1000,
        "probability_research_changes_decision_hypothesis":0.5,
    }
    args.update(bad)
    with pytest.raises(ValueError):
        review_profitability_research_value(**args)


def test_one_factor_sensitivity_recalculates_profit_and_preserves_noncausal_status():
    from empire_os.predictive_profitability_playbooks import review_profitability_sensitivities
    p=pilot(); x=plan(p)
    z=review_profitability_sensitivities(p,x,[
        {"shock_key":"price_cut", "field":"unit_price_minor",
         "proposed_value":9000,"assumption_status":"HYPOTHETICAL_UNCALIBRATED"},
        {"shock_key":"worse_cac","field":"acquisition_cost_per_attempt_minor",
         "proposed_value":500,"assumption_status":"HYPOTHETICAL_UNCALIBRATED"},
        {"shock_key":"refund_rise","field":"refund_rate",
         "proposed_value":0.40,"assumption_status":"HYPOTHETICAL_UNCALIBRATED"},
    ],as_of=NOW)
    assert z["status"]=="INDEPENDENT_WHAT_IF_RECOMPUTATIONS_ONLY"
    assert z["shock_deltas_can_be_added"] is False
    assert z["single_shock_effect_is_a_causal_effect"] is False
    assert z["economic_results_are_authenticated"] is False
    assert all(s["hypothetical_delta_operating_profit_minor"]<0 for s in z["shocks"])
    assert z["automatic_price_or_spend_change"] is False
    assert z["execution_authority"]=="none"


@pytest.mark.parametrize("change",[
    {"shock_key":"duplicated","field":"wrong_field","proposed_value":0,
     "assumption_status":"HYPOTHETICAL_UNCALIBRATED"},
    {"shock_key":"new_test","field":"unit_price_minor","proposed_value":-50,
     "assumption_status":"HYPOTHETICAL_UNCALIBRATED"},
    {"shock_key":"new_test","field":"unit_price_minor","proposed_value":9000,
     "assumption_status":"PAID_REVENUE_VERIFIED"},
    {"shock_key":"new_test","field":"conversion_rate","proposed_value":float("inf"),
     "assumption_status":"HYPOTHETICAL_UNCALIBRATED"},
])
def test_sensitivity_unverified_and_invalid_factors_fail_closed(change):
    from empire_os.predictive_profitability_playbooks import review_profitability_sensitivities
    p=pilot()
    with pytest.raises(ValueError):
        review_profitability_sensitivities(p,plan(p),[change],as_of=NOW)


def test_paid_cycle_timing_respects_original_pilot_horizon():
    x=plan(kind="subscription")
    for s in x["scenarios"]:
        s["paid_cycles"]=3
        s["paid_cycle_period_days"]=30
    with pytest.raises(ValueError,match="horizon"):
        review(x=x)
    for s in x["scenarios"]:
        s["paid_cycle_period_days"]=7
    r=review(x=x)
    assert r["scenario_rows"][1]["expected_paid_cycles_per_customer_hypothetical"]==3
    assert r["scenario_rows"][1]["paid_cycle_period_days_assumed"]==7
