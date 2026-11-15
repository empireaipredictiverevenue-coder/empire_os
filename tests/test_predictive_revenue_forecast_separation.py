import json
from datetime import datetime, timezone

from empire_os.predictive_revenue_forecast_separation import (
    classify_record, audit_runtime, write_report,
)

BASE = {
    "forecast_ref": "forecast:cohort001",
    "tenant_id": "tenant-alpha",
    "metric": "recognized_revenue_cents",
    "forecast_registered_at": "2026-11-01T10:00:00Z",
    "target_day": "2026-11-08",
    "horizon_days": 7,
    "predicted_cents": 15000,
}


def test_real_forecast_shape_not_generic_operational_evidence():
    assert classify_record(BASE) == "structural_forecast"
    assert classify_record({"predictive_revenue": True}) == "operational"
    assert classify_record({"forecast_revenue_cents": 900}) == "forecast_like_incomplete"
    assert classify_record({**BASE, "tenant_id": None}) == "forecast_like_incomplete"
    assert classify_record({**BASE, "target_day": "2026-11-09"}) == "forecast_like_incomplete"


def test_type_and_time_rejections():
    assert classify_record({**BASE, "predicted_cents": True}) == "operational"
    assert classify_record({**BASE, "predicted_cents": -1}) == "operational"
    assert classify_record({**BASE, "predicted_cents": float("nan")}) == "operational"
    assert classify_record({**BASE, "forecast_registered_at": "2026-11-01"}) == "forecast_like_incomplete"
    assert classify_record({**BASE, "horizon_days": 366}) == "forecast_like_incomplete"


def test_report_separates_claimed_actual_from_verified_actual(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "snapshot.json").write_text(json.dumps({
        "status": {"predictive_revenue": "healthy"},
        "observations": [
            BASE,
            {**BASE, "forecast_ref": "forecast:cohort002",
             "predicted_cents": 0, "actual_cents": 9000,
             "actual_verified": True},
            {"forecast_revenue_cents": 300},
        ],
    }))
    (runtime / "predictive_revenue_control").mkdir()
    (runtime / "predictive_revenue_control" / "self.json").write_text(
        json.dumps(BASE))
    result = audit_runtime(runtime, now=datetime(2026, 11, 15, tzinfo=timezone.utc))
    assert result["structural_forecast_records"] == 2
    assert result["structural_forecasts_with_claimed_actuals"] == 1
    assert result["forecast_like_incomplete_records"] == 1
    assert result["independently_verified_customer_outcome_pairs"] == 0
    assert not result["forecast_accuracy_measurable"]
    assert result["customer_revenue_verified"] is False
    output = tmp_path / "report.json"
    assert write_report(runtime, output)["mode"] == "OBSERVE"
    assert json.loads(output.read_text())["production_mutation"] is False


def test_missing_runtime_fails_closed(tmp_path):
    try:
        audit_runtime(tmp_path / "missing")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        assert False

REGISTRY = {
    "forecast_key": "tenant-alpha:2026-11-01:recognized_revenue_cents",
    "dimension_key": "tenant:alpha",
    "metric": "recognized_revenue_cents",
    "generated_at": "2026-11-01T10:00:00+00:00",
    "horizon_days": 7,
    "sample_count": 14,
    "predicted_value": 9000,
}


def test_existing_registry_row_format_is_not_customer_verification():
    assert classify_record(REGISTRY) == "registry_shape_unverified"
    assert classify_record({**REGISTRY, "dimension_key": "global"}) == "forecast_like_incomplete"
    assert classify_record({**REGISTRY, "predicted_value": True}) == "operational"
    assert classify_record({**REGISTRY, "sample_count": 0}) == "forecast_like_incomplete"


def test_registry_shape_only_remains_unverified_even_with_claimed_actual(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "predictive_cloud").mkdir(parents=True)
    (runtime / "registry.json").write_text(json.dumps({
        **REGISTRY, "actual_cents": 7000, "actual_verified": True,
    }))
    (runtime / "predictive_cloud" / "status_latest.json").write_text(json.dumps({
        "original_frozen_forecast_registry_authenticated_by_status": False,
        "customer_forecast_verified": False,
    }))
    result = audit_runtime(runtime)
    assert result["registry_shaped_unverified_records"] == 1
    assert result["structural_forecasts_with_claimed_actuals"] == 1
    assert result["independently_verified_customer_outcome_pairs"] == 0
    assert result["reported_registry_authentication_from_status"] is False
    assert result["reported_customer_forecast_verified_from_status"] is False
    assert result["forecast_accuracy_measurable"] is False


def test_uses_existing_finance_proof_gap_reader_without_promoting_actuals(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "registry.json").write_text(json.dumps({
        **REGISTRY,
        "customer_forecast_verified": True,
        "actual_revenue": True,
    }))
    report = audit_runtime(runtime)
    assert report["registry_shaped_unverified_records"] == 1
    assert report["original_independent_finance_gaps_not_admitted"] == 7
    assert "FORECAST_OUTCOME_CALIBRATION" in report[
        "original_independent_finance_gap_codes"
    ]
    assert report["independently_verified_customer_outcome_pairs"] == 0
    assert report["forecast_origin_verified"] is False
    assert report["customer_revenue_verified"] is False


def test_jev_existing_research_is_context_not_revenue_ground_truth(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "jev_client_pain_discovery").mkdir(parents=True)
    at = datetime(2026, 11, 15, 14, tzinfo=timezone.utc)
    (runtime / "jev_client_pain_discovery" / "aggregate_latest.json").write_text(
        json.dumps({
            "schema_version": "empire.jev.client_pain_production_observe.v1",
            "status": "CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY",
            "generated_at_utc": "2026-11-14T20:00:00Z",
            "mode": "OBSERVE", "execution_authority": "none",
            "model_calls": 0, "database_writes": False, "crm_writes": False,
        })
    )
    report = audit_runtime(runtime, now=at)
    assert report["jev_evidence_observation"]["research_signal_available"] is True
    assert report["jev_evidence_observation"]["model_calls_verified"] == 0
    assert report["decision_support"]["state"] == "GATHER_EVIDENCE"
    assert report["decision_support"]["recommended_next_action"] == (
        "VERIFY_EXISTING_TENANT_BOUND_FORECAST_REGISTRY"
    )
    assert report["decision_support"]["forecast_accuracy_confidence"] is None
    assert report["decision_support"]["automated_action_executed"] is False
    assert report["independently_verified_customer_outcome_pairs"] == 0
    assert report["forecast_accuracy_measurable"] is False
    # Replacing independent financial proof with a JEV model-call count fails.
    path = runtime / "jev_client_pain_discovery" / "aggregate_latest.json"
    row = json.loads(path.read_text())
    row["model_calls"] = 1
    path.write_text(json.dumps(row))
    assert audit_runtime(runtime, now=at)["jev_evidence_observation"][
        "research_signal_available"] is False


def test_rg_permission_error_keeps_partial_coverage_visible(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from empire_os import predictive_revenue_forecast_separation as unit

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    first = runtime / "existing.json"
    first.write_text(json.dumps(BASE))
    monkeypatch.setattr(unit.shutil, "which", lambda _: "/bin/rg")
    monkeypatch.setattr(unit.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=2, stdout=(str(first).encode() + b"\0"), stderr=b"denied"
    ))
    result = audit_runtime(runtime)
    assert result["source_prefilter"] == "ripgrep_partial"
    assert result["fast_prefilter_failed_or_unavailable"] is True
    assert result["source_scan_exhaustive"] is False
    assert result["source_scan_complete_enough_for_absence_claim"] is False
    assert result["structural_forecast_records"] == 1
    assert result["independently_verified_customer_outcome_pairs"] == 0


def test_no_ripgrep_falls_back_without_losing_records(tmp_path, monkeypatch):
    from empire_os import predictive_revenue_forecast_separation as unit
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "one.json").write_text(json.dumps(BASE))
    monkeypatch.setattr(unit.shutil, "which", lambda _: None)
    result = audit_runtime(runtime)
    assert result["source_prefilter"] == "python_exhaustive_fallback"
    assert result["structural_forecast_records"] == 1
    assert result["fast_prefilter_failed_or_unavailable"] is True
