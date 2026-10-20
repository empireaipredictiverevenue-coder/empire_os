"""Prospective profitability forecast declaration, NOT a registered forecast.

Original Quant conversion registry is typed for conversion_probability only.
A hypothetical operating-profit scenario needs a separate original immutable
profit forecast and later independent finance outcome custody. This preflight
creates only a deterministic declaration and content digest for source-owner
review. It cannot register a conversion forecast as a profit forecast.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
import json
from typing import Any,Mapping

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_customer_value_pilot_preflight import SCHEMA as PILOT_SCHEMA
from empire_os.predictive_profitability_playbooks import (
    review_profitability_playbook, SCHEMA as PROFIT_SCHEMA,
)
from empire_os.predictive_four_stage_economic_custody import SCHEMA as COST_SCHEMA

SCHEMA="empire.predictive_revenue.original_profit_forecast_preflight.v1"


def prepare_original_profit_forecast_preflight(
    pilot:Mapping[str,Any],
    economic_plan:Mapping[str,Any],
    four_stage_source_review:Mapping[str,Any],
    *,
    as_of:datetime,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware prospective original forecast time required")
    now=as_of.astimezone(timezone.utc)
    if (not isinstance(pilot,Mapping)
            or pilot.get("schema_version")!=PILOT_SCHEMA
            or pilot.get("status")!="PROSPECTIVE_VALUE_PILOT_DESIGN_UNREGISTERED"
            or pilot.get("original_quant_forecast_registered") is not False
            or pilot.get("prospective_design_durably_registered") is not False):
        raise ValueError("original unregistered prospective pilot required")
    start,end=_time(pilot.get("planned_pilot_start_at")),_time(pilot.get("planned_pilot_end_at"))
    if not now<start<end:
        raise ValueError("profit declaration must precede original experiment start")
    source=four_stage_source_review
    if (not isinstance(source,Mapping)
            or source.get("schema_version")!=COST_SCHEMA
            or source.get("status")!="FOUR_STAGE_ECONOMIC_SOURCE_CUSTODY_REVIEWED"
            or source.get("original_opportunity_key")!=pilot.get("opportunity_key")
            or source.get("original_pilot_design_sha256")!=pilot.get("design_revision_sha256")
            or source.get("actual_revenue_minor") is not None
            or source.get("actual_gross_profit_minor") is not None
            or source.get("original_registered_before_outcome_forecast_authenticated") is not False
            or source.get("database_writes") is not False
            or source.get("execution_authority")!="none"):
        raise ValueError("source custody invalid or already promoted")
    base=review_profitability_playbook(pilot,economic_plan,as_of=now)
    if (base.get("schema_version")!=PROFIT_SCHEMA
            or base.get("status")!="HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY"
            or base.get("original_pilot_design_sha256")!=pilot["design_revision_sha256"]
            or base.get("opportunity_key")!=pilot["opportunity_key"]
            or base.get("original_forecast_registered") is not False
            or base.get("actual_gross_profit_verified") is not False
            or base.get("execution_authority")!="none"
            or base.get("spend_authorized") is not False):
        raise ValueError("hypothetical economics cannot substitute actual forecasting evidence")
    # This is an original INTENT declaration. Its SHA is only an integrity
    # marker, not a signed DB commit or proof that an event preceded outcomes.
    payload={
        "forecast_kind":"scenario_weighted_operating_profit_research",
        "original_opportunity_key":pilot["opportunity_key"],
        "original_pilot_design_sha256":pilot["design_revision_sha256"],
        "product_type":base.get("product_type"),
        "currency":base.get("currency"),
        "first_declared_at_utc":now.isoformat(),
        "original_experiment_start_at":start.isoformat(),
        "original_experiment_end_at":end.isoformat(),
        "hypothetical_weighted_operating_profit_minor":base.get(
            "hypothetical_weighted_operating_profit_minor"),
        "hypothetical_worst_operating_profit_minor":base.get(
            "hypothetical_worst_operating_profit_minor"),
        "source_unit_price_minor_claimed":source.get(
            "source_reported_offered_price_minor_per_unit"),
        "source_material_cost_minor_claimed":source.get(
            "selected_material_reference_cost_minor_unverified"),
        "source_labor_delivery_cost_minor_assumed":source.get(
            "estimated_fulfilment_cost_minor_per_unit"),
        "source_unit_contribution_minor_unverified":source.get(
            "illustrative_unit_contribution_minor_excluding_cac_fees_tax_overhead"),
        "hypothetical_costs_and_prices_not_independent_profit_evidence":True,
        "scenario_probabilities_calibrated":False,
        "actual_profit_outcome_known":False,
    }
    if (payload["currency"]!=source.get("source_currency")
            or not isinstance(payload["hypothetical_weighted_operating_profit_minor"],(int,float))):
        raise ValueError("original currency/profit numeric semantics mismatch")
    digest=sha256(json.dumps(
        payload,sort_keys=True,separators=(",",":"),allow_nan=False,
    ).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"PROSPECTIVE_PROFIT_FORECAST_SOURCE_DECLARATION_UNREGISTERED",
        "original_intended_forecast_sha256":digest,
        "proposed_original_profit_forecast":payload,
        "original_profit_forecast_registry_target":"MISSING_DEDICATED_PROFIT_FORECAST_OWNER_REGISTRY",
        "existing_conversion_probability_registry_is_suitable_profit_registry":False,
        "original_forecast_durably_registered":False,
        "independently_readback_prediction_verified":False,
        "source_pilot_tenant_and_cohort_authenticated":False,
        "forecast_dated_before_future_actual_outcome_authenticated":False,
        "supplier_invoice_and_wages_authenticated":False,
        "payment_refunds_costs_attributed_to_same_cohort":False,
        "actual_profit_outcome_minor":None,
        "original_profit_forecast_error_minor":None,
        "calibrated_profit_prediction_interval":None,
        "original_registration_required_before_outcomes":True,
        "future_required_reader_role":"existing_scientific_quant_and_finance_authorized_roles",
        "next_owner":"existing_scientific_quant_original_profit_registry_owner",
        "next_action":"DEFINE_DURABLE_PROFIT_FORECAST_REGISTRATION_AND_AUTHENTICATED_READBACK",
        "forecast_sent_or_registered":False,
        "model_training_authorized":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
