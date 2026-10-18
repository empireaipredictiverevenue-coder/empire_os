"""Founder formula readiness only reads validated, current producer states."""
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.predictive_formula_evidence_review import (
    SOURCES, review_formula_evidence,
)
from empire_os.predictive_revenue_formula import (
    CORE_FACTORS, predictive_revenue_formula, revenue_formula_identification_bounds,
)

NOW = datetime(2026, 10, 18, 18, tzinfo=timezone.utc)


def _sources(root, *, generated_at=NOW, ready=True, evaluated=True):
    formula = {
        "schema_version": SOURCES["cloud_formula"][1],
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": generated_at.isoformat(),
        "prediction_ready": ready, "formula_evaluated": evaluated,
        "blockers": [] if ready else ["verified_probability_inputs_required"],
        "sensitive_customer_data": "do-not-output",
    }
    inputs = dict.fromkeys(CORE_FACTORS, 0.8)
    inputs["ltv_cents"] = 10000
    row = {
        "opportunity_key": "example-opportunity",
        "canonical_prediction": predictive_revenue_formula(inputs),
        "canonical_prediction_identification_bounds": (
            revenue_formula_identification_bounds(inputs)
        ),
        "private_customer_email": "sensitive-value",
    }
    distribution = {
        "schema_version": SOURCES["revenue_distribution"][1],
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": generated_at.isoformat(),
        "opportunities": [row],
    }
    for source_name, obj in (("cloud_formula", formula),
                             ("revenue_distribution", distribution)):
        path = root / SOURCES[source_name][0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))
    return formula, distribution


def test_missing_sources_stay_unknown_not_commercial_ready(tmp_path):
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert report["cloud_prediction_ready"] is None
    assert report["fresh_opportunity_count"] is None
    assert report["missing_factor_counts"] is None
    assert report["outbound_sent"] is False
    assert report["execution_authority"] == "none"


def test_fresh_complete_sources_are_review_ready_not_exec_ready(tmp_path):
    _sources(tmp_path)
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["status"] == "REVIEW_READY"
    assert report["fresh_opportunity_count"] == 1
    assert report["revenue_formula_bounds_supported"] is True
    assert report["blockers"] == []
    assert report["cloud_prediction_ready"] is True
    assert report["model_is_commercially_calibrated"] is False
    assert report["commercial_execution_authorized"] is False
    assert "sensitive-value" not in json.dumps(report)
    assert "do-not-output" not in json.dumps(report)


def test_algorithm_available_not_sufficient_for_prediction(tmp_path):
    _sources(tmp_path, ready=False, evaluated=False)
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert report["cloud_prediction_ready"] is False
    assert "verified_probability_inputs_required" in report["blockers"]
    assert "cloud_formula_not_yet_evaluated" in report["blockers"]


def test_stale_distribution_is_not_counted_as_current(tmp_path):
    cloud, distribution = _sources(tmp_path)
    old = NOW - timedelta(days=4)
    distribution["generated_at"] = old.isoformat()
    path = tmp_path / SOURCES["revenue_distribution"][0]
    path.write_text(json.dumps(distribution))
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["source_status"]["cloud_formula"] == "FRESH"
    assert report["source_status"]["revenue_distribution"] == "STALE"
    assert report["fresh_opportunity_count"] is None
    assert report["revenue_formula_bounds_supported"] is None
    assert report["status"] == "EVIDENCE_HOLD"


def test_partial_unknown_factor_counts_provide_evidence_gaps(tmp_path):
    cloud, distribution = _sources(tmp_path)
    missing = distribution["opportunities"][0]
    missing["canonical_prediction"] = predictive_revenue_formula({
        "demand": 0.8, "ltv_cents": 10000,
    })
    missing["canonical_prediction_identification_bounds"] = (
        revenue_formula_identification_bounds({"demand": 0.8, "ltv_cents": 10000})
    )
    (tmp_path / SOURCES["revenue_distribution"][0]).write_text(
        json.dumps(distribution)
    )
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["missing_factor_counts"]["payment"] == 1
    assert report["status"] == "EVIDENCE_HOLD"
    assert "revenue_formula_inputs_incomplete" in report["blockers"]
    assert report["revenue_formula_bounds_supported"] is True


@pytest.mark.parametrize("change", [
    {"mode": "LIVE"},
    {"execution_authority": "external"},
    {"generated_at": (NOW + timedelta(seconds=1)).isoformat()},
    {"generated_at": (NOW - timedelta(days=1)).isoformat()},
    {"blockers": ["email:private-sensitive-thing"]},
    {"prediction_ready": "true"},
])
def test_untrusted_cloud_producer_is_held(tmp_path, change):
    cloud, _ = _sources(tmp_path)
    cloud.update(change)
    (tmp_path / SOURCES["cloud_formula"][0]).write_text(json.dumps(cloud))
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert report["cloud_prediction_ready"] is None
    assert "private-sensitive-thing" not in json.dumps(report)


def test_symlink_data_file_is_held_without_reading(tmp_path):
    _sources(tmp_path)
    path = tmp_path / SOURCES["cloud_formula"][0]
    path.unlink()
    path.symlink_to(tmp_path / SOURCES["revenue_distribution"][0])
    assert review_formula_evidence(tmp_path, as_of=NOW)["source_status"][
        "cloud_formula"
    ] == "MISSING_OR_UNSAFE"


def test_old_distribution_contract_does_not_claim_bounds(tmp_path):
    _, distribution = _sources(tmp_path)
    distribution["opportunities"][0].pop(
        "canonical_prediction_identification_bounds"
    )
    (tmp_path / SOURCES["revenue_distribution"][0]).write_text(
        json.dumps(distribution)
    )
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert "revenue_distribution_formula_bounds_not_yet_deployed" in report["blockers"]


def test_empty_formulas_cannot_become_commercially_ready(tmp_path):
    _, distribution = _sources(tmp_path)
    distribution["opportunities"] = []
    (tmp_path / SOURCES["revenue_distribution"][0]).write_text(
        json.dumps(distribution)
    )
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert "no_observed_opportunities_for_formula" in report["blockers"]


def test_formula_health_includes_revalidated_empty_learning_not_fake_accuracy(tmp_path):
    _sources(tmp_path)
    from test_predictive_learning_readiness import empty_memory, _write
    _write(tmp_path, empty_memory(generated_at=NOW.isoformat()))
    report = review_formula_evidence(tmp_path, as_of=NOW)
    learning = report["verified_outcome_learning"]
    assert learning["status"] == "INSUFFICIENT_VERIFIED_EVIDENCE"
    assert learning["verified_review_count"] == 0
    assert learning["candidate_brier"] is None
    assert learning["candidate_beats_baseline"] is None
    assert learning["learning_promoted"] is False
    # Formula availability and commercial calibration are independent.
    assert report["status"] == "REVIEW_READY"
    assert report["model_is_commercially_calibrated"] is False


def test_formula_health_does_not_expose_scoped_outcome_data(tmp_path):
    _sources(tmp_path)
    from test_predictive_learning_readiness import empty_memory, _write
    _write(tmp_path, empty_memory(
        generated_at=NOW.isoformat(),
        tenant_id="private-tenant",
        verified_learning_feedback=[{"secret": "private-customer-data"}],
    ))
    report = review_formula_evidence(tmp_path, as_of=NOW)
    learning = report["verified_outcome_learning"]
    assert learning["reason"] == "TENANT_SCOPE_REQUIRED"
    assert learning["verified_review_count"] is None
    assert "private-tenant" not in json.dumps(report)
    assert "private-customer-data" not in json.dumps(report)


def _quant(root, *, missing_fields=None):
    from empire_os.quant_brain import _DECISION_PACKET_REQUIRED
    missing_fields = (
        list(_DECISION_PACKET_REQUIRED)
        if missing_fields is None else list(missing_fields)
    )
    available = not missing_fields
    row = {
        "opportunity_key": "private-opportunity",
        "tenant_id": "do-not-expose-tenant",
        "prediction_ref": "quant_prediction:example" if available else None,
        "decision_packet": {
            "status": "AVAILABLE" if available else "UNAVAILABLE",
            "missing_fields": missing_fields,
            "private_context": "never-output-customer",
        },
    }
    data = {
        "schema_version": SOURCES["opportunity_quant"][1],
        "mode": "OBSERVE",
        "execution_authority": "none",
        "generated_at": NOW.isoformat(),
        "candidate_count": 1,
        "available_decision_packet_count": int(available),
        "unavailable_decision_packet_count": int(not available),
        "missing_field_counts": {name: 1 for name in missing_fields},
        "items": [row],
    }
    path = root / SOURCES["opportunity_quant"][0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data, path


def test_quant_inputs_gap_is_visible_without_customer_or_forecast_leak(tmp_path):
    _sources(tmp_path)
    _quant(tmp_path)
    report = review_formula_evidence(tmp_path, as_of=NOW)
    review = report["quant_original_prediction_readiness"]
    assert report["source_status"]["opportunity_quant"] == "FRESH"
    assert review["candidate_count"] == 1
    assert review["available_quant_decision_count"] == 0
    assert review["missing_input_counts"]["probability_success"] == 1
    assert review["next_evidence_action"] == "VERIFY_ORIGINAL_QUANT_INPUT_ECONOMICS"
    assert review["source_rows_are_original_conversion_predictions"] is False
    assert review["immutable_prediction_receipt_verified"] is False
    assert "never-output-customer" not in json.dumps(report)
    assert "do-not-expose-tenant" not in json.dumps(report)


def test_quant_available_packet_still_is_not_original_conversion_forecast(tmp_path):
    _sources(tmp_path)
    _quant(tmp_path, missing_fields=[])
    report = review_formula_evidence(tmp_path, as_of=NOW)
    review = report["quant_original_prediction_readiness"]
    assert review["available_quant_decision_count"] == 1
    assert review["next_evidence_action"] == "RECORD_TIMESTAMPED_CONVERSION_PREDICTION"
    assert review["source_rows_are_original_conversion_predictions"] is False


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(available_decision_packet_count=1),
    lambda d: d.update(candidate_count=1000),
    lambda d: d["items"][0]["decision_packet"].update(
        missing_fields=["private-customer-secret"]
    ),
    lambda d: d.update(missing_field_counts={"probability_success": 77}),
    lambda d: d["items"][0].update(prediction_ref="forged:available"),
])
def test_quant_source_summary_mismatch_is_untrusted(tmp_path, mutate):
    _sources(tmp_path)
    data, path = _quant(tmp_path)
    mutate(data)
    path.write_text(json.dumps(data))
    report = review_formula_evidence(tmp_path, as_of=NOW)
    assert report["source_status"]["opportunity_quant"] == "UNTRUSTED"
    assert report["quant_original_prediction_readiness"] is None
    assert "private-customer-secret" not in json.dumps(report)
