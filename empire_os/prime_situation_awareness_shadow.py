"""Original EmpireOS PRIME: provenance-first contextual situation review.

An Alexa-class *capability coverage plan*, not a claim of consciousness, a
functioning smart-home integration, autonomous operation or omniscience.
All data is caller-supplied metadata. No raw transcript, actual user profile,
device address, location, contact, model calls or external side effects.
Reuses the existing EmpireOS AGI capability and scoped memory contracts.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
import re

from empire_os.agi_capabilities import capability_registry, review_capability_request
from empire_os.agi_memory import build_memory_query

SCHEMA = "empire.prime.situation_awareness_shadow.v1"
MAX_OBSERVATIONS = 24
MAX_AGE = timedelta(days=7)
FINGERPRINT = re.compile(r"^[a-f0-9]{64}$")
CASE_KEY = re.compile(r"^[a-z][a-z0-9_-]{2,55}$")

# Existing original capabilities are referenced, never registered by this module.
# None means an unimplemented or unverified integration, NOT a permission grant.
REQUEST_CAPABILITY: dict[str, str | None] = {
    "ASK_INFORMATION": "evidence.read",
    "WORLD_STATUS": "world_model.read",
    "FORECAST_REVIEW": "forecast.preview",
    "SIMULATE_SCENARIO": "simulation.preview",
    "VOICE_DIALOGUE": None,
    "WEATHER_STATUS": None,
    "TIMER_OR_ALARM": None,
    "PERSONAL_REMINDER": None,
    "CALENDAR_CHECK": None,
    "MEDIA_PLAYBACK": None,
    "SMART_HOME_CONTROL": None,
    "AUTOMATED_ROUTINE": None,
    "MESSAGE_SEND": None,
    "OUTBOUND_CALL": "voice.call",
    "BUYER_CONVERSATION_REVIEW": "evidence.read",
    "PAYMENT_REQUEST": "payment.move",
    "INFRASTRUCTURE_CHANGE": "infrastructure.change",
    "SAFETY_EMERGENCY": None,
}
VOICE_SURFACE = frozenset({
    "VOICE_DIALOGUE", "TIMER_OR_ALARM", "PERSONAL_REMINDER",
    "MEDIA_PLAYBACK", "SMART_HOME_CONTROL", "AUTOMATED_ROUTINE",
    "OUTBOUND_CALL", "WEATHER_STATUS", "CALENDAR_CHECK",
})
SIDE_EFFECTS = frozenset({
    "TIMER_OR_ALARM", "PERSONAL_REMINDER", "MEDIA_PLAYBACK",
    "SMART_HOME_CONTROL", "AUTOMATED_ROUTINE", "MESSAGE_SEND",
    "OUTBOUND_CALL", "PAYMENT_REQUEST", "INFRASTRUCTURE_CHANGE",
})
SIGNAL_CODES = frozenset({
    "USER_EXPLICIT_REQUEST", "VOICE_AVAILABILITY", "WORLD_EVENT",
    "ENVIRONMENT_STATE", "DEVICE_STATE", "SCHEDULE_STATE",
    "MEDIA_STATE", "BUSINESS_SIGNAL", "SOURCE_HEALTH",
    "SIMULATED_OUTCOME", "SAFETY_ALERT",
})
SOURCE_CODES = frozenset({
    "USER_DECLARATION", "ORIGINAL_VOICE_LAB", "ORIGINAL_DIGITAL_TWIN",
    "ORIGINAL_PRIME", "ORIGINAL_ASTRA", "ORIGINAL_COMMERCE",
    "EXTERNAL_PROVIDER_UNVERIFIED",
})
OBS_FIELDS = frozenset({
    "signal_code", "source_code", "observation_fingerprint",
    "observed_at", "assertion", "synthetic", "purpose_reviewed",
})
SOURCE_AGED_REQUESTS = frozenset({
    "WORLD_STATUS", "WEATHER_STATUS", "SMART_HOME_CONTROL",
    "SAFETY_EMERGENCY", "CALENDAR_CHECK", "BUYER_CONVERSATION_REVIEW",
    "PAYMENT_REQUEST",
})


def _timestamp(value: Any) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise ValueError("bounded_original_situation_timestamp_required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise ValueError("invalid_original_situation_timestamp") from None
    if dt.utcoffset() is None:
        raise ValueError("timezone_aware_original_situation_timestamp_required")
    return dt.astimezone(timezone.utc)


def _freshness(observed: datetime, now: datetime, request_code: str) -> str:
    age = now - observed
    if age < -timedelta(minutes=5):
        raise ValueError("future_situation_evidence_refused")
    if age > MAX_AGE:
        return "EXPIRED"
    limit = timedelta(minutes=5) if request_code in {
        "SAFETY_EMERGENCY", "SMART_HOME_CONTROL",
    } else timedelta(minutes=15) if request_code in SOURCE_AGED_REQUESTS else timedelta(days=1)
    return "CURRENT_AGE_ONLY" if age <= limit else "STALE"


def review_prime_situation(
    *, situation_key: str, request_code: str, observations: Sequence[Mapping[str, Any]] | None,
    as_of: datetime,
) -> dict[str, Any]:
    """Non-mutating, context-aware request plan; never authenticates source data.

    The output cannot be passed to a live executor as permission. It reports
    facts as *claims*, contradiction/age risk and original-authority blockers.
    """
    if type(situation_key) is not str or CASE_KEY.fullmatch(situation_key) is None:
        raise ValueError("bounded_nonpersonal_situation_key_required")
    if type(request_code) is not str or request_code not in REQUEST_CAPABILITY:
        raise ValueError("known_original_situation_request_code_required")
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("timezone_aware_situation_review_clock_required")
    if observations is not None and (type(observations) not in (tuple, list)
                                     or len(observations) > MAX_OBSERVATIONS):
        raise ValueError("bounded_situation_observation_collection_required")
    now = as_of.astimezone(timezone.utc)
    seen: set[str] = set()
    by_signal: dict[str, set[str]] = {}
    ages: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    for observation in observations or ():
        if type(observation) is not dict or set(observation) != OBS_FIELDS:
            raise ValueError("exact_privacy_minimal_situation_observation_required")
        code = observation["signal_code"]
        source = observation["source_code"]
        token = observation["observation_fingerprint"]
        assertion = observation["assertion"]
        if type(code) is not str or code not in SIGNAL_CODES:
            raise ValueError("known_situation_signal_type_required")
        if type(source) is not str or source not in SOURCE_CODES:
            raise ValueError("known_original_source_class_required")
        if type(token) is not str or FINGERPRINT.fullmatch(token) is None or token in seen:
            raise ValueError("opaque_purpose_scoped_nonreplayed_signal_fingerprint_required")
        if assertion not in ("PRESENT", "ABSENT") or type(assertion) is not str:
            raise ValueError("explicit_observed_assertion_required")
        if type(observation["synthetic"]) is not bool or type(observation["purpose_reviewed"]) is not bool:
            raise ValueError("explicit_source_metadata_boolean_required")
        if source == "ORIGINAL_DIGITAL_TWIN" and observation["synthetic"] is not True:
            raise ValueError("original_digital_twin_cannot_prove_live_situation")
        when = _timestamp(observation["observed_at"])
        age = _freshness(when, now, request_code)
        seen.add(token)
        ages[age] += 1
        sources[source] += 1
        labels["SYNTHETIC" if observation["synthetic"] else "DECLARED_UNAUTHENTICATED"] += 1
        if not observation["purpose_reviewed"]:
            labels["PURPOSE_HOLD"] += 1
        # Contradiction checks are source CLAIM consistency, never lie detection.
        if age != "EXPIRED":
            by_signal.setdefault(code, set()).add(assertion)
    contradictions = sorted(k for k, values in by_signal.items() if len(values) > 1)
    n = len(seen)
    cap = REQUEST_CAPABILITY[request_code]
    registry = {c["key"] for c in capability_registry()["capabilities"]}
    if cap is not None and cap not in registry:
        raise ValueError("original_agi_capability_registry_changed")
    # Deliberately grant NOTHING. This is a capability RESEARCH map, never a
    # new routing, approval or production authorization surface.
    authority = review_capability_request({
        "agent_id": "original_prime_situation_shadow",
        "capability": cap or "__unregistered_assistant_feature__",
        "authority_mode": "OBSERVE",
        "approval_present": False,
        "granted_capabilities": [],
    })
    blockers: list[str] = []
    if observations is None:
        blockers.append("SOURCE_NOT_CONNECTED_UNKNOWN_NOT_ZERO")
    elif not n:
        blockers.append("NO_OBSERVATIONS_UNKNOWN_NOT_NEGATIVE")
    if n and ages["CURRENT_AGE_ONLY"] == 0:
        blockers.append("NO_CURRENT_SOURCE_CLAIMS")
    if ages["STALE"] or ages["EXPIRED"]:
        blockers.append("STALE_OR_EXPIRED_SOURCE_CLAIMS")
    if labels["PURPOSE_HOLD"]:
        blockers.append("SOURCE_PURPOSE_NOT_REVIEWED")
    if contradictions:
        blockers.append("CONTRADICTORY_SOURCE_CLAIMS_REQUIRE_REVIEW")
    if n:
        blockers.append("INDEPENDENT_SOURCE_AUTHENTICATION_NOT_PROVIDED")
    if cap is None:
        blockers.append("FEATURE_NOT_REGISTERED_OR_CONNECTED_IN_ORIGINAL_AGI")
    if request_code in SIDE_EFFECTS:
        blockers.append("ORIGINAL_OWNER_ACTION_PERMISSION_REQUIRED")
    if request_code == "SAFETY_EMERGENCY":
        blockers.append("HUMAN_EMERGENCY_RESPONSE_NOT_REPLACED_BY_SIMULATION")
    blockers.extend("CAPABILITY_" + s for s in authority["blockers"])
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SITUATION_CONTEXT_REVIEW_HOLD",
        "request_code": request_code,
        "source_attestation_verified_by_this_module": False,
        "capability_in_original_registry": cap is not None,
        "original_capability_key": cap,
        "capability_permission_observed": False,
        "feature_connected_to_real_world_tools": False,
        "claims_received_count_not_verified_events": n if observations is not None else None,
        "age_counts": {k: ages[k] for k in ("CURRENT_AGE_ONLY", "STALE", "EXPIRED")},
        "source_classes": sorted(sources),
        "synthetic_claim_count": labels["SYNTHETIC"],
        "declared_unauthenticated_claim_count": labels["DECLARED_UNAUTHENTICATED"],
        "contradictory_signal_codes_not_lie_detection": contradictions,
        "missing_information_or_authority": blockers,
        "memory_query_plan": build_memory_query(
            task_type="research" if request_code in ("ASK_INFORMATION", "WEATHER_STATUS",
                    "WORLD_STATUS", "FORECAST_REVIEW", "SIMULATE_SCENARIO") else "planning",
            task_id="original_prime_situation_review_" + situation_key,
            topic_keys=(request_code.lower(),),
            max_items_per_type=5,
        ),
        "voice_assistant_feature_class": request_code in VOICE_SURFACE,
        "universal_awareness_or_consciousness_claim": False,
        "action_performed": False,
        "real_data_verified": False,
        "real_customer_intent_verified": False,
        "model_training": False,
        "outbound_sent": False,
        "payment_executed": False,
        "smart_home_command_sent": False,
        "original_empiredb_writes": False,
        "execution_authority": "none",
    }


def founder_situation_status(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Only request readiness and blockers; no source event refs or private detail."""
    if value is None:
        return {
            "schema_version": "empire.prime.founder_situation_awareness.v1",
            "status": "NOT_CONNECTED", "mode": "OBSERVE",
            "consciousness_claim": False, "execution_authority": "none",
        }
    if (type(value) is not dict or value.get("schema_version") != SCHEMA
        or value.get("status") != "SITUATION_CONTEXT_REVIEW_HOLD"
        or value.get("execution_authority") != "none"
        or value.get("capability_permission_observed") is not False
        or value.get("action_performed") is not False
        or value.get("source_attestation_verified_by_this_module") is not False
        or value.get("feature_connected_to_real_world_tools") is not False
        or value.get("real_data_verified") is not False
        or value.get("universal_awareness_or_consciousness_claim") is not False
        or value.get("outbound_sent") is not False
        or value.get("model_training") is not False
        or value.get("payment_executed") is not False
        or value.get("smart_home_command_sent") is not False
        or value.get("original_empiredb_writes") is not False):
        raise ValueError("untrusted_original_prime_situation_authority")
    request = value.get("request_code")
    missing = value.get("missing_information_or_authority")
    ages = value.get("age_counts")
    if (request not in REQUEST_CAPABILITY
        or value.get("capability_in_original_registry") is not (REQUEST_CAPABILITY.get(request) is not None)
        or value.get("original_capability_key") != REQUEST_CAPABILITY.get(request)
        or type(missing) is not list or not missing
        or len(missing) > 20 or any(type(x) is not str or len(x) > 96 for x in missing)
        or type(ages) is not dict
        or set(ages) != {"CURRENT_AGE_ONLY", "STALE", "EXPIRED"}
        or any(type(v) is not int or not 0 <= v <= MAX_OBSERVATIONS for v in ages.values())):
        raise ValueError("untrusted_original_situation_projection_schema")
    return {
        "schema_version": "empire.prime.founder_situation_awareness.v1",
        "mode": "OBSERVE",
        "status": "REQUIRES_REAL_SOURCE_AND_OWNER_GATES",
        "request_code": request,
        "original_capability_registered": REQUEST_CAPABILITY[request] is not None,
        "missing_information_or_authority": list(missing),
        "age_counts_not_verified_events": dict(ages),
        "consciousness_claim": False,
        "real_world_capability_live": False,
        "execution_authority": "none",
    }
