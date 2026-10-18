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
