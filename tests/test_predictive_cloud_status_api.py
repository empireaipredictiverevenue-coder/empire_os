"""Predictive Cloud status API must not promote malformed or stale snapshots."""
from datetime import datetime, timedelta, timezone
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.predictive_cloud_status import build_predictive_cloud_status
from empire_os.predictive_cloud_status_api import (
    create_predictive_cloud_status_router,
    read_predictive_cloud_status,
)

NOW = datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc)


def snapshot(tmp_path, at=NOW):
    path = tmp_path / "status.json"
    report = build_predictive_cloud_status(tmp_path, now=at)
    path.write_text(json.dumps(report))
    return path, report


def test_missing_snapshot_is_unavailable(tmp_path):
    result = read_predictive_cloud_status(tmp_path / "missing.json", now=NOW)
    assert result["available"] is False
    assert result["mode"] == "OBSERVE"
    assert result["execution_authority"] == "none"
    assert result["framework_operational"] is False
    assert result["customer_forecast_verified"] is False


def test_api_exposes_valid_v2_snapshot_read_only(tmp_path):
    path, report = snapshot(tmp_path, at=datetime.now(timezone.utc))

    app = FastAPI()
    app.include_router(create_predictive_cloud_status_router(path))
    response = TestClient(app).get("/v1/predictive-cloud/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["schema_version"] == "empire.predictive_cloud.status.v2"
    assert body["mode"] == "OBSERVE"
    assert body["component_count"] == len(report["components"])
    assert body["framework_operational"] is False
    assert body["customer_forecast_verified"] is False
    assert body["execution_authority"] == "none"


def _fixed_datetime(fixed):
    original = datetime
    class FixedDatetime(original):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz else fixed.replace(tzinfo=None)
        @classmethod
        def fromisoformat(cls, value):
            return original.fromisoformat(value)
    return FixedDatetime


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(schema_version="empire.predictive_cloud.status.v1"),
    lambda x: x.update(mode="ACTIVATE"),
    lambda x: x.update(execution_authority="send"),
    lambda x: x.update(customer_forecast_verified=True),
    lambda x: x.update(commercial_prediction_authorized=True),
    lambda x: x.update(outreach_sent_by_status=True),
    lambda x: x.update(component_count=1),
    lambda x: x.update(available_component_count=50),
    lambda x: x.update(runtime_all_sources_fresh=True),
    lambda x: x.update(framework_operational=True),
    lambda x: x.update(components={"fake": {"available": True}}),
    lambda x: x.update(generated_at="2020-01-01T00:00:00+00:00"),
    lambda x: x.update(generated_at="2027-01-01T00:00:00+00:00"),
    lambda x: x.update(generated_at="not-a-date"),
    lambda x: x.update(stale_components=["predictive_intelligence"]),
    lambda x: x.update(future_untrusted_components=["fake"]),
])
def test_modified_snapshot_rejected(tmp_path, mutate):
    path, report = snapshot(tmp_path)
    mutate(report)
    path.write_text(json.dumps(report))
    result = read_predictive_cloud_status(path, now=NOW)
    assert result["available"] is False
    assert result["execution_authority"] == "none"
    assert result["customer_forecast_verified"] is False
    assert result["components"] == {}


def test_forged_fresh_component_with_stale_evidence_is_held(tmp_path):
    path, report = snapshot(tmp_path)
    payload = report["components"]["predictive_intelligence"]
    payload.update(
        available=True,
        freshness="fresh",
        observed_at="2026-10-01T10:00:00+00:00",
        age_seconds=0,
    )
    report["available_component_count"] += 1
    report["fresh_component_count"] += 1
    report["unavailable_components"].remove("predictive_intelligence")
    path.write_text(json.dumps(report))
    result = read_predictive_cloud_status(path, now=NOW)
    assert result["available"] is False
    assert result["customer_forecast_verified"] is False


def test_bounded_and_symlinked_status_files_refused(tmp_path):
    path, report = snapshot(tmp_path)
    path.write_bytes(b"X" * 200_100)
    assert read_predictive_cloud_status(path, now=NOW)["reason_code"] == "SOURCE_OVERSIZED"
    path.unlink()
    original = tmp_path / "sensitive.json"
    original.write_text(json.dumps(report))
    path.symlink_to(original)
    assert read_predictive_cloud_status(path, now=NOW)["reason_code"] == "SOURCE_SYMLINK_REFUSED"


def test_does_not_echo_unknown_top_level_data(tmp_path):
    path, report = snapshot(tmp_path)
    report["private_contact_email"] = "confidential@example.invalid"
    path.write_text(json.dumps(report))
    response = read_predictive_cloud_status(path, now=NOW)
    assert response["available"] is True
    assert "confidential@example.invalid" not in json.dumps(response)
    assert "private_contact_email" not in response


def test_real_snapshot_schema_is_readable_when_recent(tmp_path):
    path, report = snapshot(tmp_path)
    response = read_predictive_cloud_status(path, now=NOW + timedelta(minutes=2))
    assert response["available"] is True
    assert response["runtime_all_sources_fresh"] is False


def test_stale_even_well_formed_snapshot_is_held(tmp_path):
    path, report = snapshot(tmp_path)
    assert (read_predictive_cloud_status(path, now=NOW + timedelta(minutes=16))
            ["reason_code"] == "SOURCE_UNVERIFIED_OR_STALE")
