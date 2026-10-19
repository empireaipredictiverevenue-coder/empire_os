"""Economic playbooks on top of EXISTING Quant / scenario portfolio engines.

This is the decision-support layer of Predictive Revenue, not financial truth:
all inputs are EXPLICIT hypothetical assumptions, not observed forecasts.
Known unknowns cannot be normalized into optimism or live spend authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any, Mapping, Sequence
import re

from empire_os.quant_brain import expected_economics, risk_adjusted_score, value_of_information
from empire_os.predictive_cloud_scenario_optimization import (
    build_predictive_cloud_scenario_problem,
)
from empire_os.predictive_customer_value_pilot_preflight import SCHEMA as PILOT_SCHEMA
from empire_os.predictive_customer_value_demand import _time

SCHEMA = "empire.predictive_revenue.profitability_playbooks.v1"
VARIANTS = ("downside", "base", "upside")
KINDS = frozenset(("product", "app", "service", "data_product", "lead", "call", "appointment", "click", "seat", "subscription", "affiliate"))
KEY = re.compile(r"^[a-z][a-z0-9_.:-]{2,95}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
SCENARIO_FIELDS = frozenset((
    "scenario_key", "weight", "assumption_status", "assumption_ref",
    "currency", "product_type", "unit_price_minor", "qualified_attempts",
    "conversion_rate", "refund_rate", "paid_cycles", "paid_cycle_retention_rate", "paid_cycle_period_days",
    "fulfilment_cost_per_paid_cycle_minor", "payment_fee_per_paid_cycle_minor",
    "acquisition_cost_per_attempt_minor", "fixed_pilot_cost_minor",
    "operating_overhead_minor", "cash_collection_lag_days",
))
PLAN_FIELDS = frozenset((
    "opportunity_key", "pilot_design_sha256",
    "economic_horizon_days", "risk_aversion", "max_cash_exposure_minor",
    "scenarios",
))
MAX_MINOR = 10_000_000_000
MAX_ATTEMPTS = 10_000_000


def _num(v: Any, key: str, *, hi: float, integer: bool = False) -> int | float:
    if type(v) not in ((int,) if integer else (int,float)):
        raise ValueError("explicit finite "+key+" required")
    if not 0 <= v <= hi:
        raise ValueError("bounded nonnegative "+key+" required")
    return v


def _fraction(v: Any, key: str) -> float:
    return float(_num(v,key,hi=1))


def _pilot(pilot: Mapping[str,Any], now: datetime) -> None:
    if (not isinstance(pilot,Mapping)
            or pilot.get("schema_version")!=PILOT_SCHEMA
            or pilot.get("status")!="PROSPECTIVE_VALUE_PILOT_DESIGN_UNREGISTERED"
            or pilot.get("prospective_design_durably_registered") is not False
            or pilot.get("original_quant_forecast_registered") is not False
            or pilot.get("execution_authority")!="none"):
        raise ValueError("unregistered original customer-value pilot preflight required")
    t=_time(pilot.get("planned_pilot_start_at"))
    if t <= now:
        raise ValueError("profitability assumptions require future original pilot")


def review_profitability_playbook(
    pilot: Mapping[str,Any], plan: Mapping[str,Any], *,
    as_of: datetime,
) -> dict[str,Any]:
    """Quant-driven scenario comparison, unit economics, cash exposure, playbooks."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware review time required")
    now=as_of.astimezone(timezone.utc)
    _pilot(pilot,now)
    if not isinstance(plan,Mapping) or set(plan)!=PLAN_FIELDS:
        raise ValueError("exact economic plan contract required")
    if (plan["opportunity_key"]!=pilot.get("opportunity_key")
            or not isinstance(plan["pilot_design_sha256"],str)
            or not SHA.fullmatch(plan["pilot_design_sha256"])
            or plan["pilot_design_sha256"]!=pilot.get("design_revision_sha256")):
        raise ValueError("original pilot/opportunity revision mismatch")
    horizon=_num(plan["economic_horizon_days"],"horizon",hi=365,integer=True)
    if not 1<=horizon<=365:
        raise ValueError("positive bounded horizon required")
    if horizon != pilot["planned_horizon_days"]:
        raise ValueError("original pilot horizon drift")
    risk=_fraction(plan["risk_aversion"],"risk aversion")
    budget=_num(plan["max_cash_exposure_minor"],"cash cap",hi=MAX_MINOR,integer=True)
    scenarios=plan["scenarios"]
    if (not isinstance(scenarios,(list,tuple)) or len(scenarios)!=3
            or any(not isinstance(s,Mapping) or set(s)!=SCENARIO_FIELDS for s in scenarios)
            or {s["scenario_key"] for s in scenarios if isinstance(s["scenario_key"],str)}!=set(VARIANTS)):
        raise ValueError("exact downside/base/upside scenario set required")
    normalized=[]
    currency=None
    kind=None
    for s in scenarios:
        if (s["assumption_status"]!="HYPOTHETICAL_UNCALIBRATED"
                or not isinstance(s["assumption_ref"],str)
                or not KEY.fullmatch(s["assumption_ref"])):
            raise ValueError("source hypothesis ref is not authenticated evidence")
        if (not isinstance(s["currency"],str) or s["currency"] not in ("USD","GBP","EUR")
                or not isinstance(s["product_type"],str) or s["product_type"] not in KINDS):
            raise ValueError("single scoped currency and supported commercial product required")
        if currency is None:
            currency=s["currency"]
            kind=s["product_type"]
        if s["currency"]!=currency or s["product_type"]!=kind:
            raise ValueError("cannot aggregate different currency/product units")
        weight=_fraction(s["weight"],"scenario weight")
        price=_num(s["unit_price_minor"],"unit price",hi=MAX_MINOR,integer=True)
        attempts=_num(s["qualified_attempts"],"qualified attempts",hi=MAX_ATTEMPTS,integer=True)
        conversion=_fraction(s["conversion_rate"],"conversion")
        refunds=_fraction(s["refund_rate"],"refunds")
        cycles=_num(s["paid_cycles"],"paid cycles",hi=36,integer=True)
        if cycles<1:
            raise ValueError("positive paid cycles required")
        retention=_fraction(s["paid_cycle_retention_rate"],"paid cycle retention")
        cadence=_num(s["paid_cycle_period_days"],"paid cycle period",hi=365,integer=True)
        if cadence<1 or 1+(cycles-1)*cadence>horizon:
            raise ValueError("paid cycle count cannot exceed original scenario horizon")
        expected_cycles=sum(retention**index for index in range(cycles))
        fulfil=_num(s["fulfilment_cost_per_paid_cycle_minor"],"fulfilment",hi=MAX_MINOR,integer=True)
        fees=_num(s["payment_fee_per_paid_cycle_minor"],"payment fee",hi=MAX_MINOR,integer=True)
        cac=_num(s["acquisition_cost_per_attempt_minor"],"acquisition cost",hi=MAX_MINOR,integer=True)
        fixed=_num(s["fixed_pilot_cost_minor"],"fixed setup",hi=MAX_MINOR,integer=True)
        overhead=_num(s["operating_overhead_minor"],"operating overhead",hi=MAX_MINOR,integer=True)
        lag=_num(s["cash_collection_lag_days"],"cash lag",hi=365,integer=True)
        conditional_revenue=expected_cycles*price*(1-refunds)
        conditional_cogs=expected_cycles*(fulfil+fees)
        # Existing canonical Quant expected economics: gross profit excludes
        # acquisition/overhead; an accepted paid cycle may still be refunded.
        gp=expected_economics(
            probability_success=conversion,
            conditional_revenue_cents=conditional_revenue,
            fixed_cost_cents=0,
            success_cost_cents=conditional_cogs,
        )
        expected_revenue=attempts*gp.expected_revenue_cents
        expected_cogs=attempts*gp.expected_cost_cents
        gross_profit=attempts*gp.expected_gross_profit_cents
        acquisition=attempts*cac
        operating_profit=gross_profit-acquisition-fixed-overhead
        contribution_per_attempt=gp.expected_gross_profit_cents-cac
        breakeven_attempts=(
            ceil((fixed+overhead)/contribution_per_attempt)
            if contribution_per_attempt>0 else 0
            if fixed+overhead==0 and contribution_per_attempt==0 else None
        )
        # Conservative "no cash collections yet" expected-cost exposure;
        # no claim this is an actual bank balance or worst-case cash drawdown.
        cash_exposure=expected_cogs+acquisition+fixed+overhead
        stress_cash_outflow=attempts*(cycles*(fulfil+fees)+cac)+fixed+overhead
        if max(expected_revenue,cash_exposure,stress_cash_outflow)>10**13:
            raise ValueError("scenario aggregate exceeds bounded safe monetary scale")
        q=risk_adjusted_score(
            expected_gross_profit_cents=operating_profit,
            downside_cents=stress_cash_outflow,
            uncertainty=1.0, confidence=1.0,
            time_to_revenue_days=lag,
        )
        normalized.append({
            "scenario_key":s["scenario_key"],
            "assumption_ref":s["assumption_ref"],
            "weight_hypothetical":weight,
            "currency":currency,
            "product_type":kind,
            "qualified_attempts_assumed":attempts,
            "expected_paid_cycles_per_customer_hypothetical":round(expected_cycles,6),
            "paid_cycle_period_days_assumed":cadence,
            "customer_ltv_net_of_fulfilment_minor_hypothetical":round(
                conditional_revenue-conditional_cogs,4),
            "customer_acquisition_cost_per_conversion_minor_hypothetical":(
                round(cac/conversion,4) if conversion>0 else None
            ),
            "expected_paid_customer_equivalents_hypothetical":round(attempts*conversion,6),
            "expected_revenue_minor_hypothetical":round(expected_revenue,4),
            "expected_cogs_minor_hypothetical":round(expected_cogs,4),
            "expected_gross_profit_minor_hypothetical":round(gross_profit,4),
            "expected_gross_margin_hypothetical":(
                round(gross_profit/expected_revenue,6) if expected_revenue>0 else None
            ),
            "acquisition_spend_minor_hypothetical":acquisition,
            "fixed_and_overhead_minor_hypothetical":fixed+overhead,
            "expected_operating_profit_minor_hypothetical":round(operating_profit,4),
            "break_even_qualified_attempts_hypothetical":breakeven_attempts,
            "break_even_within_assumed_volume":(
                attempts>=breakeven_attempts if breakeven_attempts is not None else False
            ),
            "cash_outflow_before_collections_minor_hypothetical":round(cash_exposure,4),
            "all_conversions_before_collections_stress_cash_minor_hypothetical":stress_cash_outflow,
            "cash_collection_lag_days_assumed":lag,
            "risk_adjusted_operating_profit_score_hypothetical":q["risk_adjusted_score"],
            "unit_margin_before_acquisition_minor_hypothetical":round(
                conditional_revenue-conditional_cogs,4),
            "revenue_recognized":False,
        })
    if abs(sum(x["weight_hypothetical"] for x in normalized)-1)>1e-9:
        raise ValueError("scenario weights must explicitly sum to one")
    bykey={x["scenario_key"]:x for x in normalized}
    if any(bykey["downside"][k]>bykey["base"][k]
           or bykey["base"][k]>bykey["upside"][k]
           for k in ("expected_operating_profit_minor_hypothetical",)):
        raise ValueError("downside/base/upside must be ordered by operating profit")
    weighted_op=sum(x["weight_hypothetical"]*x["expected_operating_profit_minor_hypothetical"]
                    for x in normalized)
    worst=min(x["expected_operating_profit_minor_hypothetical"] for x in normalized)
    robust=(1-risk)*weighted_op+risk*worst
    max_cost=max(x["all_conversions_before_collections_stress_cash_minor_hypothetical"]
                 for x in normalized)
    weighted_gp=sum(x["weight_hypothetical"]*x["expected_gross_profit_minor_hypothetical"]
                    for x in normalized)
    worst_cash_over_budget=max_cost>budget

    # Directional playbooks are recommendations with preconditions. They are
    # not agent tasks, signed instructions, an approved spend or a new solver.
    playbooks=[]
    def action(key: str, owner: str, trigger: str, next_step: str) -> None:
        playbooks.append({
            "playbook_key":key, "owner":owner, "trigger":trigger,
            "next_step":next_step, "automatic_execution_allowed":False,
        })
    action("VERIFY_FIRST_PAYER","business_development",
           "NO_AUTHENTICATED_BUYER_OR_BUYBOX",
           "OBTAIN_ORIGINAL_ACCEPTED_PRICE_TERRITORY_CAPACITY_AND_SOURCE_RIGHTS")
    action("REGISTER_PRE_OUTCOME_ECONOMICS","scientific_quant",
           "NO_ORIGINAL_REGISTERED_FORECAST",
           "FREEZE_ASSUMPTIONS_AND_REGISTER_ORIGINAL_FORECAST_BEFORE_OUTCOMES")
    if worst_cash_over_budget:
        action("CAP_CASH_EXPOSURE","capital_allocator",
               "MAX_POSSIBLE_COST_EXCEEDS_ASSUMED_CASH_LIMIT",
               "REDESIGN_PILOT_SCALE_OR_REQUIRE_SEPARATE_BUDGET_APPROVAL")
    if worst<0:
        action("LIMIT_DOWNSIDE","strategy_and_risk",
               "NEGATIVE_DOWNSIDE_OPERATING_PROFIT",
               "TEST_SMALL_REVERSIBLE_COHORT_AND_DEFINE_STOP_LOSS")
    if any(not x["break_even_within_assumed_volume"] for x in normalized):
        action("REPAIR_UNIT_ECONOMICS","pricing_and_operations",
               "BREAK_EVEN_NOT_REACHED_IN_AT_LEAST_ONE_ASSUMED_SCENARIO",
               "TEST_PRICE_CAC_REFUNDS_FULFILMENT_AND_PAID_CYCLE_SENSITIVITY")
    if any(x["cash_collection_lag_days_assumed"]>=horizon for x in normalized):
        action("PROTECT_CASH_CYCLE","finance",
               "CASH_COLLECTION_LAG_EXCEEDS_OR_MEETS_PILOT_HORIZON",
               "TEST_EARLIER_ACCEPTED_PAYOUT_TERMS_AND_REAL_COST_COVERAGE")
    action("MEASURE_CUSTOMER_VALUE","customer_success_analytics",
           "CUSTOMER_SAVINGS_AND_RETENTION_NOT_VERIFIED",
           "COLLECT_CONSENTED_BASELINE_REFUNDS_NEGATIVE_OUTCOMES_AND_FOLLOWUP")
    action("REASSESS_COMPETITIVE_MARKET","market_intelligence",
           "PRICING_AND_DEMAND_SCENARIOS_UNCALIBRATED",
           "VALIDATE_COMPETITOR_PRICE_SEARCH_INTENT_AND_BUYER_WILLINGNESS_TO_PAY")
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY",
        "opportunity_key":pilot["opportunity_key"],
        "original_pilot_design_revision_matched":True,
        "scenario_set_exhaustive_or_calibrated":False,
        "currency":currency,"product_type":kind,
        "horizon_days":horizon,
        "scenario_rows":sorted(normalized,key=lambda row:VARIANTS.index(row["scenario_key"])),
        "hypothetical_weighted_gross_profit_minor":round(weighted_gp,4),
        "hypothetical_weighted_operating_profit_minor":round(weighted_op,4),
        "hypothetical_worst_operating_profit_minor":round(worst,4),
        "hypothetical_robust_operating_profit_minor":round(robust,4),
        "hypothetical_max_cash_outflow_before_collection_minor":round(max_cost,4),
        "cash_upper_bound_assumes_all_attempts_convert_before_any_collection":True,
        "assumed_cash_limit_minor":budget,
        "worst_case_cash_exposure_above_assumed_limit":worst_cash_over_budget,
        "playbooks":playbooks,
        "uses_existing_quant_economics":True,
        "playbooks_are_agent_execution_authority":False,
        "modeled_profit_is_recognized_revenue":False,
        "original_forecast_registered":False,
        "actual_gross_profit_verified":False,
        "economic_memory_learning_performed":False,
        "outbound_sent":False,"spend_authorized":False,
        "database_writes":False,"execution_authority":"none",
    }


def build_profitability_scenario_portfolio(
    books: Sequence[Mapping[str,Any]], *, budget_minor: int,
    risk_aversion: float, capacity_by_group: Mapping[str,int],
) -> dict[str,Any]:
    """Use canonical scenario optimizer for decision support only.

    Each book is a reviewed, uncalibrated scenario output. All book currency,
    cohort horizon and scenario weights must match. Funds reserve is the
    scenario cash exposure; scenario objective values are already net costs.
    """
    if not isinstance(books,(list,tuple)) or not 1<=len(books)<=16:
        raise ValueError("bounded already-reviewed scenario books required")
    _num(budget_minor,"portfolio cash cap",hi=MAX_MINOR,integer=True)
    _fraction(risk_aversion,"portfolio risk aversion")
    if not isinstance(capacity_by_group,Mapping):
        raise ValueError("explicit capacity constraint inventory required")
    for group,count in capacity_by_group.items():
        if not isinstance(group,str) or not KEY.fullmatch(group) or type(count) is not int or count<0:
            raise ValueError("bounded explicit capacity group required")
    base=books[0]
    currency=base.get("currency")
    horizon=base.get("horizon_days")
    if currency not in ("USD","GBP","EUR") or type(horizon) is not int:
        raise ValueError("valid common currency and horizon required")
    actions=[]
    seen=set()
    common_weights=None
    for book in books:
        if (not isinstance(book,Mapping)
                or book.get("schema_version")!=SCHEMA
                or book.get("status")!="HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY"
                or book.get("execution_authority")!="none"
                or book.get("original_forecast_registered") is not False
                or book.get("currency")!=currency
                or book.get("horizon_days")!=horizon):
            raise ValueError("mixed cohort, currency or untrusted scenario book")
        key=book.get("opportunity_key")
        if not isinstance(key,str) or not KEY.fullmatch(key) or key in seen:
            raise ValueError("valid unique opportunity key required")
        seen.add(key)
        scenarios=book.get("scenario_rows")
        if not isinstance(scenarios,list) or len(scenarios)!=3:
            raise ValueError("exact source scenario set needed")
        bykey={x["scenario_key"]:x for x in scenarios}
        if set(bykey)!=set(VARIANTS):
            raise ValueError("complete original scenario states needed")
        weights=tuple(bykey[v]["weight_hypothetical"] for v in VARIANTS)
        if common_weights is None:
            common_weights=weights
        if weights!=common_weights:
            raise ValueError("different hypothetical scenario weights cannot be pooled")
        group="commercial_delivery"  # shared existing operations capacity, not new seats
        if group not in capacity_by_group:
            raise ValueError("explicit commercial_delivery capacity required")
        actions.append({
            "action_key":key.replace(":","_"),
            "action_cost_cents":ceil(book["hypothetical_max_cash_outflow_before_collection_minor"]),
            "scenario_values_cents":{
                v:bykey[v]["expected_operating_profit_minor_hypothetical"]
                for v in VARIANTS
            },
            "capacity_group":group,
            "evidence_refs":[f"hypothesis:{key}", "hypothetical:scenario_book_only"],
        })
    scenario_defs=[
        {"scenario_key":v,"probability":common_weights[i],
         "evidence_refs":[f"hypothetical:{v}"]}
        for i,v in enumerate(VARIANTS)
    ]
    result=build_predictive_cloud_scenario_problem(
        scenarios=scenario_defs,actions=actions,
        budget_cents=budget_minor,capacity_constraints=capacity_by_group,
        risk_aversion=risk_aversion,
    )
    # Already net operating profits: the action_cost field is solely an
    # exposure/budget constraint, NOT to be deducted from objective again.
    result["scenario_values_already_net_operating_costs"]=True
    result["scenario_probabilities_calibrated"]=False
    result["capital_approval_granted"]=False
    result["spend_execution"]=False
    result["recognized_gross_profit"]=False
    result["execution_authority"]="none"
    return result


def review_profitability_research_value(
    book: Mapping[str,Any], *,
    improved_operating_profit_minor_hypothesis: float,
    research_cost_minor_hypothesis: float,
    probability_research_changes_decision_hypothesis: float,
) -> dict[str,Any]:
    """Reuse original Quant value-of-information to prioritize more evidence."""
    if (not isinstance(book,Mapping)
            or book.get("schema_version")!=SCHEMA
            or book.get("status")!="HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY"
            or book.get("original_forecast_registered") is not False
            or book.get("execution_authority")!="none"):
        raise ValueError("safe hypothetical book required before information evaluation")
    current=book.get("hypothetical_robust_operating_profit_minor")
    if type(current) not in (int,float) or not -10**13<=current<=10**13:
        raise ValueError("bounded original robust operating scenario required")
    updated=improved_operating_profit_minor_hypothesis
    if type(updated) not in (int,float) or not -10**13<=updated<=10**13:
        raise ValueError("bounded improved hypothetical decision outcome required")
    expense=_num(research_cost_minor_hypothesis,"research cost",hi=MAX_MINOR)
    p=_fraction(probability_research_changes_decision_hypothesis,"decision change chance")
    value=value_of_information(
        current_expected_value_cents=current,
        informed_expected_value_cents=updated,
        information_cost_cents=expense,
        probability_information_changes_decision=p,
    )
    return {
        "schema_version":"empire.predictive_revenue.profitability_research_voi.v1",
        "status":"HYPOTHETICAL_VALUE_OF_INFORMATION_ONLY",
        "mode":"OBSERVE","opportunity_key":book["opportunity_key"],
        "research_net_information_value_minor_hypothetical":value["net_value_of_information_cents"],
        "research_gross_information_value_minor_hypothetical":value["gross_value_of_information_cents"],
        "research_worth_exploring_hypothetical":value["worth_collecting"],
        "uses_existing_quant_value_of_information":True,
        "research_probability_calibrated":False,
        "budget_or_research_execution_authorized":False,
        "verified_profit_or_conversions":False,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }


SENSITIVITY_FIELDS = frozenset((
    "unit_price_minor", "qualified_attempts", "conversion_rate",
    "refund_rate", "paid_cycle_retention_rate",
    "fulfilment_cost_per_paid_cycle_minor", "payment_fee_per_paid_cycle_minor",
    "acquisition_cost_per_attempt_minor", "fixed_pilot_cost_minor",
    "operating_overhead_minor", "cash_collection_lag_days",
))


def review_profitability_sensitivities(
    pilot: Mapping[str,Any],
    plan: Mapping[str,Any],
    shocks: Sequence[Mapping[str,Any]], *,
    as_of: datetime,
) -> dict[str,Any]:
    """Recompute the FULL scenario book per shock; don't sum noncausal deltas."""
    if not isinstance(shocks,(list,tuple)) or not 1<=len(shocks)<=12:
        raise ValueError("bounded explicit scenario perturbations required")
    base=review_profitability_playbook(pilot,plan,as_of=as_of)
    seen=set()
    results=[]
    for shock in shocks:
        if not isinstance(shock,Mapping) or set(shock)!={
            "shock_key","field","proposed_value","assumption_status",
        }:
            raise ValueError("exact what-if sensitivity contract required")
        key=shock["shock_key"]
        field=shock["field"]
        if not isinstance(key,str) or not KEY.fullmatch(key) or key in seen:
            raise ValueError("unique typed scenario hypothesis key required")
        if not isinstance(field,str) or field not in SENSITIVITY_FIELDS:
            raise ValueError("only original explicit unit economics factors can be changed")
        if shock["assumption_status"]!="HYPOTHETICAL_UNCALIBRATED":
            raise ValueError("cannot promote a what-if shock to an observed market response")
        seen.add(key)
        changed={
            **plan,
            "scenarios":[{**scenario,field:shock["proposed_value"]}
                         for scenario in plan["scenarios"]],
        }
        scenario_review=review_profitability_playbook(pilot,changed,as_of=as_of)
        results.append({
            "shock_key":key,
            "changed_assumption_field":field,
            "hypothetical_weighted_operating_profit_minor":
                scenario_review["hypothetical_weighted_operating_profit_minor"],
            "hypothetical_delta_operating_profit_minor":round(
                scenario_review["hypothetical_weighted_operating_profit_minor"]
                -base["hypothetical_weighted_operating_profit_minor"],4,
            ),
            "hypothetical_worst_operating_profit_minor":
                scenario_review["hypothetical_worst_operating_profit_minor"],
            "cash_stress_exceeds_assumed_cap":
                scenario_review["worst_case_cash_exposure_above_assumed_limit"],
            "interactions_or_causal_uplift_verified":False,
        })
    return {
        "schema_version":"empire.predictive_revenue.profitability_sensitivity.v1",
        "status":"INDEPENDENT_WHAT_IF_RECOMPUTATIONS_ONLY",
        "mode":"OBSERVE", "opportunity_key":base["opportunity_key"],
        "original_pilot_design_revision_matched":True,
        "baseline_weighted_operating_profit_minor_hypothetical":
            base["hypothetical_weighted_operating_profit_minor"],
        "shocks":results,
        "shock_deltas_can_be_added":False,
        "single_shock_effect_is_a_causal_effect":False,
        "economic_results_are_authenticated":False,
        "automatic_price_or_spend_change":False,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
