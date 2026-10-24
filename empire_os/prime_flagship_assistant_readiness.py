"""Original EmpireOS: conservative flagship assistant/voice read-only release gate.

This is an evidence presentation and engineering preflight, not a deployment
approval, real-time runtime attestation, valuation, or execution capability.
All caller evidence is UNAUTHENTICATED at this layer; owner proof remains
independent. A green /health, available slot, or speech model file is NOT
evidence of reliable end-to-end AI voice task completion.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "empire.prime.original_flagship_assistant_readiness.v1"
FIELDS = frozenset({
    "local_model_health", "local_model_idle_slot", "bounded_inference_completed",
    "voice_dependencies_available", "voice_models_available",
    "legacy_voice_uses_supabase", "voice_route_empiredb_readback_verified",
    "private_founder_ingress_approved", "end_to_end_consent_voice_task_verified",
    "commercial_buyer_demand_and_payment_verified",
})
BOOLEAN_FIELDS = FIELDS


def review_flagship_assistant_readiness(
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed on unknown, incomplete, or incompatible evidence.

    Never promote caller booleans to authenticated original-owner proof or
    permission to operate any voice, household, outbound, financial or CRM
    system. The source is a non-authoritative readiness diagnostic only.
    """
    if evidence is None:
        observed: dict[str, bool | None] = {key: None for key in FIELDS}
    else:
        if type(evidence) is not dict or set(evidence) != FIELDS:
            raise ValueError("exact_original_flagship_evidence_fields_required")
        if any(type(evidence[key]) not in (bool, type(None)) for key in FIELDS):
            raise ValueError("tri_state_flagship_evidence_boolean_required")
        observed = dict(evidence)

    def present(name: str) -> bool:
        return observed[name] is True

    blockers: list[str] = []
    if not present("local_model_health"):
        blockers.append("MODEL_HEALTH_NOT_VERIFIED")
    if not present("local_model_idle_slot"):
        blockers.append("MODEL_CAPACITY_NOT_VERIFIED")
    if not present("bounded_inference_completed"):
        blockers.append("BOUNDED_GENERATION_NOT_VERIFIED")
    if not present("voice_dependencies_available"):
        blockers.append("ORIGINAL_SPEECH_DEPENDENCIES_NOT_VERIFIED")
    if not present("voice_models_available"):
        blockers.append("ORIGINAL_SPEECH_ASSETS_NOT_VERIFIED")
    if observed["legacy_voice_uses_supabase"] is True:
        blockers.append("LEGACY_VOICE_USES_NONCANONICAL_SUPABASE_PATH")
    elif observed["legacy_voice_uses_supabase"] is None:
        blockers.append("ORIGINAL_VOICE_CANONICAL_PATH_UNVERIFIED")
    if not present("voice_route_empiredb_readback_verified"):
        blockers.append("ORIGINAL_EMPIREDB_VOICE_READBACK_NOT_VERIFIED")
    if not present("private_founder_ingress_approved"):
        blockers.append("PRIVATE_FOUNDER_SECURITY_INGRESS_NOT_APPROVED")
    if not present("end_to_end_consent_voice_task_verified"):
        blockers.append("CONSENTED_VOICE_TASK_END_TO_END_NOT_VERIFIED")
    if not present("commercial_buyer_demand_and_payment_verified"):
        blockers.append("INDEPENDENT_COMMERCIAL_PROOF_NOT_VERIFIED")

    # This module CANNOT validate that a report was signed by an authorised
    # owner. Even all-green self-reported booleans do not authorise release.
    if not blockers:
        blockers.append("ORIGINAL_OWNER_SIGNED_ATTESTATION_STILL_REQUIRED")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "FLAGSHIP_PRODUCTION_READINESS_ON_HOLD",
        "health_only_does_not_prove_inference": True,
        "inference_success_observed_by_this_module": False,
        "legacy_supabase_is_not_original_empiredb": True,
        "observed_reported_signal_count": sum(v is not None for v in observed.values()),
        "reported_signals_not_cryptographic_proof": True,
        "readiness_blockers": blockers,
        "technical_build_and_commercial_valuation_are_distinct": True,
        "target_valuation_independently_verified": False,
        "real_world_accuracy": None,
        "action_authorized": False,
        "real_voice_call_placed": False,
        "reminder_scheduled": False,
        "model_mutated": False,
        "original_empiredb_writes": False,
        "outbound_sent": False,
        "payment_executed": False,
        "execution_authority": "none",
    }


def founder_flagship_readiness_status(packet: Mapping[str, Any] | None) -> dict[str, Any]:
    """Minimal preflight projection, no runtime addresses, secrets or caller IDs."""
    if packet is None:
        return {
            "schema_version": "empire.prime.founder_flagship_readiness.v1",
            "status": "NOT_CHECKED",
            "mode": "OBSERVE",
            "launch_approved": False,
            "execution_authority": "none",
        }
    allowed = {
        "schema_version", "mode", "status",
        "health_only_does_not_prove_inference",
        "inference_success_observed_by_this_module",
        "legacy_supabase_is_not_original_empiredb",
        "observed_reported_signal_count",
        "reported_signals_not_cryptographic_proof", "readiness_blockers",
        "technical_build_and_commercial_valuation_are_distinct",
        "target_valuation_independently_verified", "real_world_accuracy",
        "action_authorized", "real_voice_call_placed", "reminder_scheduled",
        "model_mutated", "original_empiredb_writes", "outbound_sent",
        "payment_executed", "execution_authority",
    }
    if (type(packet) is not dict or set(packet) != allowed
        or packet["schema_version"] != SCHEMA
        or packet["status"] != "FLAGSHIP_PRODUCTION_READINESS_ON_HOLD"
        or packet["mode"] != "OBSERVE"
        or packet["health_only_does_not_prove_inference"] is not True
        or packet["inference_success_observed_by_this_module"] is not False
        or packet["legacy_supabase_is_not_original_empiredb"] is not True
        or packet["reported_signals_not_cryptographic_proof"] is not True
        or packet["target_valuation_independently_verified"] is not False
        or packet["technical_build_and_commercial_valuation_are_distinct"] is not True
        or packet["real_world_accuracy"] is not None
        or packet["action_authorized"] is not False
        or packet["real_voice_call_placed"] is not False
        or packet["reminder_scheduled"] is not False
        or packet["model_mutated"] is not False
        or packet["original_empiredb_writes"] is not False
        or packet["outbound_sent"] is not False
        or packet["payment_executed"] is not False
        or packet["execution_authority"] != "none"):
        raise ValueError("untrusted_original_flagship_release_claim")
    blockers = packet["readiness_blockers"]
    count = packet["observed_reported_signal_count"]
    if (type(blockers) is not list or not 1 <= len(blockers) <= 16
        or any(type(x) is not str or not x.isupper() or len(x) > 75
               for x in blockers)
        or len(blockers) != len(set(blockers))
        or type(count) is not int or not 0 <= count <= len(FIELDS)):
        raise ValueError("invalid_original_flagship_preflight_projection")
    return {
        "schema_version": "empire.prime.founder_flagship_readiness.v1",
        "mode": "OBSERVE",
        "status": "LAUNCH_ON_HOLD",
        "readiness_blockers": list(blockers),
        "readiness_is_not_market_valuation": True,
        "launch_approved": False,
        "execution_authority": "none",
    }
