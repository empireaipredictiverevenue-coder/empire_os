"""Market Digital Twin -> scenario re-evaluation of Predictive unit economics.

Preserves existing deterministic MarketScenario and profitability playbook
engines. All market baselines and stresses are explicitly HYPOTHETICAL; real
weather, labour, search, competitor, geography or capacity observations must
arrive from their original, permissioned source owners.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence
import re

from empire_os.digital_twin import MarketBaseline, MarketScenario, simulate_market_scenario
from empire_os.predictive_profitability_playbooks import (
    review_profitability_playbook, PLAN_FIELDS, VARIANTS,
)

SCHEMA="empire.predictive_revenue.market_economic_twin.v1"
SLUG=re.compile(r"^[a-z][a-z0-9_]{2,63}$")
KEY=re.compile(r"^[a-z][a-z0-9_.:-]{2,95}$")
GEO_FIELDS=frozenset((
    "market_key","geography_key","niche_key","baseline_at",
    "evidence_ref","assumption_status","demand_units","capacity_units",
    "price_per_unit_minor","capacity_rights_verified",
))
DRIVER_FIELDS=frozenset((
    "driver_key","driver_type","assumption_status","hypothesis_ref",
    "demand_multiplier","capacity_multiplier","price_multiplier",
    "conversion_multiplier","acquisition_cost_multiplier",
    "fulfilment_cost_multiplier","refund_rate_delta",
))
DRIVERS=frozenset((
    "weather_storm","material_cost","competitor_response","search_ai_change",
    "labor_capacity","seasonal_demand","regulatory_change",
    "consumer_preference","channel_distribution","supply_chain",
))
MAX_MONEY=10**10


def _number(value:Any,name:str,hi:float,integer:bool=False) -> float | int:
    if type(value) not in ((int,) if integer else (int,float)) or not 0<=value<=hi:
        raise ValueError("invalid bounded hypothetical "+name)
    return value


def _slug(value:Any,name:str,pattern=re.compile(r"^[a-z][a-z0-9_]{2,63}$")) -> str:
    if not isinstance(value,str) or not pattern.fullmatch(value):
        raise ValueError("bounded "+name+" required")
    return value


def review_market_economic_twin(
    pilot: Mapping[str,Any],
    economic_plan: Mapping[str,Any],
    market: Mapping[str,Any],
    drivers: Sequence[Mapping[str,Any]], *,
    as_of:datetime,
) -> dict[str,Any]:
    """Full profit re-evaluation after geographic demand/capacity/cost shocks."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted prospective clock required")
    initial=review_profitability_playbook(pilot,economic_plan,as_of=as_of)
    if (not isinstance(market,Mapping) or set(market)!=GEO_FIELDS
            or market["assumption_status"]!="HYPOTHETICAL_UNCALIBRATED"
            or market["capacity_rights_verified"] is not False):
        raise ValueError("unverified hypothetical market baseline only")
    key=_slug(market["market_key"],"market key")
    geo=_slug(market["geography_key"],"geographic location")
    niche=_slug(market["niche_key"],"market niche")
    evidence=_slug(market["evidence_ref"],"hypothesis evidence ref",KEY)
    from empire_os.predictive_customer_value_demand import _time
    observed=_time(market["baseline_at"])
    if not 0<=(as_of-observed).total_seconds()<=7*86400:
        raise ValueError("hypothetical market timestamp is stale or from future")
    demand=_number(market["demand_units"],"demand units",1_000_000,True)
    capacity=_number(market["capacity_units"],"capacity units",1_000_000,True)
    price=_number(market["price_per_unit_minor"],"unit price",MAX_MONEY,True)
    if price<=0:
        raise ValueError("positive hypothetical price required")
    if (not isinstance(economic_plan,Mapping) or set(economic_plan)!=PLAN_FIELDS
            or any(type(s.get("unit_price_minor")) is not int
                   or s["unit_price_minor"]!=price
                   for s in economic_plan["scenarios"])):
        raise ValueError("twin purchased unit must match original economics assumption")
    if any(s["qualified_attempts"] != min(demand,capacity)
           for s in economic_plan["scenarios"]):
        raise ValueError("original economics attempt cohort must equal baseline served-capacity units")
    if not isinstance(drivers,(list,tuple)) or not 1<=len(drivers)<=12:
        raise ValueError("bounded scenario drivers required")
    # Legacy MarketBaseline calls its inputs 'observed', hence it must never
    # be sent to a real-data API: this wrapper forces hypothetical only.
    original=MarketBaseline(
        niche=niche,metro=geo,observed_demand_units=demand,
        observed_capacity_units=capacity,
        observed_price_per_unit_cents=price,
        observed_at=observed.isoformat(),evidence_ref="hypothesis:"+evidence,
    )
    original.validate()
    baseline_served=min(demand,capacity)
    seen=set()
    summaries=[]
    for driver in drivers:
        if not isinstance(driver,Mapping) or set(driver)!=DRIVER_FIELDS:
            raise ValueError("exact typed economic twin driver fields required")
        driver_key=_slug(driver["driver_key"],"driver key")
        dtype=driver["driver_type"]
        if not isinstance(dtype,str) or dtype not in DRIVERS or driver_key in seen:
            raise ValueError("unique allowed economic market driver required")
        seen.add(driver_key)
        if driver["assumption_status"]!="HYPOTHETICAL_UNCALIBRATED":
            raise ValueError("uncalibrated stress must not masquerade as observed")
        _slug(driver["hypothesis_ref"],"driver evidence ref",KEY)
        dm=_number(driver["demand_multiplier"],"demand multiplier",5)
        cm=_number(driver["capacity_multiplier"],"capacity multiplier",5)
        pm=_number(driver["price_multiplier"],"price multiplier",5)
        conv=_number(driver["conversion_multiplier"],"conversion multiplier",5)
        cac=_number(driver["acquisition_cost_multiplier"],"acquisition multiplier",5)
        fulfil=_number(driver["fulfilment_cost_multiplier"],"fulfilment multiplier",5)
        refund=driver["refund_rate_delta"]
        if type(refund) not in (int,float) or not -1<=refund<=1:
            raise ValueError("refund rate change bounded to minus/plus one")
        market_result=simulate_market_scenario(
            baseline=original,
            scenario=MarketScenario(
                scenario_id=driver_key,demand_multiplier=dm,
                capacity_multiplier=cm,price_multiplier=pm,
            ),
        )
        if market_result.projected_price_per_unit_cents==0 and market_result.projected_served_units>0:
            raise ValueError("positive served units require a price")
        # The market twin projects SERVED eligible attempts capped by delivery
        # capacity, not paid conversions. The economics engine still models
        # payment separately using its original scenario conversion rates.
        changed=[]
        for s in economic_plan["scenarios"]:
            factor_price=market_result.projected_price_per_unit_cents
            factor_attempts=market_result.projected_served_units
            factor_conversion=s["conversion_rate"]*conv
            if factor_conversion>1:
                raise ValueError("conversion shock exceeds probability one")
            refund_value=s["refund_rate"]+refund
            if not 0<=refund_value<=1:
                raise ValueError("driver would create invalid refund probability")
            spend=round(s["acquisition_cost_per_attempt_minor"]*cac)
            variable=round(s["fulfilment_cost_per_paid_cycle_minor"]*fulfil)
            if max(spend,variable,factor_price)>MAX_MONEY:
                raise ValueError("market driver would exceed monetary scenario bounds")
            changed.append({
                **s,"unit_price_minor":factor_price,
                "qualified_attempts":factor_attempts,
                "conversion_rate":factor_conversion,
                "refund_rate":refund_value,
                "acquisition_cost_per_attempt_minor":spend,
                "fulfilment_cost_per_paid_cycle_minor":variable,
            })
        scenario_book=review_profitability_playbook(
            pilot,{**economic_plan,"scenarios":changed},as_of=as_of,
        )
        summaries.append({
            "driver_key":driver_key,"driver_type":dtype,
            "hypothesis_not_measured_weather_or_market_data":True,
            "simulated_demand_units":market_result.projected_demand_units,
            "simulated_capacity_units":market_result.projected_capacity_units,
            "simulated_eligible_attempts_capacity_capped":market_result.projected_served_units,
            "simulated_purchased_unit_price_minor":market_result.projected_price_per_unit_cents,
            "capacity_binding":market_result.projected_demand_units>market_result.projected_capacity_units,
            "hypothetical_weighted_operating_profit_minor":scenario_book["hypothetical_weighted_operating_profit_minor"],
            "hypothetical_weighted_profit_delta_minor":round(
                scenario_book["hypothetical_weighted_operating_profit_minor"]
                -initial["hypothetical_weighted_operating_profit_minor"],4,
            ),
            "hypothetical_worst_profit_minor":scenario_book["hypothetical_worst_operating_profit_minor"],
            "hypothetical_cash_stress_minor":scenario_book["hypothetical_max_cash_outflow_before_collection_minor"],
            "cash_cap_exceeded":scenario_book["worst_case_cash_exposure_above_assumed_limit"],
            "driver_intervention_is_proven_causal_effect":False,
        })
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED",
        "market_key":key,"geography_key":geo,"niche_key":niche,
        "opportunity_key":initial["opportunity_key"],
        "original_pilot_design_sha256":initial["original_pilot_design_sha256"],
        "hypothetical_baseline_eligible_attempts":baseline_served,
        "hypothetical_baseline_unit_price_minor":price,
        "baseline_weighted_operating_profit_minor":initial["hypothetical_weighted_operating_profit_minor"],
        "scenario_driver_count":len(summaries),
        "driver_scenarios":summaries,
        "uses_existing_market_digital_twin":True,
        "uses_existing_profitability_playbook":True,
        "source_market_conditions_authenticated":False,
        "company_geographic_eligibility_verified":False,
        "weather_phenomenon_confirmed":False,
        "pricing_and_purchasing_terms_verified":False,
        "simulated_served_attempts_are_paid_sales":False,
        "scenario_profit_is_recognized_revenue":False,
        "original_forecast_registered":False,
        "next_owner":"market_spatial_intelligence_strategy_and_finance",
        "next_action":"COLLECT_SOURCE_REVISED_MARKET_CAPACITY_COST_AND_PURCHASING_RECEIPTS",
        "market_shock_applied_to_production":False,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
