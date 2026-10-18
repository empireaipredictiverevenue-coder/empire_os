"""Prospective prediction packets are NEVER proof of durable pre-outcome forecasts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.predictive_calibration import prepare_prospective_conversion_prediction

NOW = datetime(2026, 10, 18, 20, 30, tzinfo=timezone.utc)


def packet(**changes):
    values = {
        "tenant_id": "test-tenant",
        "opportunity_key": "op-123",
        "predicted_probability": 0.6,
        "predicted_at": NOW.isoformat(),
        "horizon_until": (NOW + timedelta(days=14)).isoformat(),
        "evidence_refs": ["quant:source:1", "canonical:research:1"],
        "model_name": "empire_quant",
        "model_version": "v1",
        "assessed_at": NOW,
    }
    values.update(changes)
    return prepare_prospective_conversion_prediction(**values)


def test_prospective_prediction_candidate_is_deterministic_and_not_durable():
    first = packet()
    second = packet(evidence_refs=["canonical:research:1", "quant:source:1"])
    assert first == second
    assert first["status"] == "REGISTRY_PROOF_REQUIRED"
    assert first["proposed_prediction"]["prediction_type"] == "conversion_probability"
    assert first["proposed_prediction"]["predicted_probability"] == 0.6
    assert first["candidate_prediction_ref"].startswith("conversion_prediction_candidate:")
    assert first["original_prediction_registered"] is False
    assert first["pre_outcome_immutability_proven"] is False
    assert first["may_use_in_verified_calibration"] is False
    assert first["database_writes"] is False
    assert first["execution_authority"] == "none"


def test_changed_probability_or_horizon_gets_distinct_proposed_identity():
    a = packet()
    assert a["candidate_prediction_ref"] != packet(
        predicted_probability=0.7
    )["candidate_prediction_ref"]
    assert a["candidate_prediction_ref"] != packet(
        horizon_until=(NOW + timedelta(days=15)).isoformat()
    )["candidate_prediction_ref"]


@pytest.mark.parametrize("changes", [
    {"tenant_id": ""},
    {"opportunity_key": ""},
    {"model_version": ""},
    {"predicted_probability": None},
    {"predicted_probability": float("nan")},
    {"predicted_probability": float("inf")},
    {"predicted_probability": True},
    {"predicted_probability": 1.01},
    {"predicted_at": (NOW + timedelta(minutes=1)).isoformat()},
    {"predicted_at": "2026-10-18T20:30:00"},
    {"horizon_until": NOW.isoformat()},
    {"assessed_at": datetime(2026, 10, 18)},
    {"evidence_refs": []},
    {"evidence_refs": ["one", "one"]},
    {"evidence_refs": [""]},
])
def test_invalid_and_backdated_candidate_inputs_do_not_pass(changes):
    with pytest.raises(ValueError):
        packet(**changes)


def test_mutating_caller_inputs_does_not_mutate_proposed_packet():
    evidence = ["canonical:research:1"]
    payload = packet(evidence_refs=evidence)
    evidence.append("malicious:later")
    assert payload["proposed_prediction"]["evidence_refs"] == ["canonical:research:1"]
    assert json.dumps(payload, allow_nan=False)
