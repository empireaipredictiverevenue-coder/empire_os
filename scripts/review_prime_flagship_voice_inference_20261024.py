#!/usr/bin/env python3
"""Read-only owner diagnostic: original flagship speech + local reasoning HOLD.

No generation, model reloads, live audio, private text, sender, or DB writes.
Local health/idle slot are not proof of successful bounded inference.
"""
from __future__ import annotations

import json
from urllib import request, error

from empire_os.voice_lab import EmpireVoiceLab, VoiceLabConfig
from empire_os.voice_routing_policy import switchboard_status
from empire_os.coder.llama_cpp_provider import LlamaCppProvider
from empire_os.prime_flagship_assistant_readiness import (
    FIELDS, review_flagship_assistant_readiness,
    founder_flagship_readiness_status,
)


def _local_slot_idle() -> bool | None:
    """Only loopback. Never prints the slot's original prompt or identifiers."""
    try:
        with request.urlopen("http://127.0.0.1:11435/slots", timeout=2) as resp:
            if resp.status != 200:
                return None
            slots = json.loads(resp.read(32768))
            if type(slots) is not list or not slots:
                return None
            if any(type(x) is not dict or type(x.get("is_processing")) is not bool
                   for x in slots):
                return None
            return any(x["is_processing"] is False for x in slots)
    except (OSError, TimeoutError, ValueError, error.URLError):
        return None


def inspect() -> dict:
    try:
        dependencies = EmpireVoiceLab.dependency_readiness()
        assets = EmpireVoiceLab.model_readiness(VoiceLabConfig.from_env())
    except (ValueError, OSError, TypeError):
        dependencies, assets = {}, {}
    try:
        legacy = switchboard_status().get("canonical_database") == "supabase"
    except (ValueError, OSError, TypeError):
        legacy = None
    try:
        health = LlamaCppProvider(timeout_seconds=10).health()
    except (ValueError, OSError, TypeError):
        health = None
    values = {
        "local_model_health": health,
        "local_model_idle_slot": _local_slot_idle(),
        "bounded_inference_completed": False,  # previous read-only probes timed out
        "voice_dependencies_available": (all(dependencies.values()) if dependencies else None),
        "voice_models_available": (all(assets.values()) if assets else None),
        "legacy_voice_uses_supabase": legacy,
        "voice_route_empiredb_readback_verified": False,
        "private_founder_ingress_approved": False,
        "end_to_end_consent_voice_task_verified": False,
        "commercial_buyer_demand_and_payment_verified": False,
    }
    if set(values) != FIELDS:
        raise ValueError("original_flagship_readiness_schema_drift")
    packet = review_flagship_assistant_readiness(values)
    return {
        "schema_version": "empire.prime.original_flagship_diagnostic.v1",
        "status": "READ_ONLY_OWNER_REVIEW",
        "observed_health_but_not_inference_success": health is True,
        "observed_idle_slot_but_not_inference_success": values["local_model_idle_slot"] is True,
        "original_speech_dependency_flags": {
            "all_available": values["voice_dependencies_available"],
            "assets_available": values["voice_models_available"],
        },
        "legacy_voice_database_not_canonical": legacy,
        "founder_projection": founder_flagship_readiness_status(packet),
        "outbound_sent": False,
        "production_mutated": False,
        "execution_authority": "none",
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True, indent=2))
