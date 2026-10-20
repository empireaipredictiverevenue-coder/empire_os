"""Cross-owner prospective revenue, GP and customer-outcome measurement gate.

Binds deterministic reviews from the EXISTING pilot, economic scenario, commerce,
customer value and original Quant registry owners. This adapter does not read
receipts or register forecasts and cannot independently authenticate source truth.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from math import isfinite

from empire_os.predictive_customer_value_pilot_preflight import SCHEMA as PILOT_SCHEMA
from empire_os.predictive_profitability_playbooks import SCHEMA as ECON_SCHEMA
from empire_os.predictive_customer_value_commerce_evidence import SCHEMA as COMMERCE_SCHEMA
from empire_os.predictive_customer_value_measurement_evidence import SCHEMA as VALUE_SCHEMA
from empire_os.predictive_customer_value_demand import _time

SCHEMA = "empire.predictive_revenue.profit_outcome_measurement_gate.v1"
REVIEW_SCHEMA = "empire.original_conversion_registry_readback_review.v1"
HOLD = (
    "PILOT_DESIGN_NOT_DURABLY_REGISTERED",
    "PROSPECTIVE_QUANT_FORECAST_NOT_AUTHENTICATED",
    "PILOT_TO_FORECAST_TENANT_AND_DESIGN_BINDING_NOT_AUTHENTICATED",
    "FORECAST_HORIZON_AND_OUTCOME_CHRONOLOGY_NOT_AUTHENTICATED",
    "PAID_SOURCE_SETTLEMENT_REFUNDS_AND_COSTS_NOT_AUTHENTICATED",
    "CUSTOMER_MEASUREMENT_CONSENT_CONTROL_AND_BASELINE_NOT_AUTHENTICATED",
    "ATTRIBUTED_PROFIT_AND_OUTCOME_PAIR_NOT_AVAILABLE",
)


def review_profit_outcome_instrument(
    pilot: Mapping[str, Any],
    scenario: Mapping[str, Any],
    commerce: Mapping[str, Any],
    customer_value: Mapping[str, Any],
    registry_readback: Mapping[str, Any],
    *, as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware review clock required")
    if any(not isinstance(row, Mapping)
           for row in (pilot, scenario, commerce, customer_value, registry_readback)):
        raise ValueError("original owner result packets required")
    if (pilot.get("schema_version") != PILOT_SCHEMA
            or pilot.get("status") != "PROSPECTIVE_VALUE_PILOT_DESIGN_UNREGISTERED"
            or pilot.get("execution_authority") != "none"
            or pilot.get("prospective_design_durably_registered") is not False
            or pilot.get("original_quant_forecast_registered") is not False
            or pilot.get("customer_savings_verified") is not False):
        raise ValueError("only original unregistered prospective pilot allowed")
    revision=pilot.get("design_revision_sha256")
    opportunity=pilot.get("opportunity_key")
    if (not isinstance(revision,str) or len(revision)!=64
            or any(c not in "0123456789abcdef" for c in revision)
            or not isinstance(opportunity,str) or len(opportunity)>150 or not opportunity):
        raise ValueError("original bounded design and opportunity identity required")
    start = _time(pilot.get("planned_pilot_start_at"))
    end = _time(pilot.get("planned_pilot_end_at"))
    if not start < end or end - start > timedelta(days=90):
        raise ValueError("original pilot planned horizon invalid")
    if (scenario.get("schema_version")!=ECON_SCHEMA
            or scenario.get("status")!="HYPOTHETICAL_PROFITABILITY_PLAYBOOK_READY"
            or scenario.get("opportunity_key")!=opportunity
            or scenario.get("original_pilot_design_sha256")!=revision
            or scenario.get("execution_authority")!="none"
            or scenario.get("original_forecast_registered") is not False
            or scenario.get("actual_gross_profit_verified") is not False
            or scenario.get("spend_authorized") is not False):
        raise ValueError("economic assumptions do not match original pilot or read-only policy")
    if (commerce.get("schema_version")!=COMMERCE_SCHEMA
            or commerce.get("status")!="OWNER_REPORTED_COMMERCE_EVIDENCE_RECONCILED_UNAUTHENTICATED"
            or commerce.get("original_pilot_design_revision_matched") is not True
            or commerce.get("tenant_authentication_proven") is not False
            or commerce.get("original_quant_forecast_registered") is not False
            or commerce.get("source_owner_authentication_proven") is not False
            or commerce.get("quant_calibration_ready") is not False
            or commerce.get("execution_authority")!="none"
            or commerce.get("database_writes") is not False):
        raise ValueError("untrusted or prematurely promoted commerce evidence")
    if (customer_value.get("schema_version")!=VALUE_SCHEMA
            or customer_value.get("status")!="CUSTOMER_VALUE_MEASUREMENT_CLAIMS_RECONCILED_UNAUTHENTICATED"
            or customer_value.get("original_pilot_revision_matched") is not True
            or customer_value.get("source_owner_authenticated") is not False
            or customer_value.get("cohort_identity_or_consent_verified") is not False
            or customer_value.get("original_quant_forecast_registered") is not False
            or customer_value.get("causal_lift_verified") is not False
            or customer_value.get("customer_value_calibration_ready") is not False
            or customer_value.get("execution_authority")!="none"
            or customer_value.get("database_writes") is not False
            or customer_value.get("primary_metric")!=pilot.get("primary_value_measure")):
        raise ValueError("untrusted or unmatched customer-value evidence")
    if (registry_readback.get("schema_version")!=REVIEW_SCHEMA
            or registry_readback.get("status") not in
                ("READBACK_HOLD","MATCHED_UNAUTHENTICATED_INPUT")
            or registry_readback.get("original_prediction_registered") is not False
            or registry_readback.get("immutable_registry_proven") is not False
            or registry_readback.get("eligible_for_calibration") is not False
            or registry_readback.get("execution_authority")!="none"):
        raise ValueError("untrusted registry attestation or false authority")

    def safe_count(report: Mapping[str,Any], key: str) -> int:
        value=report.get(key)
        if type(value) is not int or not 0<=value<=100_000:
            raise ValueError("bounded integer research source counter required")
        return value

    paid=safe_count(commerce,"claimed_paid_event_count")
    refunds=safe_count(commerce,"claimed_reversal_count")
    treat=safe_count(customer_value,"complete_treatment_pairs")
    control=safe_count(customer_value,"complete_control_pairs")
    unpaired=safe_count(customer_value,"unpaired_slots")
    observed_cash=commerce.get("source_reported_net_after_reversals_and_variable_cost_minor_unverified")
    if observed_cash is not None and (type(observed_cash) is not int
            or not -10**13<=observed_cash<=10**13):
        raise ValueError("bounded only unverified accounting estimate required")
    claimed_delta=customer_value.get("claimed_between_arm_delta_unverified_not_causal")
    if claimed_delta is not None and (type(claimed_delta) not in (int,float)
            or not isfinite(claimed_delta) or abs(claimed_delta)>1e10):
        raise ValueError("bounded only claimed treatment/control delta required")
    if commerce.get("source_reported_gross_minor_unverified") is None and paid:
        raise ValueError("paid records lack an original source owner amount")
    report={
        "schema_version":SCHEMA, "mode":"OBSERVE",
        "status":"PROSPECTIVE_PROFIT_AND_CUSTOMER_VALUE_EVIDENCE_GATES_REVIEWED",
        "original_opportunity_key":opportunity,
        "original_pilot_design_revision_sha256":revision,
        "planned_start_at":start.isoformat(),
        "planned_end_at":end.isoformat(),
        "source_assessment_clock":as_of.astimezone(timezone.utc).isoformat(),
        "registry_packet_status":registry_readback["status"],
        "registry_matching_dict_is_authenticated_db_attestation":False,
        "commerce_and_customer_value_summary_pilot_binding_independently_authenticated":False,
        "original_quant_registry_packet_has_cryptographic_pilot_design_binding":False,
        "buyer_and_purchase_source_custody_verified":False,
        "claimed_paid_event_count_not_verified_sales":paid,
        "claimed_reversal_count_not_verified_refunds":refunds,
        "claimed_net_after_refunds_and_variable_cost_minor_unverified":observed_cash,
        "claimed_paired_treatment_slots_unverified":treat,
        "claimed_paired_control_slots_unverified":control,
        "unpaired_source_cohort_slots":unpaired,
        "claimed_control_comparison_delta_unverified_not_causal":claimed_delta,
        "hypothetical_weighted_operating_profit_minor":scenario.get(
            "hypothetical_weighted_operating_profit_minor"),
        "hypothetical_profit_is_realised_gp":False,
        "measured_gross_profit_minor":None,
        "measured_operating_profit_minor":None,
        "measured_cash_saved_minor":None,
        "registered_original_profit_forecast_ref":None,
        "matched_original_forecast_and_outcome_pairs":None,
        "profit_prediction_error_minor":None,
        "conversion_brier_score":None,
        "scenario_probabilities_calibrated":False,
        "experiment_ran_or_randomized_verified":False,
        "controls_not_inferred_from_unpaired_observations":True,
        "remaining_measurement_proof_gates":list(HOLD),
        "next_owners":{
            "registered_original_forecast":"scientific_quant_original_registry",
            "authenticated_paid_outcomes":"commerce_billing_and_finance",
            "customer_baselines_and_holdouts":"customer_success_analytics",
            "profit_and_error_learning":"finance_and_economic_memory",
        },
        "model_calibration_authorized":False,
        "economic_memory_outcome_written":False,
        "business_action_authorized":False,
        "outbound_sent":False,
        "database_writes":False,
        "execution_authority":"none",
    }
    value=report["hypothetical_weighted_operating_profit_minor"]
    if type(value) not in (int,float) or not isfinite(value):
        raise ValueError("original bounded hypothetical economics required")
    return report
