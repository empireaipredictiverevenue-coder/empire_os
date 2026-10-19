"""Prospective customer-value measurement design, before observing pilot outcomes.

A deterministic design-only custody gate anchored to the source revision from
the existing Predictive customer-value/Radar bridge. This NEVER registers
a forecast, enrolls participants, claims causal lift, contacts a customer,
consumes private data, approves payments or rewrites Quant weights.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_customer_value_radar_bridge import SCHEMA as BRIDGE_SCHEMA

SCHEMA="empire.predictive.customer_value_prospective_pilot.v1"
HEX64=re.compile(r"^[0-9a-f]{64}$")
KEY=re.compile(r"^community_pain:[a-z][a-z0-9_]{2,63}$")
FIELDS=frozenset((
    "opportunity_key", "source_revision_fingerprint",
    "planned_start_at", "planned_end_at", "baseline_window_days",
    "planned_participants", "comparison_mode", "primary_measure",
    "commercial_measure", "negative_outcomes_recorded",
    "refunds_and_cancellations_recorded", "consent_required",
    "original_forecast_must_precede_outcomes",
))


def review_prospective_customer_value_pilot(
    source_bridge: Mapping[str, Any],
    design: Mapping[str, Any], *,
    as_of: datetime,
) -> dict[str, Any]:
    """Proof of bounded design coherence only, NEVER a pilot authorization."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware design review time required")
    if not isinstance(source_bridge, Mapping) or not isinstance(design, Mapping):
        raise ValueError("bridge and original experiment design required")
    if set(design) != FIELDS:
        raise ValueError("exact prospective pilot design contract required")
    if (source_bridge.get("schema_version") != BRIDGE_SCHEMA
            or source_bridge.get("status") != "CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED"
            or source_bridge.get("source_identity_aligned") is not True
            or source_bridge.get("prospective_original_quant_registered") is not False
            or source_bridge.get("execution_authority") != "none"):
        raise ValueError("source must come from safe current Radar bridge")
    key=design["opportunity_key"]
    rev=design["source_revision_fingerprint"]
    if (not isinstance(key,str) or not KEY.fullmatch(key)
            or not isinstance(rev,str) or not HEX64.fullmatch(rev)):
        raise ValueError("typed source key and revision required")
    matches=[
        item for item in source_bridge.get("research_cards",())
        if isinstance(item,Mapping) and item.get("opportunity_key")==key
    ]
    if len(matches)!=1 or matches[0].get("source_revision_fingerprint")!=rev:
        raise ValueError("experiment cannot attach to different or stale research revision")
    card=matches[0]
    if (design["primary_measure"]!=card["proposed_primary_value_metric"]
            or design["commercial_measure"]!=card["proposed_commercial_validation_metric"]):
        raise ValueError("value metrics must match frozen prospectively chosen evidence")
    if type(design["baseline_window_days"]) is not int or not 7<=design["baseline_window_days"]<=90:
        raise ValueError("bounded comparable baseline window required")
    if type(design["planned_participants"]) is not int or not 2<=design["planned_participants"]<=100000:
        raise ValueError("bounded intended cohort required")
    if design["comparison_mode"] not in ("randomized_holdout","observational_before_after"):
        raise ValueError("explicit valid comparison mode required")
    for flag in ("negative_outcomes_recorded","refunds_and_cancellations_recorded",
                 "consent_required","original_forecast_must_precede_outcomes"):
        if design[flag] is not True:
            raise ValueError("missing original pilot safety and anti-leakage precommitment")
    now=as_of.astimezone(timezone.utc)
    start=_time(design["planned_start_at"])
    end=_time(design["planned_end_at"])
    if not now < start < end <= now+timedelta(days=90):
        raise ValueError("pilot dates must be future and within 90 days")
    source_epoch=_time(source_bridge["source_radar_epoch"])
    if not timedelta(0)<=now-source_epoch<=timedelta(hours=6):
        raise ValueError("source Radar snapshot not current")
    proposal={k:design[k] for k in sorted(FIELDS)}
    digest=sha256(json.dumps(
        proposal,separators=(",",":"),sort_keys=True,allow_nan=False,
    ).encode()).hexdigest()
    return {
        "schema_version": SCHEMA,
        "status":"PROSPECTIVE_VALUE_PILOT_DESIGN_UNREGISTERED",
        "mode":"OBSERVE", "design_revision_sha256":digest,
        "opportunity_key":key,
        "original_research_revision_checked":True,
        "primary_value_measure":design["primary_measure"],
        "commercial_measure":design["commercial_measure"],
        "comparison_mode":design["comparison_mode"],
        "planned_participants_not_actual_enrollment":design["planned_participants"],
        "planned_baseline_window_days":design["baseline_window_days"],
        "planned_horizon_days":(end-start).total_seconds()/86400,
        "planned_pilot_start_at":start.isoformat(),
        "planned_pilot_end_at":end.isoformat(),
        "causal_impact_claim_approved":False,
        "bias_and_sample_power_evaluated":False,
        "customer_consent_verified":False,
        "customer_identity_authenticated":False,
        "customer_outcomes_collected":False,
        "customer_value_measured":False,
        "real_cost_and_margin_authenticated":False,
        "customer_savings_verified":False,
        "original_quant_forecast_registered":False,
        "original_forecast_probability":None,
        "original_outcome_feedback_verified":False,
        "model_calibration_performed":False,
        "prospective_design_durably_registered":False,
        "automatic_pilot_activation":False,
        "next_owner":"existing_predictive_quant_and_customer_success_owners",
        "next_action":"APPROVE_AND_DURABLY_REGISTER_PROSPECTIVE_BASELINE_THEN_RECRUIT_CONSENTED_COHORT",
        "outbound_sent":False, "database_writes":False,
        "execution_authority":"none",
    }
