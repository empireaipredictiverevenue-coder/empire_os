"""Voice/AI flagship acceptance is evidence-based and not a £250k appraisal."""
from __future__ import annotations

from copy import deepcopy

import pytest

from empire_os.prime_flagship_assistant_readiness import (
    FIELDS, review_flagship_assistant_readiness,
    founder_flagship_readiness_status,
)
from scripts.review_prime_flagship_voice_inference_20261024 import inspect


def evidence(**changes):
    row = dict.fromkeys(FIELDS, False)
    row.update(changes)
    return row


def test_unknown_readiness_does_not_invent_a_live_voice_product():
    r = review_flagship_assistant_readiness(None)
    assert r["status"] == "FLAGSHIP_PRODUCTION_READINESS_ON_HOLD"
    assert r["observed_reported_signal_count"] == 0
    assert r["inference_success_observed_by_this_module"] is False
    assert r["target_valuation_independently_verified"] is False
    assert r["real_voice_call_placed"] is False
    assert r["payment_executed"] is False
    assert "ORIGINAL_VOICE_CANONICAL_PATH_UNVERIFIED" in r["readiness_blockers"]


def test_healthy_and_idle_model_not_proof_of_successful_generation():
    packet = review_flagship_assistant_readiness(evidence(
        local_model_health=True, local_model_idle_slot=True,
    ))
    assert "MODEL_HEALTH_NOT_VERIFIED" not in packet["readiness_blockers"]
    assert "MODEL_CAPACITY_NOT_VERIFIED" not in packet["readiness_blockers"]
    assert "BOUNDED_GENERATION_NOT_VERIFIED" in packet["readiness_blockers"]
    assert packet["inference_success_observed_by_this_module"] is False


def test_original_self_hosted_speech_assets_are_not_complete_voice_assistant():
    packet = review_flagship_assistant_readiness(evidence(
        local_model_health=True, local_model_idle_slot=True,
        voice_dependencies_available=True, voice_models_available=True,
        legacy_voice_uses_supabase=True,
    ))
    assert "ORIGINAL_SPEECH_DEPENDENCIES_NOT_VERIFIED" not in packet["readiness_blockers"]
    assert "ORIGINAL_SPEECH_ASSETS_NOT_VERIFIED" not in packet["readiness_blockers"]
    assert "LEGACY_VOICE_USES_NONCANONICAL_SUPABASE_PATH" in packet["readiness_blockers"]
    assert "ORIGINAL_EMPIREDB_VOICE_READBACK_NOT_VERIFIED" in packet["readiness_blockers"]
    assert "CONSENTED_VOICE_TASK_END_TO_END_NOT_VERIFIED" in packet["readiness_blockers"]
    assert packet["real_voice_call_placed"] is False
    assert packet["original_empiredb_writes"] is False


def test_caller_self_reported_everything_green_still_cannot_grant_launch():
    packet = review_flagship_assistant_readiness(evidence(**{k: True for k in FIELDS if k != "legacy_voice_uses_supabase"}, legacy_voice_uses_supabase=False))
    assert packet["readiness_blockers"] == ["ORIGINAL_OWNER_SIGNED_ATTESTATION_STILL_REQUIRED"]
    assert packet["status"] == "FLAGSHIP_PRODUCTION_READINESS_ON_HOLD"
    assert founder_flagship_readiness_status(packet)["launch_approved"] is False


def test_missing_and_wrong_schema_fail_closed():
    with pytest.raises(ValueError, match="exact_original_flagship"):
        review_flagship_assistant_readiness({})
    with pytest.raises(ValueError, match="exact_original_flagship"):
        review_flagship_assistant_readiness({**evidence(), "private_customer_email": "person@example.test"})


@pytest.mark.parametrize("wrong", [1, 0, "yes", [], {}, float("nan")])
def test_numeric_string_and_untrusted_flags_cannot_prove_voice_ready(wrong):
    with pytest.raises(ValueError, match="tri_state"):
        review_flagship_assistant_readiness(evidence(bounded_inference_completed=wrong))


def test_founder_no_status_unknown_is_not_claim_of_valution():
    r = founder_flagship_readiness_status(None)
    assert r["status"] == "NOT_CHECKED"
    assert r["launch_approved"] is False
    assert r["execution_authority"] == "none"


@pytest.mark.parametrize("tamper", [
    {"execution_authority": "live"},
    {"action_authorized": True},
    {"real_voice_call_placed": True},
    {"target_valuation_independently_verified": True},
    {"inference_success_observed_by_this_module": True},
    {"reminder_scheduled": True},
    {"payment_executed": True},
    {"original_empiredb_writes": True},
    {"status": "FULLY_CONSCIOUS_LAUNCHED"},
    {"readiness_blockers": []},
    {"real_world_accuracy": 0.99},
])
def test_founder_refuses_forged_release_or_commercial_claim(tamper):
    original = review_flagship_assistant_readiness(evidence(
        local_model_health=True, local_model_idle_slot=True,
    ))
    packet = deepcopy(original)
    packet.update(tamper)
    with pytest.raises(ValueError):
        founder_flagship_readiness_status(packet)


def test_cli_diagnostic_is_read_only_and_cannot_report_launch():
    r = inspect()
    assert r["status"] == "READ_ONLY_OWNER_REVIEW"
    assert r["outbound_sent"] is False
    assert r["production_mutated"] is False
    assert r["execution_authority"] == "none"
    assert r["founder_projection"]["launch_approved"] is False
    assert r["founder_projection"]["readiness_is_not_market_valuation"] is True


def test_existing_founder_twin_api_embeds_safe_unknown_flagship_gate_without_inference():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    with TestClient(build_founder_dashboard_service()) as client:
        response = client.get("/v1/founder-dashboard/prime-digital-twin")
        assert response.status_code == 200
        data = response.json()
        gate = data["flagship_release_readiness"]
        assert gate["status"] == "LAUNCH_ON_HOLD"
        assert gate["launch_approved"] is False
        assert gate["readiness_is_not_market_valuation"] is True
        assert gate["execution_authority"] == "none"
        assert data["local_model_active_in_this_read_only_request"] is False
        assert data["recognized_revenue_cents"] is None
