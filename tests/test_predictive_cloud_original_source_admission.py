"""Filesystem snapshots cannot self-attest tenant-specific Cloud readiness."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from empire_os.predictive_cloud_materializer import (
    FORMULA_OUTPUT, TREND_OUTPUT, refresh_predictive_cloud_materializers,
)

NOW = datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc)


def save(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value))


def files(root, *, outcome=30, probability=3, timing=3, refs=True):
    save(root, "runtime/opportunity_factory/value_latest.json", {
        "candidate_count": 3,
        "items": [{
            "status": "AVAILABLE",
            "expected_revenue_cents": 100000,
            "expected_gross_profit_cents": 92000,
            "quant_input_evidence": {
                "evidence_refs": ["owner:self_attested"]
            } if refs else {}
        }]
    })
    save(root, "runtime/predictive_intelligence/latest.json", {
        "schema_version": "empire.predictive_intelligence.v1",
        "mode": "OBSERVE",
        "generated_at": NOW.isoformat(),
        "tenant_id": "self_attested_founder",
        "original_tenant_source_authenticated": True,
        "original_outcome_issuer_authenticated": True,
        "original_forecast_registered_before_outcome": True,
        "probability_ready_product_count": probability,
        "timing_ready_product_count": timing,
        "matched_outcome_count": outcome,
        "product_estimates": {"sku_fake": {"probability_available": True}},
        "source_scope_admission_status": "LOCAL_UNVERIFIED_SOURCE",
    })


def assert_held(result):
    assert result["status"] == "AVAILABLE"  # executable runtime, not model proof
    assert result["prediction_ready_component_count"] == 0
    assert result["source_admission_state"] == "UNVERIFIED_LOCAL_SNAPSHOT_ONLY"
    assert result["original_tenant_issuer_authenticated"] is False
    assert result["frozen_original_forecast_registry_verified"] is False
    for item in ("future_trend", "predictive_cloud_formula"):
        report = result[item]
        assert report["available"] is True
        assert report["algorithm_available"] is True
        assert report["prediction_ready"] is False
        assert report["economic_rows_independently_verified"] is False
        assert report["normalized_economic_candidate_count"] == 0
        assert report["independent_source_admitted"] is False
        assert report["source_admission_state"] == "UNVERIFIED_LOCAL_SNAPSHOT_ONLY"
        assert "independent_tenant_issuer_and_frozen_forecast_receipts_required" in report["blockers"]
        assert report["execution_authority"] == "none"
        assert report["actual_revenue"] is False


def test_forged_positive_original_flags_cannot_make_cloud_ready(tmp_path):
    files(tmp_path)
    result = refresh_predictive_cloud_materializers(tmp_path, now=NOW)
    assert_held(result)
    trend = result["future_trend"]
    assert trend["source_reported_probability_ready_product_count"] == 3
    assert trend["source_reported_timing_ready_product_count"] == 3
    assert trend["source_reported_matched_outcome_count"] == 30
    assert trend["source_reported_economic_candidate_count"] == 1
    assert trend["verified_terminal_outcome_count"] == 0
    for file in (TREND_OUTPUT, FORMULA_OUTPUT):
        persisted = json.loads((tmp_path / file).read_text())
        assert persisted["prediction_ready"] is False
        assert persisted["source_admission_state"] == "UNVERIFIED_LOCAL_SNAPSHOT_ONLY"


@pytest.mark.parametrize("outcome,probability,timing", [
    (0, 0, 0),
    (20, 1, 1),
    (200, 86, 86),
    (True, True, False),
    ("bogus", -1, "22"),
    (float("inf"), 100, None),
])
def test_unverified_or_invalid_counts_cannot_authorize_predictions(
    tmp_path, outcome, probability, timing,
):
    files(tmp_path, outcome=outcome, probability=probability, timing=timing)
    result = refresh_predictive_cloud_materializers(tmp_path, now=NOW)
    assert_held(result)
    for record in (result["future_trend"], result["predictive_cloud_formula"]):
        assert record["probability_ready_product_count"] == 0
        assert record["prediction_ready"] is False


def test_fake_economics_refs_are_never_independently_attested(tmp_path):
    files(tmp_path, refs=False)
    result = refresh_predictive_cloud_materializers(tmp_path, now=NOW)
    assert_held(result)
    assert result["future_trend"]["source_reported_economic_candidate_count"] == 0


def test_bad_candidate_counts_do_not_crash_materializer(tmp_path):
    files(tmp_path)
    path = tmp_path / "runtime/opportunity_factory/value_latest.json"
    data = json.loads(path.read_text())
    data["candidate_count"] = "not a number"
    path.write_text(json.dumps(data))
    save(tmp_path, "runtime/opportunity_radar/latest.json", {
        "candidate_count": 2000000000000000000,
    })
    result = refresh_predictive_cloud_materializers(tmp_path, now=NOW)
    assert_held(result)
    assert result["future_trend"]["candidate_count"] == 0
