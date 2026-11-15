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
