"""Four ecosystem adapters: offline science, safe tracing, no remote UX tracking."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from empire_os.flagship_quality_integrations import (
    CATEGORIES,
    emit_flagship_quality_trace,
    flagship_vendor_readiness,
    quality_distribution_preflight,
    run_offline_evidently_report,
)
from empire_os.telemetry import JsonlTelemetrySink, NullTelemetrySink
from empire_os.predictive_decision_control import build_predictive_decision_control_runtime


NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def counts(**values):
    base = {category: 0 for category in CATEGORIES}
    base.update(values)
    return base


def test_offline_source_quality_delta_is_not_called_statistically_significant():
    old = counts(OBSERVED=12, HELD=2)
    new = counts(OBSERVED=10, HELD=3, STALE=1)
    result = quality_distribution_preflight(old, new, as_of=NOW)
    assert result["status"] == "BOUNDED_QUALITY_DISTRIBUTION_REVIEW"
    assert result["reference_n"] == 14
    assert result["current_n"] == 14
    assert result["absolute_proportion_changes"]["STALE"] > 0
    assert result["statistical_significance_established"] is False
    assert result["evidently_drift_test_executed"] is False
    assert result["source_quality_evidence_verified"] is False


def test_empty_or_insufficient_source_denominator_never_proves_zero_drift():
    output = quality_distribution_preflight(
        counts(), counts(OBSERVED=2), as_of=NOW,
    )
    assert output["status"] == "INSUFFICIENT_REFERENCE_OR_CURRENT_AGGREGATE"
    assert output["absolute_proportion_changes"] is None
    assert output["source_quality_evidence_verified"] is False


@pytest.mark.parametrize("bad", [
    {"OBSERVED": -1},
    {"OBSERVED": True},
    {"OBSERVED": 1000},
    {"OBSERVED": "email@example.com"},
    {"OBSERVED": 1, "buyer_name": "private@example.com"},
])
def test_aggregate_quality_rejects_suspicious_unbounded_or_private_data(bad):
    sample = counts()
    sample.update(bad)
    with pytest.raises(ValueError):
        quality_distribution_preflight(sample, counts(OBSERVED=1), as_of=NOW)


def test_evidently_optional_adapter_runs_only_when_explicitly_invoked():
    called = []
    def fake_report():
        called.append(1)
        return object()
    result = run_offline_evidently_report(
        counts(OBSERVED=6,HELD=1),
        counts(OBSERVED=4,HELD=3),
        as_of=NOW, report_factory=fake_report,
    )
    assert called == [1]
    assert result["evidently_drift_test_executed"] is True
    assert result["evidently_run_status"] == "OFFLINE_EVALUATION_EXECUTED"
    assert result["statistical_significance_established"] is False
    assert result["report_stored_or_uploaded"] is False
    assert result["source_quality_evidence_verified"] is False


def test_evidently_provider_exception_is_masked_and_does_not_leak_contact():
    def failed():
        raise RuntimeError("api_key=private-super-secret")
    result = run_offline_evidently_report(
        counts(OBSERVED=1), counts(OBSERVED=1),
        as_of=NOW, report_factory=failed,
    )
    assert result["evidently_run_status"] == "OFFLINE_EVALUATION_HELD"
    assert "private-super-secret" not in json.dumps(result)
    assert result["evidently_drift_test_executed"] is False


def test_local_otel_trace_only_emits_allowlisted_result_state(tmp_path):
    target = tmp_path / "events.jsonl"
    output = emit_flagship_quality_trace(
        JsonlTelemetrySink(target),
        kind="customer_results_explanation", status="HELD",
        duration_ms=24, as_of=NOW,
    )
    assert output["external_export_verified"] is False
    event = json.loads(target.read_text().strip())
    assert event["name"] == "empire.flagship.customer_results_explanation"
    assert event["attributes"]["empire.flagship.duration_ms"] == 24
    assert event["attributes"]["empire.flagship.customer_contact_included"] is False
    assert "buyer_name" not in json.dumps(event)
    assert "tenant_id" not in json.dumps(event)


@pytest.mark.parametrize("kind,status,duration", [
    ("email:jane@example.com", "HELD", 2),
    ("source_quality_review", "buyer@example.com", 2),
    ("source_quality_review", "HELD", -1),
    ("source_quality_review", "HELD", 99999999),
    ("source_quality_review", "HELD", True),
])
def test_tracing_rejects_arbitrary_private_attributes(kind,status,duration):
    with pytest.raises(ValueError):
        emit_flagship_quality_trace(
            NullTelemetrySink(), kind=kind, status=status,
            duration_ms=duration, as_of=NOW,
        )


def test_four_vendor_readiness_adapters_remain_held_without_export():
    status = flagship_vendor_readiness(as_of=NOW)
    assert set(status["integrations"]) == {
        "evidently", "langfuse", "posthog", "openreplay"
    }
    assert all(
        provider["provider_fork_created"] is False
        for provider in status["integrations"].values()
    )
    assert status["integrations"]["langfuse"]["remote_export_enabled_by_this_feature"] is False
    assert status["integrations"]["posthog"]["autocapture_enabled"] is False
    assert status["integrations"]["openreplay"]["session_recording_enabled"] is False
    assert status["external_customer_data_transmitted"] is False
    assert status["actual_model_calibration_performed"] is False
    assert status["execution_authority"] == "none"


def test_existing_founder_decision_includes_research_vendor_status(tmp_path):
    # The surrounding Founder decision system handles missing source files.
    result = build_predictive_decision_control_runtime(tmp_path, as_of=NOW)
    vendor = result["flagship_quality_integrations"]
    assert vendor["schema_version"] == "empire.flagship_scientific_experience_integrations.v1"
    assert vendor["integrations"]["evidently"]["remote_upload_enabled"] is False
    assert vendor["integrations"]["posthog"]["network_enabled"] is False
