"""Multi-series cost-pressure decision lens using the EXISTING Market Economic Twin.

Each scenario is a declared hypothetical experiment, never an inferred local
cost or commercially approved action. Published national PPI is *output price*,
not an authentic supplier bill, forecast probability or contractor capacity.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping, Sequence
import re

from empire_os.predictive_bls_cost_index import SCHEMA as BLS_SCHEMA
from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_market_economic_twin import (
    review_market_economic_twin,
    DRIVERS, DRIVER_FIELDS,
)

SCHEMA="empire.predictive_revenue.multi_index_cost_pressure_lens.v1"
NAME=re.compile(r"^[a-z][a-z0-9_]{2,48}$")
HEX=re.compile(r"^[0-9a-f]{64}$")
MAX_INDEX_SHOCK=3.0


def _fraction(x:Any,name:str)->float:
    if type(x) not in (int,float) or not isfinite(x) or not 0<=x<=1:
        raise ValueError("explicit 0-to-1 "+name+" hypothesis required")
    return float(x)


def _fail_closed_source(source:Mapping[str,Any],now:datetime)->dict[str,Mapping[str,Any]]:
    if (not isinstance(source,Mapping)
            or source.get("schema_version")!=BLS_SCHEMA
            or source.get("status")!="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"
            or source.get("execution_authority")!="none"
            or source.get("original_source_publisher_authenticated_independently") is not False
            or source.get("actual_material_or_labor_cost_authenticated") is not False
            or source.get("realized_profit_verified") is not False
            or not isinstance(source.get("source_revision_sha256"),str)
            or not HEX.fullmatch(source["source_revision_sha256"])):
        raise ValueError("original research-only BLS owner review required")
    observed=_time(source.get("owner_source_generated_at"))
    if not timedelta(0)<=now-observed<=timedelta(hours=72):
        raise ValueError("BLS source review timestamp stale or from future")
    rows=source.get("series_research_cards")
    if (not isinstance(rows,list) or type(source.get("series_observation_count")) is not int
            or len(rows)!=source["series_observation_count"] or not 1<=len(rows)<=12):
        raise ValueError("source card completeness required")
    index={}
    for row in rows:
        if not isinstance(row,Mapping):
            raise ValueError("invalid BLS source series")
        sid=row.get("original_public_series_id")
        if not isinstance(sid,str) or sid in index:
            raise ValueError("unique source series required")
        index[sid]=row
    return index


def review_multi_index_cost_pressure(
    source:Mapping[str,Any],
    pilot:Mapping[str,Any],
    economic_plan:Mapping[str,Any],
    market:Mapping[str,Any],
    *,
    cost_basket:Sequence[Mapping[str,Any]],
    scenario_cases:Sequence[Mapping[str,Any]],
    as_of:datetime,
)->dict[str,Any]:
    """Evaluate explicit material input exposure hypotheses, using owner twin."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware scenario time required")
    now=as_of.astimezone(timezone.utc)
    series=_fail_closed_source(source,now)
    if (not isinstance(market,Mapping)
            or market.get("market_key") not in ("us","usa","united_states")
            or market.get("assumption_status")!="HYPOTHETICAL_UNCALIBRATED"
            or market.get("capacity_rights_verified") is not False):
        raise ValueError("US BLS index cannot silently price an unverified foreign market")
    if (not isinstance(cost_basket,(tuple,list)) or not 1<=len(cost_basket)<=6
            or not isinstance(scenario_cases,(tuple,list)) or not 2<=len(scenario_cases)<=6):
        raise ValueError("bounded original cost basket and scenario cases required")
    seen=set()
    series_cost_shares=[]
    total_share=0.0
    for item in cost_basket:
        if (not isinstance(item,Mapping)
                or set(item)!={
                    "series_id","assumed_input_cost_share","assumed_index_to_cost_translation_fraction"
                }):
            raise ValueError("strict cost basket row required")
        sid=item["series_id"]
        if sid not in series or sid in seen:
            raise ValueError("unknown or repeated BLS series in cost basket")
        seen.add(sid)
        row=series[sid]
        if row.get("owner_reported_series_role")!="producer_output_price_index":
            raise ValueError("wage index is not material price or workforce capacity")
        pct=row.get("year_over_year_index_change_pct_research_only")
        if type(pct) not in (int,float) or not isfinite(pct) or not -100<=pct<=500:
            raise ValueError("same-month original cost index comparison required")
        exposure=_fraction(item["assumed_input_cost_share"],"input cost share")
        passed=_fraction(item["assumed_index_to_cost_translation_fraction"],"index-to-cost mapping")
        total_share+=exposure
        series_cost_shares.append({
            "public_series_id":sid,
            "source_yoy_output_price_index_pct":round(float(pct),5),
            "assumed_input_cost_share":exposure,
            "assumed_index_to_cost_translation_fraction":passed,
            "hypothetical_cost_multiplier_component":round(float(pct)/100*exposure*passed,8),
            "source_month":row.get("latest_observed_month"),
            "source_series_is_original_job_invoice":False,
            "source_series_is_verified_local_supplier_cost":False,
        })
    if total_share>1.00000001:
        raise ValueError("cost exposure shares cannot exceed 100 percent")

    drivers=[]
    selections=[]
    case_keys=set()
    for case in scenario_cases:
        if (not isinstance(case,Mapping)
                or set(case)!={"case_key","assumed_index_change_scale",
                                "assumed_capacity_multiplier","assumed_demand_multiplier",
                                "assumed_price_multiplier"}
                or not isinstance(case["case_key"],str)
                or not NAME.fullmatch(case["case_key"])
                or case["case_key"] in case_keys):
            raise ValueError("unique bounded what-if case name and parameters required")
        case_keys.add(case["case_key"])
        scale=case["assumed_index_change_scale"]
        if type(scale) not in (int,float) or not isfinite(scale) or not 0<=scale<=MAX_INDEX_SHOCK:
            raise ValueError("bounded index amplification must be explicit")
        inputs={}
        for k in ("assumed_capacity_multiplier","assumed_demand_multiplier","assumed_price_multiplier"):
            v=case[k]
            if type(v) not in (int,float) or not isfinite(v) or not 0<=v<=3:
                raise ValueError("bounded market what-if multiplier required")
            inputs[k]=float(v)
        shock=sum(x["hypothetical_cost_multiplier_component"] for x in series_cost_shares)
        cost_factor=1+shock*scale
        if not 0.5<=cost_factor<=1.5:
            raise ValueError("combined scenario cost stress outside modeled safe range")
        driver={
            "driver_key":case["case_key"],
            "driver_type":"material_cost",
            "assumption_status":"HYPOTHETICAL_UNCALIBRATED",
            "hypothesis_ref":"bls_multi_index_assumption",
            "demand_multiplier":inputs["assumed_demand_multiplier"],
            "capacity_multiplier":inputs["assumed_capacity_multiplier"],
            "price_multiplier":inputs["assumed_price_multiplier"],
            "conversion_multiplier":1.0,
            "acquisition_cost_multiplier":1.0,
            "fulfilment_cost_multiplier":round(cost_factor,8),
            "refund_rate_delta":0.0,
        }
        assert set(driver)==DRIVER_FIELDS
        drivers.append(driver)
        selections.append({
            "case_key":case["case_key"],
            "assumed_index_change_scale":float(scale),
            **inputs,
            "assumed_composite_fulfilment_cost_multiplier":round(cost_factor,8),
            "assumed_index_shock_pct_of_full_variable_cost":round((cost_factor-1)*100,5),
            "stress_is_independently_calibrated":False,
        })
    twin=review_market_economic_twin(
        pilot,economic_plan,market,drivers,as_of=as_of,
    )
    if (twin.get("status")!="HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED"
            or twin.get("execution_authority")!="none"
            or twin.get("original_forecast_registered") is not False
            or twin.get("source_market_conditions_authenticated") is not False
            or twin.get("market_shock_applied_to_production") is not False
            or twin.get("scenario_driver_count")!=len(drivers)):
        raise ValueError("original economic twin not research-only")
    outcomes={x["driver_key"]:x for x in twin["driver_scenarios"]}
    if len(outcomes)!=len(drivers):
        raise ValueError("missing twin scenario")
    results=[]
    for scenario in selections:
        key=scenario["case_key"]
        original=outcomes[key]
        results.append({
            **scenario,
            "hypothetical_expected_operating_profit_minor":original[
                "hypothetical_weighted_operating_profit_minor"],
            "hypothetical_profit_delta_vs_original_minor":original[
                "hypothetical_weighted_profit_delta_minor"],
            "hypothetical_worst_operating_profit_minor":original[
                "hypothetical_worst_profit_minor"],
            "hypothetical_cash_exposure_minor":original[
                "hypothetical_cash_stress_minor"],
            "cash_cap_exceeded_under_assumptions":original["cash_cap_exceeded"],
            "modeled_capacity_binding":original["capacity_binding"],
            "hypothetical_eligible_attempts_not_sales":original[
                "simulated_eligible_attempts_capacity_capped"],
            "expected_operating_profit_negative_under_assumptions":
                original["hypothetical_weighted_operating_profit_minor"]<0,
            "worst_case_loss_under_assumptions":
                original["hypothetical_worst_profit_minor"]<0,
            "source_movement_is_not_observed_job_margin":True,
        })
    downside=sorted(results,key=lambda row:(
        row["hypothetical_expected_operating_profit_minor"],row["case_key"]
    ))[0]
    cash=sorted(results,key=lambda row:(
        -row["hypothetical_cash_exposure_minor"],row["case_key"]
    ))[0]
    relative_profit_gap=round(
        max(r["hypothetical_expected_operating_profit_minor"] for r in results)
        -min(r["hypothetical_expected_operating_profit_minor"] for r in results),4,
    )
    priorities=[
        {
            "rank_class":"P0",
            "evidence_need":"SOURCE_PPI_TO_ACTUAL_MATERIAL_INPUT_COST_TRANSLATION",
            "owner":"existing_materials_and_finance",
            "why":"Published producer output indexes are not the supplier's paid input prices",
            "quantified_real_value_of_information_minor":None,
            "is_automatic_action":False,
        },
        {
            "rank_class":"P0",
            "evidence_need":"ORIGINAL_ACCEPTED_CUSTOMER_PRICE_AND_PAYING_BUYER",
            "owner":"existing_commercial_buyers_and_quant",
            "why":"No source series or hypothetical twin independently establishes an accepted selling price or paid unit",
            "quantified_real_value_of_information_minor":None,
            "is_automatic_action":False,
        },
    ]
    if any(row.get("any_source_preliminary_footnotes") for row in series.values()):
        priorities.append({
            "rank_class":"P1","evidence_need":"BLS_PRELIMINARY_SERIES_REVISION_CHECK",
            "owner":"existing_economic_source_owner",
            "why":"One or more original index series has preliminary publication footnotes",
            "quantified_real_value_of_information_minor":None,
            "is_automatic_action":False,
        })
    if any(r["modeled_capacity_binding"] for r in results):
        priorities.append({
            "rank_class":"P0","evidence_need":"ACTUAL_SERVICE_CAPACITY_AND_DELIVERY_RADIUS",
            "owner":"existing_service_and_spatial_capacity_owner",
            "why":"At least one modeled demand/capacity case binds delivery capacity",
            "quantified_real_value_of_information_minor":None,
            "is_automatic_action":False,
        })
    if any(r["cash_cap_exceeded_under_assumptions"] for r in results):
        priorities.append({
            "rank_class":"P0","evidence_need":"PAYMENT_LAG_CASH_LIMIT_AND_COLLECTION_PROOF",
            "owner":"existing_finance_treasury_owner",
            "why":"At least one hypothetical case crosses the original cash exposure policy assumption",
            "quantified_real_value_of_information_minor":None,
            "is_automatic_action":False,
        })
    if any(r["expected_operating_profit_negative_under_assumptions"] for r in results):
        priorities.append({
            "rank_class":"P0","evidence_need":"NEGATIVE_MARGIN_UNIT_ECONOMICS_VERIFICATION",
            "owner":"existing_finance_quant_and_commerce_owners",
            "why":"At least one explicit scenario yields negative weighted operating profit",
            "quantified_real_value_of_information_minor":None,
            "is_automatic_action":False,
        })
    priorities.sort(key=lambda x:(0 if x["rank_class"]=="P0" else 1,x["evidence_need"]))
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"MULTI_INDEX_HYPOTHETICAL_ECONOMIC_RISK_REVIEWED",
        "source_revision_sha256":source["source_revision_sha256"],
        "original_pilot_design_sha256":twin["original_pilot_design_sha256"],
        "market_key":twin["market_key"],
        "market_geography_key":twin["geography_key"],
        "market_niche_key":twin["niche_key"],
        "currency_and_actual_costs_verified":False,
        "cost_basket_sources":series_cost_shares,
        "assumed_total_cost_exposure_share":round(total_share,7),
        "cost_series_overlaps_independently_checked":False,
        "scenario_count":len(results),
        "hypothetical_scenario_outcomes":results,
        "largest_stressed_profit_loss_case":downside["case_key"],
        "largest_stressed_cash_exposure_case":cash["case_key"],
        "hypothetical_profit_dispersion_minor":relative_profit_gap,
        "evidence_priority_queue":priorities,
        "evidence_priority_queue_is_expected_monetary_value_ranking":False,
        "risk_flags":{
            "negative_expected_profit_in_at_least_one_hypothesis":any(
                r["expected_operating_profit_negative_under_assumptions"] for r in results
            ),
            "worst_case_loss_in_at_least_one_hypothesis":any(
                r["worst_case_loss_under_assumptions"] for r in results
            ),
            "cash_cap_exceeded_in_at_least_one_hypothesis":any(
                r["cash_cap_exceeded_under_assumptions"] for r in results
            ),
            "capacity_constrained_in_at_least_one_hypothesis":any(
                r["modeled_capacity_binding"] for r in results
            ),
        },
        "hypothetical_scenario_case_probabilities_authenticated":False,
        "calibrated_likelihood_of_loss":None,
        "genuine_purchases_from_cost_signal":None,
        "realized_customer_gross_profit_minor":None,
        "source_to_actual_job_cost_mapping_authenticated":False,
        "original_forecast_registered":False,
        "scenario_outcomes_entered_into_economic_memory":False,
        "source_index_as_actual_supplier_invoice_used":False,
        "scenario_executed":False,
        "new_commercial_or_marketing_playbook_authorized":False,
        "next_owner":"existing_materials_finance_spatial_quant_and_decision_control",
        "next_action":"REVIEW_COST_EXPOSURE_ASSUMPTIONS_AND_AUTHENTICATE_JOB_COSTS",
        "database_writes":False,"outbound_sent":False,"execution_authority":"none",
    }
