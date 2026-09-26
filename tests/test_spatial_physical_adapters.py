import pytest

from empire_os.satellite_scanner import SatelliteScanResult
from empire_os.spatial_physical_adapters import (
    physical_from_satellite_vision,
    physical_from_storm_event,
)
from empire_os.spatial_physical_fusion import fuse_spatial_physical_priority
from empire_os.storm_predictor import StormEvent


def test_nws_alert_becomes_exposure_not_damage():
    event = StormEvent(
        event_id="nws:alert:1",
        event_type="Severe Thunderstorm Warning",
        severity=4,
        area_description="Dallas County, TX",
        occurred_at="2026-09-21T15:00:00Z",
        raw={"certainty": "Observed", "urgency": "Immediate"},
    )
    row = physical_from_storm_event(event)

    assert row.phenomenon == "storm_exposure"
    assert row.evidence_class == "observed"
    assert row.measurements["severity_index"] == 4.0
    assert row.confidence == 0.95
    assert row.execution_authority == "none"


def test_heuristic_satellite_result_is_rejected():
    result = SatelliteScanResult(
        zip_code="75201",
        damage_score=28,
        dominant_damage="unknown",
        confidence=0.3,
        method="heuristic",
        scanned_at="2026-09-21T15:05:00Z",
    )
    with pytest.raises(ValueError, match="only llm_vision"):
        physical_from_satellite_vision(
            result,
            subject_ref="property:75201:warehouse-1",
            evidence_ref="satellite:scan:1",
        )


def test_vision_satellite_result_is_model_inference():
    result = SatelliteScanResult(
        zip_code="75201",
        warehouses_detected=3,
        damage_score=82,
        dominant_damage="hail",
        confidence=0.86,
        method="llm_vision",
        scanned_at="2026-09-21T15:05:00Z",
    )
    row = physical_from_satellite_vision(
        result,
        subject_ref="property:75201:warehouse-1",
        evidence_ref="satellite:scan:vision:1",
    )

    assert row.phenomenon == "storm_damage"
    assert row.evidence_class == "model_inference"
    assert row.measurements["damage_score"] == 82.0
    assert row.evidence_refs == ("satellite:scan:vision:1",)
    assert row.execution_authority == "none"


def test_model_inference_receives_lower_priority_weight_than_observed():
    inferred = physical_from_satellite_vision(
        SatelliteScanResult(
            damage_score=80,
            warehouses_detected=2,
            dominant_damage="hail",
            confidence=0.9,
            method="llm_vision",
            scanned_at="2026-09-21T15:05:00Z",
        ),
        subject_ref="property:1",
        evidence_ref="satellite:vision:1",
    )
    observed = inferred.__class__(
        subject_ref=inferred.subject_ref,
        source="inspection",
        observed_at=inferred.observed_at,
        phenomenon=inferred.phenomenon,
        evidence_refs=("inspection:1",),
        measurements=inferred.measurements,
        units=inferred.units,
        confidence=inferred.confidence,
        evidence_class="observed",
    )

    inferred_priority = fuse_spatial_physical_priority(
        vertical="roofing",
        physical=inferred,
    )
    observed_priority = fuse_spatial_physical_priority(
        vertical="roofing",
        physical=observed,
    )
    assert inferred_priority.spatial_physical_priority_boost < (
        observed_priority.spatial_physical_priority_boost
    )


def test_storm_exposure_does_not_double_count_as_damage_boost():
    row = physical_from_storm_event(
        StormEvent(
            event_id="nws:alert:2",
            event_type="High Wind Warning",
            severity=4,
            area_description="Dallas County, TX",
            occurred_at="2026-09-21T15:00:00Z",
            raw={"certainty": "Likely"},
        )
    )
    fused = fuse_spatial_physical_priority(
        vertical="roofing",
        physical=row,
    )
    assert fused.physical_relevant is False
    assert fused.spatial_physical_priority_boost == 0
    assert fused.demand_multiplier_hint == 1.0
