"""Before/after customer-value observation preflight for Predictive pilots.

Aggregates only bounded, pseudonymous source-owner measurement *claims*.
Protects the original pilot metric, baseline chronology, missing pairs and
holdout arms; never certifies causal lift, customer time saved, monetary
benefit, consent, real-world identity or verified conversion accuracy.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping, Sequence

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_customer_value_commerce_evidence import (
    SHA256, REUSE_SCOPE, _validated_pilot,
)

SCHEMA = "empire.predictive.customer_value_measurement_evidence.v1"
MAX_ROWS = 500
UNITS = {
    "verified_acquisition_cost_per_accepted_customer": "minor_cash",
    "verified_sales_conversion_from_inbound": "basis_points",
    "verified_qualified_search_traffic": "count",
    "monthly_task_minutes": "minutes",
    "decision_quality_against_holdout": "basis_points",
    "incremental_paid_net_revenue": "minor_cash",
    "time_to_accepted_service": "minutes",
}
FIELDS = frozenset((
    "tenant_ref_sha256", "pilot_design_sha256", "cohort_slot_sha256",
    "source_measurement_sha256", "source_owner", "reuse_scope",
    "evidence_status", "arm", "phase", "metric", "unit",
    "value", "observed_at", "evidence_available_at",
))
SOURCE_STATE = "SOURCE_OWNER_REPORTED_UNAUTHENTICATED"


def _measure(value: Any, unit: str) -> float:
    if type(value) not in (int, float) or not -1e10 <= value <= 1e10:
        raise ValueError("bounded original measurement needed")
    if not isfinite(value):
        raise ValueError("only finite original source-owner values")
    if unit != "minor_cash" and value < 0:
        raise ValueError("negative counts/rates/time not allowed")
    if unit in ("minutes","count","minor_cash") and type(value) is not int:
        raise ValueError("integer base measurement unit required")
    if unit == "basis_points" and not 0 <= value <= 10000:
        raise ValueError("bounded basis point percentage required")
    return float(value)


def review_customer_value_measurement_evidence(
    pilot: Mapping[str, Any],
    measurements: Sequence[Mapping[str, Any]], *,
    tenant_ref_sha256: str,
    as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware trusted measurement review clock required")
    now = as_of.astimezone(timezone.utc)
    if not isinstance(tenant_ref_sha256, str) or not SHA256.fullmatch(tenant_ref_sha256):
        raise ValueError("opaque tenant custody ref required")
    start,end = _validated_pilot(pilot,now)
    if not isinstance(measurements,(list,tuple)) or len(measurements)>MAX_ROWS:
        raise ValueError("bounded source-owner value measurements required")
    metric=pilot.get("primary_value_measure")
    if not isinstance(metric,str) or metric not in UNITS:
        raise ValueError("unsupported original metric unit contract")
    unit=UNITS[metric]
    comparison=pilot.get("comparison_mode")
    if comparison not in ("randomized_holdout","observational_before_after"):
        raise ValueError("unknown prospective comparison method")
    days=pilot.get("planned_baseline_window_days")
    if type(days) is not int or not 7<=days<=90:
        raise ValueError("bounded original baseline interval required")

    source_ids=set()
    pairs: dict[str,dict[str,Any]]={}
    for row in measurements:
        if not isinstance(row, Mapping) or set(row)!=FIELDS:
            raise ValueError("typed bounded source-value receipt required")
        if (row["tenant_ref_sha256"]!=tenant_ref_sha256
                or row["pilot_design_sha256"]!=pilot["design_revision_sha256"]):
            raise ValueError("measurement tenant or pilot revision mismatch")
        for key in ("source_measurement_sha256","cohort_slot_sha256"):
            value=row[key]
            if not isinstance(value,str) or not SHA256.fullmatch(value):
                raise ValueError("opaque measurement and participant ref required")
        measurement_id=row["source_measurement_sha256"]
        if measurement_id in source_ids:
            raise ValueError("replayed customer measurement source event")
        source_ids.add(measurement_id)
        if (row["source_owner"]!="customer_success_analytics"
                or row["reuse_scope"]!=REUSE_SCOPE
                or row["evidence_status"]!=SOURCE_STATE):
            raise ValueError("source authority and aggregate research rights required")
        if row["metric"]!=metric or row["unit"]!=unit:
            raise ValueError("changed metric/unit would bias original experiment")
        arm=row["arm"]
        phase=row["phase"]
        if arm not in ("treatment","control") or phase not in ("baseline","followup"):
            raise ValueError("named experimental arm and observation phase required")
        if comparison=="observational_before_after" and arm!="treatment":
            raise ValueError("observational design cannot add a post-hoc control group")
        observed=_time(row["observed_at"])
        available=_time(row["evidence_available_at"])
        if not observed<=available<=now:
            raise ValueError("future/backfilled availability cannot support measurements")
        if phase=="baseline" and not start-timedelta(days=days)<=observed<start:
            raise ValueError("baseline must be in the original preceding interval")
        if phase=="followup" and not start<=observed<=end:
            raise ValueError("followup must be inside original prospective horizon")
        value=_measure(row["value"],unit)
        slot=row["cohort_slot_sha256"]
        item=pairs.setdefault(slot,{"arm":arm})
        if item["arm"]!=arm or phase in item:
            raise ValueError("participant changed experimental arm or duplicated phase")
        item[phase]=value

    completed=defaultdict(list)
    missing=0
    for slot in pairs.values():
        if not ("baseline" in slot and "followup" in slot):
            missing+=1
            continue
        completed[slot["arm"]].append(slot["followup"]-slot["baseline"])
    def average(values: list[float]) -> float | None:
        return round(sum(values)/len(values),6) if values else None
    treatment=average(completed["treatment"])
    control=average(completed["control"])
    comparison_delta=(
        round(treatment-control,6)
        if comparison=="randomized_holdout"
        and treatment is not None and control is not None
        else None
    )
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"CUSTOMER_VALUE_MEASUREMENT_CLAIMS_RECONCILED_UNAUTHENTICATED",
        "original_pilot_revision_matched":True,
        "primary_metric":metric,"unit":unit,
        "comparison_mode":comparison,
        "source_measurement_receipts":len(measurements),
        "claimed_distinct_cohort_slots":len(pairs),
        "complete_treatment_pairs":len(completed["treatment"]),
        "complete_control_pairs":len(completed["control"]),
        "unpaired_slots":missing,
        "claimed_treatment_signed_change_unverified":treatment,
        "claimed_control_signed_change_unverified":control,
        "claimed_between_arm_delta_unverified_not_causal":comparison_delta,
        "source_owner_authenticated":False,
        "cohort_identity_or_consent_verified":False,
        "cohort_completeness_verified":False,
        "randomization_verified":False,
        "baseline_was_prospectively_registered":False,
        "original_quant_forecast_registered":False,
        "source_measurements_independently_authenticated":False,
        "negative_customer_outcomes_completely_observed":False,
        "time_or_cash_saved_verified":False,
        "causal_lift_verified":False,
        "customer_value_calibration_ready":False,
        "economic_memory_outcome_write":False,
        "next_owner":"customer_success_analytics_and_original_quant_registry",
        "next_action":"VERIFY_CONSENT_REAL_MEASUREMENTS_ORIGINAL_BASELINE_AND_REGISTERED_FORECAST",
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
