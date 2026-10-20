"""Precision-first market and revenue-gap diagnostics on original Predictive Twin.

Produces economically comparable *hypotheses*, not discovered paying buyers,
causally proven gaps, actual sales or an executable growth campaign.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Mapping, Sequence
import re

from empire_os.predictive_market_economic_twin import (
    review_market_economic_twin, DRIVERS,
)
from empire_os.predictive_profitability_playbooks import (
    review_profitability_playbook,
)

SCHEMA = "empire.predictive_revenue.structural_revenue_gap_review.v1"
KEY = re.compile(r"^[a-z][a-z0-9_]{2,48}$")
CAUSES = {
    "capacity_constraint": ("labor_capacity", "supply_chain"),
    "demand_acquisition": ("channel_distribution", "seasonal_demand", "search_ai_change"),
    "conversion_friction": ("consumer_preference", "competitor_response"),
    "cost_pressure": ("material_cost", "supply_chain"),
    "price_pressure": ("competitor_response", "regulatory_change"),
    "fulfilment_risk": ("labor_capacity", "weather_storm", "supply_chain"),
    "regulatory_delay": ("regulatory_change",),
}
INTERVENTION_FIELDS = frozenset((
    "case_key", "suspected_cause", "driver_type", "hypothesis_ref",
    "estimated_days_to_effect_unverified", "assumed_one_off_cash_cost_minor",
    "demand_multiplier", "capacity_multiplier", "price_multiplier",
    "conversion_multiplier", "acquisition_cost_multiplier",
    "fulfilment_cost_multiplier", "refund_rate_delta",
))
RISK_CLASS = {
    "gap_unverified": "EVIDENCE_GAP",
    "under_capacity": "HYPOTHETICAL_SERVICE_CAPACITY_SHORTFALL",
    "unprofitable": "HYPOTHETICAL_UNIT_ECONOMIC_SHORTFALL",
    "cash_risk": "HYPOTHETICAL_CASH_EXPOSURE_RISK",
}


def _numeric(v: Any, *, minimum: float=0, maximum: float=5) -> float:
    if type(v) not in (int,float) or not isfinite(v) or not minimum<=v<=maximum:
        raise ValueError("bounded, finite, explicit hypothetical multiplier required")
    return float(v)


def review_structural_market_revenue_gaps(
    pilot: Mapping[str,Any],
    economic_plan: Mapping[str,Any],
    market: Mapping[str,Any],
    interventions: Sequence[Mapping[str,Any]], *,
    as_of: datetime,
)->dict[str,Any]:
    """Compare structural remedies against exactly the same original economics.

    The only proven input here is what assumptions were supplied and which
    constraints the existing engines imply. Source observations and
    independent causal root causes have *not* been established.
    """
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware review clock required")
    if not isinstance(interventions,(list,tuple)) or not 1<=len(interventions)<=10:
        raise ValueError("1–10 specifically named gap remediation hypotheses required")
    if not isinstance(market,Mapping):
        raise ValueError("original hypothetical market required")
    demand=market.get("demand_units")
    capacity=market.get("capacity_units")
    if type(demand) is not int or type(capacity) is not int:
        raise ValueError("original numeric uncalibrated market assumptions required")
    if demand<0 or capacity<0:
        raise ValueError("original nonnegative market units required")
    if not isinstance(economic_plan,Mapping):
        raise ValueError("original economic plan required")

    # The zero-change case is the same underlying original twin/plan, NOT an
    # alternate outcome population or fresh unregistered original forecast.
    baseline=review_profitability_playbook(pilot,economic_plan,as_of=as_of)
    if (baseline.get("status")!="HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY"
            or baseline.get("execution_authority")!="none"
            or baseline.get("original_forecast_registered") is not False
            or baseline.get("actual_gross_profit_verified") is not False):
        raise ValueError("trusted hypothetical original unit economics required")
    horizon=economic_plan.get("economic_horizon_days")
    limit=economic_plan.get("max_cash_exposure_minor")
    if type(horizon) is not int or not 1<=horizon<=365:
        raise ValueError("original economic evaluation horizon required")
    if type(limit) is not int or not 0<=limit<=10**11:
        raise ValueError("original bounded cash-risk limit required")

    drivers=[]
    metadata=[]
    seen=set()
    for candidate in interventions:
        if not isinstance(candidate,Mapping) or set(candidate)!=INTERVENTION_FIELDS:
            raise ValueError("strict, complete structural intervention contract required")
        key=candidate["case_key"]
        cause=candidate["suspected_cause"]
        kind=candidate["driver_type"]
        if (not isinstance(key,str) or not KEY.fullmatch(key) or key in seen
                or cause not in CAUSES or kind not in CAUSES[cause] or kind not in DRIVERS):
            raise ValueError("unique plausible lever, causal hypothesis and driver required")
        seen.add(key)
        hypothesis=candidate["hypothesis_ref"]
        if not isinstance(hypothesis,str) or not KEY.fullmatch(hypothesis):
            raise ValueError("original hypothetical source assumption key required")
        days=candidate["estimated_days_to_effect_unverified"]
        cash=candidate["assumed_one_off_cash_cost_minor"]
        if (type(days) is not int or not 1<=days<=180
                or type(cash) is not int or not 0<=cash<=10**10):
            raise ValueError("bounded explicit hypothetical intervention timing and cost required")
        dm=_numeric(candidate["demand_multiplier"])
        cm=_numeric(candidate["capacity_multiplier"])
        pm=_numeric(candidate["price_multiplier"])
        conv=_numeric(candidate["conversion_multiplier"])
        cac=_numeric(candidate["acquisition_cost_multiplier"])
        fulfil=_numeric(candidate["fulfilment_cost_multiplier"])
        refund=_numeric(candidate["refund_rate_delta"],minimum=-1,maximum=1)
        driver={
            "driver_key":key,"driver_type":kind,
            "assumption_status":"HYPOTHETICAL_UNCALIBRATED",
            "hypothesis_ref":hypothesis,
            "demand_multiplier":dm,
            "capacity_multiplier":cm,
            "price_multiplier":pm,
            "conversion_multiplier":conv,
            "acquisition_cost_multiplier":cac,
            "fulfilment_cost_multiplier":fulfil,
            "refund_rate_delta":refund,
        }
        drivers.append(driver)
        metadata.append({
            "case_key":key,
            "suspected_cause_not_confirmed":cause,
            "potential_structural_lever":kind,
            "assumed_one_off_cash_cost_minor":cash,
            "estimated_days_to_effect_unverified":days,
            "timely_within_original_horizon_under_assumptions":days<=horizon,
        })

    original=review_market_economic_twin(
        pilot,economic_plan,market,drivers,as_of=as_of,
    )
    if (original.get("status")!="HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED"
            or original.get("execution_authority")!="none"
            or original.get("original_forecast_registered") is not False
            or original.get("market_shock_applied_to_production") is not False
            or original.get("scenario_driver_count")!=len(drivers)
            or original.get("original_pilot_design_sha256")
               !=baseline.get("original_pilot_design_sha256")):
        raise ValueError("original market twin review or pilot lineage mismatch")
    rows={r["driver_key"]:r for r in original["driver_scenarios"]}
    if len(rows)!=len(metadata):
        raise ValueError("scenario output coverage drift")
    base_profit=baseline["hypothetical_weighted_operating_profit_minor"]
    candidate_results=[]
    for item in metadata:
        row=rows[item["case_key"]]
        expense=item["assumed_one_off_cash_cost_minor"]
        incremental=round(row["hypothetical_weighted_profit_delta_minor"]-expense,4)
        net_profit=round(row["hypothetical_weighted_operating_profit_minor"]-expense,4)
        worst=round(row["hypothetical_worst_profit_minor"]-expense,4)
        # Conservative cash check: the one-off cash estimate is additional to
        # the twin's modeled cash outflow, not added to realised financial books.
        cash_stress=round(row["hypothetical_cash_stress_minor"]+expense,4)
        over_cash=cash_stress>limit
        profitable=incremental>0 and net_profit>0 and worst>=0
        timely=item["timely_within_original_horizon_under_assumptions"]
        # Do not rank scenario expected profits as measured value or VOI.
        if not timely:
            verdict="RESEARCH_TIMING_BEYOND_ECONOMIC_HORIZON"
        elif over_cash:
            verdict="RESEARCH_CASH_LIMIT_UNDER_ASSUMPTIONS"
        elif not profitable:
            verdict="RESEARCH_PROFITABILITY_OR_DOWNSIDE_UNDER_ASSUMPTIONS"
        else:
            verdict="RESEARCH_CONDITIONALLY_FEASIBLE_UNVERIFIED"
        candidate_results.append({
            **item,
            "simulated_demand_units_not_verified_market_demand":row["simulated_demand_units"],
            "simulated_delivery_capacity_units_not_verified_available_supply":row["simulated_capacity_units"],
            "simulated_unserved_eligible_attempts_not_lost_sales":max(
                row["simulated_demand_units"]-row["simulated_capacity_units"],0
            ),
            "hypothetical_incremental_operating_profit_net_of_one_off_cost_minor":incremental,
            "hypothetical_net_operating_profit_minor":net_profit,
            "hypothetical_worst_case_operating_profit_net_of_one_off_cost_minor":worst,
            "hypothetical_pre_collection_cash_exposure_including_one_off_minor":cash_stress,
            "cash_exposure_exceeds_original_assumed_limit":over_cash,
            "underlying_market_capacity_binding":row["capacity_binding"],
            "gap_repair_profitability_proven":False,
            "time_to_value_measured":False,
            "root_cause_independently_authenticated":False,
            "intervention_causally_tested":False,
            "intervention_verdict":verdict,
            "published_value_of_information_minor":None,
        })
    # Fixed ordinal rule, never machine-learned probability or real ROI rank.
    verdict_order={
        "RESEARCH_CONDITIONALLY_FEASIBLE_UNVERIFIED":0,
        "RESEARCH_PROFITABILITY_OR_DOWNSIDE_UNDER_ASSUMPTIONS":1,
        "RESEARCH_CASH_LIMIT_UNDER_ASSUMPTIONS":2,
        "RESEARCH_TIMING_BEYOND_ECONOMIC_HORIZON":3,
    }
    candidate_results.sort(key=lambda x:(
        verdict_order[x["intervention_verdict"]],
        -x["hypothetical_incremental_operating_profit_net_of_one_off_cost_minor"],
        x["case_key"],
    ))
    market_unserved=max(demand-capacity,0)
    diagnostic=[
        {
            "gap_type":RISK_CLASS["under_capacity"],
            "hypothetical_gap_units":market_unserved,
            "gap_units_are_actual_lost_sales":False,
            "suspected_drivers":["capacity_constraint","fulfilment_risk"]
                if market_unserved else [],
            "root_cause_established":False,
            "verification_owner":"existing_spatial_service_capacity_and_commerce",
        },
        {
            "gap_type":RISK_CLASS["unprofitable"],
            "hypothetical_gap_units":None,
            "baseline_hypothetical_weighted_operating_profit_minor":base_profit,
            "may_require_margin_repair":base_profit<=0,
            "root_cause_established":False,
            "verification_owner":"existing_finance_pricing_materials_quant",
        },
        {
            "gap_type":RISK_CLASS["cash_risk"],
            "hypothetical_gap_units":None,
            "baseline_pre_collection_cash_exposure_minor":baseline[
                "hypothetical_max_cash_outflow_before_collection_minor"
            ],
            "cash_risk_under_baseline":baseline[
                "worst_case_cash_exposure_above_assumed_limit"
            ],
            "root_cause_established":False,
            "verification_owner":"existing_finance_and_treasury",
        },
        {
            "gap_type":RISK_CLASS["gap_unverified"],
            "hypothetical_gap_units":None,
            "observed_funnel_conversion_denominator":None,
            "authenticated_market_purchase_or_service_units":None,
            "observed_industry_total_addressable_gap_minor":None,
            "causally_attributed_revenue_leak_minor":None,
            "root_cause_established":False,
            "verification_owner":"existing_market_gps_buyer_qualifier_crm_and_quant",
        },
    ]
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"STRUCTURAL_MARKET_GAP_HYPOTHESIS_REVIEWED",
        "market_key":original["market_key"],
        "geography_key":original["geography_key"],
        "niche_key":original["niche_key"],
        "original_pilot_design_sha256":original["original_pilot_design_sha256"],
        "assumptions_are_real_market_evidence":False,
        "baseline_hypothetical_eligible_demand_units":demand,
        "baseline_hypothetical_delivery_capacity_units":capacity,
        "baseline_hypothetical_unserved_attempts":market_unserved,
        "baseline_hypothetical_weighted_operating_profit_minor":base_profit,
        "original_cash_limit_minor":limit,
        "original_economic_horizon_days":horizon,
        "gap_diagnostics":diagnostic,
        "intervention_count":len(candidate_results),
        "intervention_research_comparisons":candidate_results,
        "rankings_are_observed_best_market_opportunities":False,
        "hypothetical_case_weights_are_calibrated_probabilities":False,
        "root_causes_authenticated":False,
        "original_demand_and_supply_evidence_verified":False,
        "estimated_market_revenue_gap_minor":None,
        "authenticated_potential_recoverable_revenue_minor":None,
        "measured_incremental_operating_profit_minor":None,
        "recommended_original_evidence_owner_order":[
            "AUTHENTICATE_ORIGINAL_MARKET_CONVERSION_DENOMINATOR_AND_PRICE",
            "VERIFY_DELIVERABLE_CAPACITY_MATERIALS_COSTS_AND_FULFILMENT",
            "REGISTER_ORIGINAL_PRE_OUTCOME_ECONOMIC_PREDICTION",
            "MEASURE_REAL_OUTCOME_PAYMENT_REFUNDS_MARGIN_AND_COLLECTION_TIMES",
            "EXPERIMENT_WITH_COMPARABLE_CONTROL_WHEN_AUTHORIZED",
        ],
        "decision_policy_authority_granted":False,
        "live_campaign_or_website_changed":False,
        "original_quant_forecast_registered":False,
        "calibration_performed":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
