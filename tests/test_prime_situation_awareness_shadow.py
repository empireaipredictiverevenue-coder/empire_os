"""Original PRIME contextual awareness: missing truth stays missing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from empire_os.prime_situation_awareness_shadow import (
    REQUEST_CAPABILITY, review_prime_situation, founder_situation_status,
)

NOW = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)


def observation(i=0, **changes):
    row = {
        "signal_code": "USER_EXPLICIT_REQUEST",
        "source_code": "USER_DECLARATION",
        "observation_fingerprint": sha256(f"synthetic-fixture-{i}".encode()).hexdigest(),
        "observed_at": (NOW - timedelta(minutes=3)).isoformat(),
        "assertion": "PRESENT",
        "synthetic": True,
        "purpose_reviewed": True,
    }
    row.update(changes)
    return row


def review(code="SIMULATE_SCENARIO", rows=None):
    return review_prime_situation(
        situation_key="fictional_case_one",
        request_code=code,
        observations=rows, as_of=NOW,
    )


def test_unconnected_source_is_unknown_not_all_seeing():
    out = review()
    assert out["status"] == "SITUATION_CONTEXT_REVIEW_HOLD"
    assert out["claims_received_count_not_verified_events"] is None
    assert "SOURCE_NOT_CONNECTED_UNKNOWN_NOT_ZERO" in out["missing_information_or_authority"]
    assert out["universal_awareness_or_consciousness_claim"] is False
    assert out["execution_authority"] == "none"
    assert out["action_performed"] is False
    assert out["original_capability_key"] == "simulation.preview"


def test_empty_sources_do_not_mean_zero_hazards_or_zero_opportunities():
    out = review("SAFETY_EMERGENCY", [])
    assert out["claims_received_count_not_verified_events"] == 0
    assert "NO_OBSERVATIONS_UNKNOWN_NOT_NEGATIVE" in out["missing_information_or_authority"]
    assert "HUMAN_EMERGENCY_RESPONSE_NOT_REPLACED_BY_SIMULATION" in out["missing_information_or_authority"]
    assert out["smart_home_command_sent"] is False
    assert out["real_data_verified"] is False


def test_same_context_fuses_multiple_declared_modalities_but_not_verification():
    out = review("WORLD_STATUS", [
        observation(0, source_code="ORIGINAL_ASTRA",
                    signal_code="WORLD_EVENT", synthetic=False),
        observation(1, source_code="ORIGINAL_VOICE_LAB",
                    signal_code="VOICE_AVAILABILITY", synthetic=True),
    ])
    assert out["claims_received_count_not_verified_events"] == 2
    assert out["age_counts"]["CURRENT_AGE_ONLY"] == 2
    assert out["declared_unauthenticated_claim_count"] == 1
    assert "ORIGINAL_VOICE_LAB" in out["source_classes"]
    assert "INDEPENDENT_SOURCE_AUTHENTICATION_NOT_PROVIDED" in out["missing_information_or_authority"]
    assert out["real_data_verified"] is False
    assert out["capability_permission_observed"] is False


def test_alexa_like_unconnected_features_are_explicit_gaps():
    for code in ("WEATHER_STATUS", "TIMER_OR_ALARM", "PERSONAL_REMINDER",
                 "CALENDAR_CHECK", "MEDIA_PLAYBACK", "SMART_HOME_CONTROL",
                 "AUTOMATED_ROUTINE", "VOICE_DIALOGUE", "MESSAGE_SEND"):
        out = review(code, [])
        assert out["capability_in_original_registry"] is False
        assert "FEATURE_NOT_REGISTERED_OR_CONNECTED_IN_ORIGINAL_AGI" in out[
            "missing_information_or_authority"
        ]
        assert out["feature_connected_to_real_world_tools"] is False
        assert out["execution_authority"] == "none"


def test_original_high_risk_registered_capability_is_not_granted():
    for code, key in (("PAYMENT_REQUEST", "payment.move"),
                      ("OUTBOUND_CALL", "voice.call"),
                      ("INFRASTRUCTURE_CHANGE", "infrastructure.change")):
        out = review(code, [observation()])
        assert out["original_capability_key"] == key
        assert out["capability_in_original_registry"] is True
        assert "ORIGINAL_OWNER_ACTION_PERMISSION_REQUIRED" in out["missing_information_or_authority"]
        assert "CAPABILITY_capability_not_granted" in out["missing_information_or_authority"]
        assert out["payment_executed"] is False
        assert out["outbound_sent"] is False


def test_digital_twin_synthetic_claim_cannot_assert_actual_world_state():
    with pytest.raises(ValueError, match="original_digital_twin_cannot_prove_live_situation"):
        review("BUYER_CONVERSATION_REVIEW", [
            observation(source_code="ORIGINAL_DIGITAL_TWIN", synthetic=False),
        ])


def test_synthetic_simulated_outcome_remains_noncommercial():
    out = review("SIMULATE_SCENARIO", [
        observation(source_code="ORIGINAL_DIGITAL_TWIN",
                    signal_code="SIMULATED_OUTCOME"),
    ])
    assert out["synthetic_claim_count"] == 1
    assert out["real_customer_intent_verified"] is False
    assert out["model_training"] is False
    assert out["real_data_verified"] is False
    assert out["payment_executed"] is False


def test_conflicting_source_claims_do_not_enable_world_action():
    out = review("SMART_HOME_CONTROL", [
        observation(1, source_code="EXTERNAL_PROVIDER_UNVERIFIED",
                    signal_code="DEVICE_STATE", assertion="PRESENT", synthetic=False),
        observation(2, source_code="USER_DECLARATION",
                    signal_code="DEVICE_STATE", assertion="ABSENT"),
    ])
    assert out["contradictory_signal_codes_not_lie_detection"] == ["DEVICE_STATE"]
    assert "CONTRADICTORY_SOURCE_CLAIMS_REQUIRE_REVIEW" in out["missing_information_or_authority"]
    assert out["smart_home_command_sent"] is False
    assert out["real_data_verified"] is False


def test_old_data_is_stale_and_not_current():
    out = review("SMART_HOME_CONTROL", [
        observation(0, signal_code="DEVICE_STATE",
                    observed_at=(NOW - timedelta(hours=1)).isoformat()),
    ])
    assert out["age_counts"]["STALE"] == 1
    assert "NO_CURRENT_SOURCE_CLAIMS" in out["missing_information_or_authority"]
    assert "STALE_OR_EXPIRED_SOURCE_CLAIMS" in out["missing_information_or_authority"]


def test_oldest_data_expires_but_never_fake_recency():
    out = review("ASK_INFORMATION", [
        observation(0, observed_at=(NOW - timedelta(days=8)).isoformat()),
    ])
    assert out["age_counts"]["EXPIRED"] == 1


def test_temporally_impossible_evidence_fails_closed():
    with pytest.raises(ValueError, match="future_situation_evidence_refused"):
        review("ASK_INFORMATION", [
            observation(observed_at=(NOW + timedelta(hours=1)).isoformat()),
        ])


def test_unreviewed_processing_rights_cannot_grant_context_authority():
    out = review("VOICE_DIALOGUE", [observation(purpose_reviewed=False)])
    assert "SOURCE_PURPOSE_NOT_REVIEWED" in out["missing_information_or_authority"]
    assert out["real_data_verified"] is False


def test_fake_private_contact_is_not_an_opaque_signal_fingerprint():
    with pytest.raises(ValueError, match="opaque_purpose_scoped"):
        review("BUYER_CONVERSATION_REVIEW", [
            observation(observation_fingerprint="real-user@example.test"),
        ])


def test_duplicate_fingerprints_cannot_inflate_situational_coverage():
    with pytest.raises(ValueError, match="opaque_purpose_scoped"):
        review("WORLD_STATUS", [observation(), observation()])


def test_missing_and_unrecognised_situation_class_fails_closed():
    with pytest.raises(ValueError, match="known_original_situation_request_code_required"):
        review("OMNISCIENT_AUTONOMOUS_AGENT")
    with pytest.raises(ValueError, match="bounded_nonpersonal_situation_key"):
        review_prime_situation(
            situation_key="user@example.test", request_code="SIMULATE_SCENARIO",
            observations=[], as_of=NOW,
        )


@pytest.mark.parametrize("extra", [
    {"body": "private conversation message"},
    {"email": "user@example.test"},
    {"personality_profile": "fearful"},
])
def test_private_fields_rejected_instead_of_observed(extra):
    bad = observation()
    bad.update(extra)
    with pytest.raises(ValueError, match="exact_privacy_minimal"):
        review("ASK_INFORMATION", [bad])


def test_founder_projection_obscures_source_and_fingerprints():
    out = review("SIMULATE_SCENARIO", [observation()])
    safe = founder_situation_status(out)
    assert safe["status"] == "REQUIRES_REAL_SOURCE_AND_OWNER_GATES"
    assert safe["consciousness_claim"] is False
    assert safe["execution_authority"] == "none"
    assert "observation_fingerprint" not in str(safe)
    assert "USER_DECLARATION" not in str(safe)
    assert founder_situation_status(None)["status"] == "NOT_CONNECTED"


@pytest.mark.parametrize("tamper", [
    {"action_performed": True},
    {"source_attestation_verified_by_this_module": True},
    {"feature_connected_to_real_world_tools": True},
    {"universal_awareness_or_consciousness_claim": True},
    {"payment_executed": True},
    {"outbound_sent": True},
    {"smart_home_command_sent": True},
    {"original_empiredb_writes": True},
    {"execution_authority": "unrestricted"},
    {"request_code": "ALL_KNOWING"},
])
def test_forged_authority_or_consciousness_claim_rejected_by_founder(tamper):
    out = review("SIMULATE_SCENARIO", [observation()])
    out.update(tamper)
    with pytest.raises(ValueError):
        founder_situation_status(out)


def test_original_capability_coverage_contract_does_not_use_new_executor():
    out = review("FORECAST_REVIEW", [observation()])
    assert out["original_capability_key"] == "forecast.preview"
    assert out["memory_query_plan"]["filters"]["outcome_conditioned_requires_verified_outcome"] is True
    assert out["memory_query_plan"]["execution_authority"] == "none"
    assert out["capability_permission_observed"] is False
    assert out["action_performed"] is False


@pytest.mark.parametrize("tamper", [
    {"capability_in_original_registry": False},
    {"original_capability_key": "outreach.send"},
    {"missing_information_or_authority": []},
])
def test_founder_rejects_forged_registered_capability_or_suppressed_blockers(tamper):
    out = review("SIMULATE_SCENARIO", [observation()])
    out.update(tamper)
    with pytest.raises(ValueError, match="untrusted_original_situation_projection_schema"):
        founder_situation_status(out)
