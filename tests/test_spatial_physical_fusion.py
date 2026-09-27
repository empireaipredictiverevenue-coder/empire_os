import pytest

from empire_os.spatial_physical_fusion import (
    digital_twin_demand_scenario,
    digital_twin_evidence,
    fuse_spatial_physical_priority,
)
from empire_os.spatial_physical_intelligence import (
    PhysicalObservation,
    VolumetricObservation,
)
from empire_os.storm_revenue_multiplier import calculate_storm_multiplier


def volumetric(confidence=0.85):
    return VolumetricObservation(
        subject_ref="property:dfw:123",
        source="drone_imagery",
        observed_at="2026-09-21T16:00:00Z",
        representation="mesh",
        evidence_refs=("evidence:drone:123",),
        confidence=confidence,
    )


def physical(phenomenon="roof_condition", confidence=0.9):
    return PhysicalObservation(
        subject_ref="property:dfw:123",
        source="roof_condition_model",
        observed_at="2026-09-21T16:01:00Z",
        phenomenon=phenomenon,
        evidence_refs=("evidence:roof:123",),
        measurements={"surface_change_ratio": 0.31},
        units={"surface_change_ratio": "ratio"},
        confidence=confidence,
    )


def storm():
    return calculate_storm_multiplier(
        niche="roofing",
        event_type="hail",
        severity="severe",
        evidence_confidence=0.95,
        territory_match=1.0,
        age_hours=8,
        evidence_refs=("nws:dfw:2026-09-21",),
    )


def test_roofing_fusion_adds_bounded_evidence_backed_priority():
    base = storm()
    fused = fuse_spatial_physical_priority(
        vertical="roofing",
        volumetric=volumetric(),
        physical=physical(),
        storm=base,
    )

    assert fused.physical_relevant is True
    assert fused.spatial_physical_priority_boost > 0
    assert fused.combined_priority_boost > base.priority_boost
    assert fused.combined_priority_boost <= 60
    assert fused.demand_multiplier_hint >= base.multiplier
    assert fused.demand_multiplier_hint <= 3
    assert fused.modeled_only is True
    assert fused.execution_authority == "none"
    assert set(fused.evidence_refs) == {
        "evidence:drone:123",
        "evidence:roof:123",
        "nws:dfw:2026-09-21",
    }


def test_irrelevant_physical_phenomenon_does_not_boost_solar():
    fused = fuse_spatial_physical_priority(
        vertical="solar",
        volumetric=volumetric(),
        physical=physical(phenomenon="hvac_load"),
    )
    assert fused.physical_relevant is False
    assert fused.physical_confidence is None
    assert fused.spatial_physical_priority_boost == pytest.approx(6.8)


def test_unknown_confidence_does_not_invent_numeric_boost():
    fused = fuse_spatial_physical_priority(
        vertical="property",
        volumetric=volumetric(confidence=None),
    )
    assert fused.spatial_confidence is None
    assert fused.spatial_physical_priority_boost == 0
    assert fused.demand_multiplier_hint == 1.0


def test_subject_mismatch_fails_closed():
    other = PhysicalObservation(
        subject_ref="property:other",
        source="thermal",
        observed_at="2026-09-21T16:01:00Z",
        phenomenon="thermal_loss",
        evidence_refs=("evidence:thermal:other",),
        confidence=0.8,
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        fuse_spatial_physical_priority(
            vertical="property",
            volumetric=volumetric(),
            physical=other,
        )


def test_digital_twin_scenario_changes_demand_only_and_stays_evidenced():
    fused = fuse_spatial_physical_priority(
        vertical="roofing",
        volumetric=volumetric(),
        physical=physical(),
        storm=storm(),
    )
    scenario = digital_twin_demand_scenario(
        scenario_id="roofing-dfw-spatial-physical-v1",
        priority=fused,
    )
    evidence = digital_twin_evidence(fused)

    assert scenario.demand_multiplier == fused.demand_multiplier_hint
    assert scenario.capacity_multiplier == 1.0
    assert scenario.price_multiplier == 1.0
    assert evidence["modeled_only"] is True
    assert evidence["actual_revenue"] is False
    assert evidence["execution_authority"] == "none"
